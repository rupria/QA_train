"""Read Python source and compare symbols without executing either version.

The AST stored on a SourceUnit is complete. A CodeSymbol's ``ast_dump`` owns
only its scope: child definitions are represented by name/kind placeholders.
This keeps a method body edit from also becoming a class and module body edit.
"""

from __future__ import annotations

import ast
import copy
import difflib
import json
import os
import tokenize
from dataclasses import dataclass
from pathlib import Path

from ast_analyzer import IGNORED_DIRS, sanitize_notebook_source


@dataclass
class SourceUnit:
    path: str
    module: str
    source: str
    tree: ast.Module | None
    error: str | None
    preprocessed: bool = False


@dataclass
class CodeSymbol:
    id: str
    file: str
    module: str
    qualified_name: str
    kind: str
    node: ast.AST
    start_line: int
    end_line: int
    source: str
    ast_dump: str


@dataclass
class Snapshot:
    input_path: str
    units: dict[str, SourceUnit]
    symbols: dict[str, CodeSymbol]
    errors: list[dict]
    warnings: list[str]


_DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_KINDS = {
    ast.FunctionDef: "function",
    ast.AsyncFunctionDef: "async_function",
    ast.ClassDef: "class",
}


def _module_name(file_key: str) -> str:
    parts = list(Path(file_key).with_suffix("").parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or Path(file_key).stem


class _ScopeOnly(ast.NodeTransformer):
    """Replace child declarations, including declarations inside branches.

    Their name, definition kind, and position among executable statements are
    significant for the enclosing scope. Their implementation is owned by the
    child symbol and is intentionally not duplicated here.
    """

    def _definition(self, node: ast.AST) -> ast.AST:
        kind = _KINDS[type(node)]
        return ast.Expr(value=ast.Constant(value=f"<definition:{kind}:{node.name}>"))

    visit_FunctionDef = _definition
    visit_AsyncFunctionDef = _definition
    visit_ClassDef = _definition


def _own_ast(node: ast.AST) -> str:
    own = copy.deepcopy(node)
    # Apply the transformer to children, never to the symbol's own declaration.
    own = _ScopeOnly().generic_visit(own)
    return ast.dump(own, annotate_fields=True, include_attributes=False, indent=2)


def _unit_symbols(unit: SourceUnit) -> dict[str, CodeSymbol]:
    if unit.tree is None:
        return {}
    symbols: dict[str, CodeSymbol] = {}
    lines = unit.source.splitlines(keepends=True)

    def add(node: ast.AST, qualified_name: str, kind: str) -> None:
        if isinstance(node, ast.Module):
            start_line, end_line, source = 1, max(len(lines), 1), unit.source
        else:
            decorators = getattr(node, "decorator_list", [])
            start_line = min([node.lineno] + [item.lineno for item in decorators])
            end_line = node.end_lineno or node.lineno
            source = "".join(lines[start_line - 1 : end_line])
        symbol_id = f"{unit.path}::{qualified_name}"
        if symbol_id in symbols:
            raise ValueError(
                f"Duplicate qualified name {qualified_name!r}; "
                "conditional/repeated definitions cannot be matched safely."
            )
        symbols[symbol_id] = CodeSymbol(
            symbol_id,
            unit.path,
            unit.module,
            qualified_name,
            kind,
            node,
            start_line,
            end_line,
            source,
            _own_ast(node),
        )

    def visit(node: ast.AST, scope: tuple[str, ...]) -> None:
        next_scope = scope
        if isinstance(node, _DEFINITIONS):
            next_scope = (*scope, node.name)
            add(node, ".".join(next_scope), _KINDS[type(node)])
        for child in ast.iter_child_nodes(node):
            visit(child, next_scope)

    add(unit.tree, "<module>", "module")
    visit(unit.tree, ())
    return symbols


def _record_error(snapshot: Snapshot, unit: SourceUnit, exc: Exception | str) -> None:
    unit.error = exc if isinstance(exc, str) else f"{type(exc).__name__}: {exc}"
    unit.tree = None
    snapshot.units[unit.path] = unit
    snapshot.errors.append({"file": unit.path, "error": unit.error})


def _add_unit(snapshot: Snapshot, unit: SourceUnit, parsed_source: str | None = None) -> None:
    try:
        unit.tree = ast.parse(
            unit.source if parsed_source is None else parsed_source,
            filename=unit.path,
        )
        symbols = _unit_symbols(unit)
    except (SyntaxError, ValueError, RecursionError) as exc:
        _record_error(snapshot, unit, exc)
        return
    snapshot.units[unit.path] = unit
    snapshot.symbols.update(symbols)


def _load_python(snapshot: Snapshot, path: Path, file_key: str) -> None:
    unit = SourceUnit(file_key, _module_name(file_key), "", None, None)
    try:
        # Honor PEP 263 encoding declarations; never import or execute the file.
        with tokenize.open(path) as handle:
            unit.source = handle.read()
    except (OSError, UnicodeError, SyntaxError) as exc:
        _record_error(snapshot, unit, exc)
        return
    _add_unit(snapshot, unit)


def _load_notebook(snapshot: Snapshot, path: Path, file_key: str) -> None:
    container_unit = SourceUnit(file_key, _module_name(file_key), "", None, None)
    try:
        notebook = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(notebook, dict) or not isinstance(notebook.get("cells"), list):
            raise ValueError("Notebook must contain a 'cells' list.")
        for cell in notebook["cells"]:
            if not isinstance(cell, dict):
                raise ValueError("Every notebook cell must be an object.")
            if cell.get("cell_type") == "code":
                raw = cell.get("source", "")
                if not isinstance(raw, str) and not (
                    isinstance(raw, list) and all(isinstance(line, str) for line in raw)
                ):
                    raise ValueError("Code cell source must be a string or a list of strings.")
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        _record_error(snapshot, container_unit, exc)
        return

    snapshot.warnings.append(
        f"{file_key}: notebook code cells are matched by original cell index; "
        "inserting/reordering cells can appear as additions or deletions. "
        "Notebook runtime state and cross-cell symbol resolution are not analyzed."
    )
    code_cells = 0
    for cell_number, cell in enumerate(notebook["cells"], start=1):
        if cell.get("cell_type") != "code":
            continue
        code_cells += 1
        raw = cell.get("source", "")
        source = "".join(raw) if isinstance(raw, list) else raw
        parsed_source = sanitize_notebook_source(source)
        preprocessed = source.splitlines() != parsed_source.splitlines()
        key = f"{file_key}#cell-{cell_number}"
        unit = SourceUnit(
            key, f"{_module_name(file_key)}.cell_{cell_number}", source, None, None, preprocessed
        )
        if preprocessed:
            snapshot.warnings.append(
                f"{key}: IPython commands/cell magic were preprocessed by "
                "sanitize_notebook_source; discarded commands are outside AST comparison. "
                "%%writefile bodies are interpreted as Python source only."
            )
        _add_unit(snapshot, unit, parsed_source)
    if not code_cells:
        # Empty notebooks are valid but have no comparable Python implementation.
        snapshot.warnings.append(f"{file_key}: notebook contains no Python code cells.")


def load_snapshot(path: Path, single_file_key: str | None = None) -> Snapshot:
    """Load .py/.ipynb input; invalid roots raise, bad source units are recorded.

    For two standalone files with different names, pass the same single_file_key
    to both loads. Directories always retain their relative file paths.
    """
    path = Path(path).resolve()
    if not path.exists():
        raise FileNotFoundError(f"Source input does not exist: {path}")
    snapshot = Snapshot(str(path), {}, {}, [], [])
    if path.is_file():
        if path.suffix.lower() not in {".py", ".ipynb"}:
            raise ValueError(f"Unsupported source extension {path.suffix!r}; use .py or .ipynb.")
        files = [(path, single_file_key or path.name)]
    elif path.is_dir():
        if single_file_key is not None:
            raise ValueError("single_file_key is only supported for a standalone source file.")
        files = []

        def walk_error(exc: OSError) -> None:
            file_key = os.path.relpath(exc.filename or path, path).replace("\\", "/")
            unit = SourceUnit(file_key, _module_name(file_key), "", None, None)
            _record_error(snapshot, unit, exc)

        for directory, dirs, names in os.walk(path, onerror=walk_error, followlinks=False):
            dirs[:] = sorted(
                name for name in dirs if name not in IGNORED_DIRS and not name.startswith(".venv")
            )
            for name in sorted(names):
                source_path = Path(directory) / name
                if source_path.suffix.lower() in {".py", ".ipynb"}:
                    files.append((source_path, source_path.relative_to(path).as_posix()))
        if not files and not snapshot.errors:
            raise ValueError(f"Source directory contains no .py or .ipynb files: {path}")
    else:
        raise ValueError(f"Source input must be a regular file or directory: {path}")
    for source_path, file_key in sorted(files, key=lambda item: item[1]):
        if source_path.suffix.lower() == ".ipynb":
            _load_notebook(snapshot, source_path, file_key)
        else:
            _load_python(snapshot, source_path, file_key)
    snapshot.warnings.append(
        "AST comparison is structural, not proof of behavioral equivalence. "
        "Renames/moves across qualified names or files are reported as deletion/addition. "
        "Sources are never executed."
    )
    return snapshot


def _parent_container(file_key: str) -> str:
    return file_key.split("#cell-", 1)[0]


def _is_under(file_key: str, error_key: str) -> bool:
    # An unreadable directory also blocks descendant files from comparison.
    return (
        file_key == error_key
        or _parent_container(file_key) == error_key
        or file_key.startswith(error_key.rstrip("/") + "/")
        or error_key == "."
    )


def _symbol_data(symbol: CodeSymbol | None) -> dict | None:
    if symbol is None:
        return None
    return {
        "start_line": symbol.start_line,
        "end_line": symbol.end_line,
        "source": symbol.source,
        "ast": symbol.ast_dump,
    }


def _diff(before: str, after: str, label: str, *, is_ast: bool = False) -> str:
    # keepends makes source diffs faithful; add a missing newline for readable
    # diff output without implying this normalization is a semantic change.
    before_lines = before.splitlines(keepends=True)
    after_lines = after.splitlines(keepends=True)
    before_lines = [line if line.endswith("\n") else line + "\n" for line in before_lines]
    after_lines = [line if line.endswith("\n") else line + "\n" for line in after_lines]
    extension = ".ast" if is_ast else ""
    return "".join(
        difflib.unified_diff(
            before_lines,
            after_lines,
            fromfile=f"base/{label}{extension}",
            tofile=f"target/{label}{extension}",
        )
    )


def compare_snapshots(base: Snapshot, target: Snapshot) -> dict:
    """Return deterministic symbol changes, with invalid input units excluded."""
    invalid_keys = sorted(
        {key for snapshot in (base, target) for key, unit in snapshot.units.items() if unit.error}
    )
    all_unit_keys = set(base.units) | set(target.units)
    skipped_keys = sorted(
        key for key in all_unit_keys if any(_is_under(key, bad) for bad in invalid_keys)
    )
    skipped_files = []
    for key in skipped_keys:
        reasons = []
        for side, snapshot in (("base", base), ("target", target)):
            for bad_key in invalid_keys:
                unit = snapshot.units.get(bad_key)
                if unit is not None and unit.error and _is_under(key, bad_key):
                    reasons.append(f"{side}: {unit.error}")
        skipped_files.append({"file": key, "reasons": reasons})
    skipped_set = set(skipped_keys)
    changes = []
    changed_files = set()
    for symbol_id in sorted(set(base.symbols) | set(target.symbols)):
        before, after = base.symbols.get(symbol_id), target.symbols.get(symbol_id)
        symbol = after or before
        if symbol.file in skipped_set:
            continue
        if before is not None and after is not None and before.ast_dump == after.ast_dump:
            continue
        change_type = "added" if before is None else "deleted" if after is None else "modified"
        changes.append(
            {
                "id": f"CODE-{len(changes) + 1:03d}",
                "file": symbol.file,
                "symbol": symbol.qualified_name,
                "kind": symbol.kind,
                "change_type": change_type,
                "base": _symbol_data(before),
                "target": _symbol_data(after),
                "ast_diff": _diff(
                    before.ast_dump if before else "",
                    after.ast_dump if after else "",
                    symbol_id,
                    is_ast=True,
                ),
                "source_diff": _diff(
                    before.source if before else "", after.source if after else "", symbol_id
                ),
            }
        )
        changed_files.add(symbol.file)
    ignored_text_changes = sorted(
        key
        for key in set(base.units) & set(target.units)
        if key not in skipped_set
        and key not in changed_files
        and base.units[key].source != target.units[key].source
    )
    counts = {
        name: sum(change["change_type"] == name for change in changes)
        for name in ("added", "deleted", "modified")
    }
    return {
        "changes": changes,
        "skipped_files": skipped_files,
        "ignored_text_changes": ignored_text_changes,
        "summary": {
            **counts,
            "total_changes": len(changes),
            "changed_files": len(changed_files),
            "skipped_files": len(skipped_files),
            "ignored_text_changes": len(ignored_text_changes),
            "base_units": len(base.units),
            "target_units": len(target.units),
            "base_symbols": len(base.symbols),
            "target_symbols": len(target.symbols),
        },
    }
