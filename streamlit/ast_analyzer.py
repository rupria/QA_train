from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable


IGNORED_DIRS = {
    ".git",
    ".venv",
    ".venv-ast",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".ipynb_checkpoints",
    "node_modules",
}


@dataclass
class Symbol:
    name: str
    qualified_name: str
    kind: str
    start_line: int
    end_line: int
    decorators: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)


@dataclass
class ModuleInfo:
    path: str
    module: str
    feature_group: str
    imports: list[str] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    assignments: list[str] = field(default_factory=list)
    module_calls: list[str] = field(default_factory=list)
    control_flow: list[str] = field(default_factory=list)
    execution_items: list[dict[str, str | int]] = field(default_factory=list)
    error: str | None = None


@dataclass
class DiffHunk:
    path: str
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    old_lines: list[int] = field(default_factory=list)
    new_lines: list[int] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    added: list[str] = field(default_factory=list)


def dotted_name(node: ast.AST | None) -> str:
    if node is None:
        return ""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        left = dotted_name(node.value)
        return f"{left}.{node.attr}" if left else node.attr
    if isinstance(node, ast.Call):
        return dotted_name(node.func)
    return ""


class SourceAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.stack: list[str] = []
        self.symbols: list[Symbol] = []

    def _record_symbol(self, node: ast.AST, name: str, kind: str) -> None:
        qualified_name = ".".join([*self.stack, name])
        decorators = [dotted_name(item) for item in getattr(node, "decorator_list", [])]
        calls = sorted(
            {
                dotted_name(item.func)
                for item in ast.walk(node)
                if isinstance(item, ast.Call) and dotted_name(item.func)
            }
        )
        self.symbols.append(
            Symbol(
                name=name,
                qualified_name=qualified_name,
                kind=kind,
                start_line=getattr(node, "lineno", 1),
                end_line=getattr(node, "end_lineno", getattr(node, "lineno", 1)),
                decorators=decorators,
                calls=calls,
            )
        )

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self._record_symbol(node, node.name, "class")
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._record_symbol(node, node.name, "function")
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._record_symbol(node, node.name, "async_function")
        self.stack.append(node.name)
        self.generic_visit(node)
        self.stack.pop()


def compact_expression(node: ast.AST, limit: int = 180) -> str:
    try:
        value = ast.unparse(node).replace("\n", " ").strip()
    except (AttributeError, ValueError):
        value = type(node).__name__
    return value if len(value) <= limit else value[: limit - 1] + "…"


class ModuleExecutionAnalyzer(ast.NodeVisitor):
    def __init__(self) -> None:
        self.assignments: list[str] = []
        self.calls: list[str] = []
        self.control_flow: list[str] = []
        self.items: list[dict[str, str | int]] = []
        self.depth = 0

    @staticmethod
    def _append_unique(items: list[str], value: str) -> None:
        if value and value not in items:
            items.append(value)

    def _record(self, kind: str, value: str, node: ast.AST) -> None:
        self.items.append(
            {
                "kind": kind,
                "value": value,
                "line": getattr(node, "lineno", 1),
                "depth": self.depth,
            }
        )

    def _visit_nested(self, nodes: Iterable[ast.AST]) -> None:
        self.depth += 1
        for node in nodes:
            self.visit(node)
        self.depth -= 1

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Assign(self, node: ast.Assign) -> None:
        value = compact_expression(node)
        self._append_unique(self.assignments, value)
        self._record("변수 대입", value, node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        value = compact_expression(node)
        self._append_unique(self.assignments, value)
        self._record("변수 대입", value, node)

    def visit_AugAssign(self, node: ast.AugAssign) -> None:
        value = compact_expression(node)
        self._append_unique(self.assignments, value)
        self._record("변수 대입", value, node)

    def visit_Call(self, node: ast.Call) -> None:
        value = compact_expression(node)
        self._append_unique(self.calls, value)
        self._record("호출", value, node)

    def visit_If(self, node: ast.If) -> None:
        value = f"if {compact_expression(node.test)}"
        self._append_unique(self.control_flow, value)
        self._record("제어 흐름", value, node)
        self._visit_nested(node.body)
        if node.orelse:
            if len(node.orelse) == 1 and isinstance(node.orelse[0], ast.If):
                self.visit(node.orelse[0])
            else:
                self._record("제어 흐름", "else", node.orelse[0])
                self._visit_nested(node.orelse)

    def visit_For(self, node: ast.For) -> None:
        value = f"for {compact_expression(node.target)} in {compact_expression(node.iter)}"
        self._append_unique(self.control_flow, value)
        self._record("제어 흐름", value, node)
        self._visit_nested(node.body)
        if node.orelse:
            self._record("제어 흐름", "for-else", node.orelse[0])
            self._visit_nested(node.orelse)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:
        value = f"async for {compact_expression(node.target)} in {compact_expression(node.iter)}"
        self._append_unique(self.control_flow, value)
        self._record("제어 흐름", value, node)
        self._visit_nested(node.body)
        if node.orelse:
            self._record("제어 흐름", "async-for-else", node.orelse[0])
            self._visit_nested(node.orelse)

    def visit_While(self, node: ast.While) -> None:
        value = f"while {compact_expression(node.test)}"
        self._append_unique(self.control_flow, value)
        self._record("제어 흐름", value, node)
        self._visit_nested(node.body)
        if node.orelse:
            self._record("제어 흐름", "while-else", node.orelse[0])
            self._visit_nested(node.orelse)

    def visit_Try(self, node: ast.Try) -> None:
        self._append_unique(self.control_flow, "try/except")
        self._record("제어 흐름", "try", node)
        self._visit_nested(node.body)
        for handler in node.handlers:
            exception = compact_expression(handler.type) if handler.type else "Exception"
            self._record("제어 흐름", f"except {exception}", handler)
            self._visit_nested(handler.body)
        if node.orelse:
            self._record("제어 흐름", "try-else", node.orelse[0])
            self._visit_nested(node.orelse)
        if node.finalbody:
            self._record("제어 흐름", "finally", node.finalbody[0])
            self._visit_nested(node.finalbody)

    def visit_With(self, node: ast.With) -> None:
        values = ", ".join(compact_expression(item.context_expr) for item in node.items)
        value = f"with {values}"
        self._append_unique(self.control_flow, value)
        self._record("제어 흐름", value, node)
        self._visit_nested(node.body)

    def visit_Match(self, node: ast.Match) -> None:
        value = f"match {compact_expression(node.subject)}"
        self._append_unique(self.control_flow, value)
        self._record("제어 흐름", value, node)
        for case in node.cases:
            case_value = f"case {compact_expression(case.pattern)}"
            case_node = case.pattern
            self._record("제어 흐름", case_value, case_node)
            self._visit_nested(case.body)


def collect_execution_details(
    tree: ast.AST,
) -> tuple[list[str], list[str], list[str], list[dict[str, str | int]]]:
    analyzer = ModuleExecutionAnalyzer()
    analyzer.visit(tree)
    return analyzer.assignments, analyzer.calls, analyzer.control_flow, analyzer.items


def module_name(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = list(relative.parts)
    if parts and parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts) or path.stem


def feature_group(relative_path: Path) -> str:
    parts = relative_path.parts
    if not parts:
        return "(root)"
    if len(parts) == 1:
        return relative_path.stem
    if parts[0].lower() in {"src", "app", "lib"} and len(parts) > 1:
        return parts[1]
    return parts[0]


def collect_imports(tree: ast.AST) -> list[str]:
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            base = node.module or ""
            imports.add(prefix + base)
            imports.update(
                prefix + ".".join(part for part in (base, alias.name) if part)
                for alias in node.names
            )
    return sorted(item for item in imports if item)


def analyze_source(path: Path, root: Path, source: str | None = None) -> ModuleInfo:
    relative = path.relative_to(root)
    info = ModuleInfo(
        path=relative.as_posix(),
        module=module_name(path, root),
        feature_group=feature_group(relative),
    )
    try:
        text = source if source is not None else path.read_text(encoding="utf-8-sig")
        tree = ast.parse(text, filename=str(path))
        visitor = SourceAnalyzer()
        visitor.visit(tree)
        info.imports = collect_imports(tree)
        info.symbols = sorted(visitor.symbols, key=lambda item: (item.start_line, item.end_line))
        (
            info.assignments,
            info.module_calls,
            info.control_flow,
            info.execution_items,
        ) = collect_execution_details(tree)
    except (OSError, SyntaxError, UnicodeError) as exc:
        info.error = f"{type(exc).__name__}: {exc}"
    return info


def sanitize_notebook_source(source: str) -> str:
    lines = source.splitlines()
    first_code_line = next((line.strip() for line in lines if line.strip()), "")
    if first_code_line.startswith("%%"):
        if first_code_line.startswith("%%writefile"):
            replaced = False
            sanitized = []
            for line in lines:
                if not replaced and line.strip().startswith("%%writefile"):
                    sanitized.append("# AST skipped writefile directive")
                    replaced = True
                else:
                    sanitized.append(line)
            return "\n".join(sanitized)
        return "\n".join("# AST skipped cell magic" if line.strip() else "" for line in lines)
    return "\n".join(
        "# AST skipped notebook command" if line.lstrip().startswith(("%", "!")) else line
        for line in lines
    )


def analyze_notebook(path: Path, root: Path) -> list[ModuleInfo]:
    relative = path.relative_to(root)
    group = feature_group(relative)
    notebook_module = module_name(path, root)
    try:
        notebook = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [
            ModuleInfo(
                path=relative.as_posix(),
                module=notebook_module,
                feature_group=group,
                error=f"{type(exc).__name__}: {exc}",
            )
        ]

    modules: list[ModuleInfo] = []
    for cell_number, cell in enumerate(notebook.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        raw_source = cell.get("source", "")
        source = "".join(raw_source) if isinstance(raw_source, list) else str(raw_source)
        if not source.strip():
            continue
        cell_path = f"{relative.as_posix()}#cell-{cell_number}"
        info = ModuleInfo(
            path=cell_path,
            module=f"{notebook_module}.cell_{cell_number}",
            feature_group=group,
        )
        try:
            tree = ast.parse(sanitize_notebook_source(source), filename=cell_path)
            visitor = SourceAnalyzer()
            visitor.visit(tree)
            info.imports = collect_imports(tree)
            info.symbols = sorted(visitor.symbols, key=lambda item: (item.start_line, item.end_line))
            (
                info.assignments,
                info.module_calls,
                info.control_flow,
                info.execution_items,
            ) = collect_execution_details(tree)
        except SyntaxError as exc:
            info.error = f"SyntaxError: {exc}"
        modules.append(info)
    if not modules:
        modules.append(
            ModuleInfo(
                path=relative.as_posix(),
                module=notebook_module,
                feature_group=group,
                error="분석할 Python 코드 셀이 없습니다.",
            )
        )
    return modules


def iter_source_files(source: Path) -> Iterable[Path]:
    if source.is_file():
        if source.suffix.lower() in {".py", ".ipynb"}:
            yield source
        return
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".py", ".ipynb"}:
            continue
        if not any(part in IGNORED_DIRS or part.startswith(".venv") for part in path.parts):
            yield path


def analyze_tree(source: Path) -> tuple[Path, list[ModuleInfo]]:
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(
            f"분석 경로가 없습니다: {source}. 원본 .py 또는 .ipynb 파일의 전체 경로를 지정하세요."
        )
    if source.is_file() and source.suffix.lower() not in {".py", ".ipynb"}:
        raise ValueError(f"지원하지 않는 파일 형식입니다: {source.suffix}. .py 또는 .ipynb를 지정하세요.")
    root = source.parent if source.is_file() else source
    modules: list[ModuleInfo] = []
    for path in sorted(iter_source_files(source)):
        if path.suffix.lower() == ".ipynb":
            modules.extend(analyze_notebook(path, root))
        else:
            modules.append(analyze_source(path, root))
    return root, modules


def run_git(repo: Path, arguments: list[str]) -> str:
    command = [
        "git",
        "-c",
        f"safe.directory={repo.as_posix()}",
        "-C",
        str(repo),
        *arguments,
    ]
    result = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git command failed")
    return result.stdout


HUNK_RE = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")


def parse_diff(text: str) -> list[DiffHunk]:
    hunks: list[DiffHunk] = []
    old_path = ""
    new_path = ""
    active: DiffHunk | None = None
    old_line = 0
    new_line = 0

    for line in text.splitlines():
        if line.startswith("--- "):
            value = line[4:]
            old_path = value[2:] if value.startswith("a/") else value
            continue
        if line.startswith("+++ "):
            value = line[4:]
            new_path = value[2:] if value.startswith("b/") else value
            continue
        match = HUNK_RE.match(line)
        if match:
            path = new_path if new_path != "/dev/null" else old_path
            if not path.endswith(".py"):
                active = None
                continue
            old_start, old_count, new_start, new_count = (
                int(match.group(1)),
                int(match.group(2) or 1),
                int(match.group(3)),
                int(match.group(4) or 1),
            )
            active = DiffHunk(path, old_start, old_count, new_start, new_count)
            hunks.append(active)
            old_line = old_start
            new_line = new_start
            continue
        if active is None:
            continue
        if line.startswith("-") and not line.startswith("---"):
            active.old_lines.append(old_line)
            active.removed.append(line[1:])
            old_line += 1
        elif line.startswith("+") and not line.startswith("+++"):
            active.new_lines.append(new_line)
            active.added.append(line[1:])
            new_line += 1
        elif line.startswith(" "):
            old_line += 1
            new_line += 1
    return hunks


def symbol_for_lines(module: ModuleInfo | None, lines: list[int]) -> Symbol | None:
    if module is None or not lines:
        return None
    candidates = [
        symbol
        for symbol in module.symbols
        if any(symbol.start_line <= line <= symbol.end_line for line in lines)
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item.end_line - item.start_line)


def old_module(repo: Path, base: str, path: str) -> ModuleInfo | None:
    try:
        source = run_git(repo, ["show", f"{base}:{path}"])
    except RuntimeError:
        return None
    virtual_path = repo / path
    return analyze_source(virtual_path, repo, source)


def compact(lines: list[str], limit: int = 140) -> str:
    value = " ⏎ ".join(line.strip() for line in lines if line.strip()) or "—"
    value = value.replace("|", "\\|").replace("`", "'")
    return value if len(value) <= limit else value[: limit - 1] + "…"


def import_candidates(module: str) -> set[str]:
    values = {module}
    parts = module.split(".")
    if parts and parts[0] in {"src", "app", "lib"} and len(parts) > 1:
        values.add(".".join(parts[1:]))
    return values


def relation_rows(
    changed_module: ModuleInfo | None,
    changed_symbol: Symbol | None,
    modules: list[ModuleInfo],
) -> list[dict[str, str]]:
    if changed_module is None:
        return []
    changed_candidates = import_candidates(changed_module.module)
    symbol_names = set()
    if changed_symbol:
        symbol_names.update({changed_symbol.name, changed_symbol.qualified_name})
    rows: list[dict[str, str]] = []
    for module in modules:
        if module.path == changed_module.path or module.error:
            continue
        evidence: set[str] = set()
        for imported in module.imports:
            normalized = imported.lstrip(".")
            if any(
                normalized == candidate
                or normalized.startswith(candidate + ".")
                or candidate.startswith(normalized + ".")
                for candidate in changed_candidates
            ):
                evidence.add(f"import:{imported}")
        if symbol_names:
            for symbol in module.symbols:
                for call in symbol.calls:
                    tail = call.split(".")[-1]
                    if tail in symbol_names or call in symbol_names:
                        evidence.add(f"call:{call}")
        if evidence:
            rows.append(
                {
                    "module": module.module,
                    "path": module.path,
                    "feature_group": module.feature_group,
                    "evidence": ", ".join(sorted(evidence)),
                }
            )
    return rows


def build_diff_report(repo: Path, base: str, target: str | None) -> dict:
    repo = repo.resolve()
    comparison = f"{base}...{target}" if target else base
    diff_text = run_git(repo, ["diff", "--find-renames", "--unified=0", comparison])
    hunks = parse_diff(diff_text)
    _, modules = analyze_tree(repo)
    module_by_path = {module.path: module for module in modules}
    changes = []

    for index, hunk in enumerate(hunks, start=1):
        current_module = module_by_path.get(hunk.path)
        symbol = symbol_for_lines(current_module, hunk.new_lines)
        if symbol is None and hunk.old_lines:
            previous_module = old_module(repo, base, hunk.path)
            symbol = symbol_for_lines(previous_module, hunk.old_lines)
        kind = "modified"
        if hunk.added and not hunk.removed:
            kind = "added"
        elif hunk.removed and not hunk.added:
            kind = "removed"
        relations = relation_rows(current_module, symbol, modules)
        groups = sorted(
            {current_module.feature_group if current_module else feature_group(Path(hunk.path))}
            | {row["feature_group"] for row in relations}
        )
        changes.append(
            {
                "change_id": f"CHG-{index:03d}",
                "path": hunk.path,
                "module": current_module.module if current_module else Path(hunk.path).stem,
                "symbol": symbol.qualified_name if symbol else "(module)",
                "symbol_kind": symbol.kind if symbol else "module",
                "change_type": kind,
                "old_value": compact(hunk.removed),
                "new_value": compact(hunk.added),
                "old_range": f"{hunk.old_start}+{hunk.old_count}",
                "new_range": f"{hunk.new_start}+{hunk.new_count}",
                "feature_groups": groups,
                "related_modules": relations,
            }
        )

    return {
        "mode": "diff",
        "repository": str(repo),
        "base": base,
        "target": target or "working-tree",
        "change_count": len(changes),
        "changes": changes,
        "parse_errors": [asdict(module) for module in modules if module.error],
    }


def structure_report(source: Path) -> dict:
    root, modules = analyze_tree(source)
    return {
        "mode": "structure",
        "source": str(source.resolve()),
        "root": str(root),
        "module_count": len(modules),
        "modules": [asdict(module) for module in modules],
    }


def markdown_ast_tree(source: Path) -> str:
    source = source.resolve()
    if not source.exists():
        raise FileNotFoundError(f"분석 경로가 없습니다: {source}")

    root = source.parent if source.is_file() else source
    title = source.stem if source.is_file() else source.name
    lines = [
        f"# {title} AST Tree",
        "",
        f"- 분석 경로: `{source}`",
    ]

    for path in sorted(iter_source_files(source)):
        relative = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".ipynb":
            try:
                notebook = json.loads(path.read_text(encoding="utf-8-sig"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                lines.extend(["", f"## {relative}", "", f"파싱 오류: {type(exc).__name__}: {exc}"])
                continue

            for cell_number, cell in enumerate(notebook.get("cells", []), start=1):
                if cell.get("cell_type") != "code":
                    continue
                raw_source = cell.get("source", "")
                cell_source = "".join(raw_source) if isinstance(raw_source, list) else str(raw_source)
                if not cell_source.strip():
                    continue
                heading = (
                    f"원본 코드 셀 {cell_number}"
                    if source.is_file()
                    else f"{relative} 코드 셀 {cell_number}"
                )
                lines.extend(["", f"## {heading}", "", "```text"])
                try:
                    tree = ast.parse(
                        sanitize_notebook_source(cell_source),
                        filename=f"{relative}#cell-{cell_number}",
                    )
                    lines.append(ast.dump(tree, indent=2))
                except SyntaxError as exc:
                    lines.append(f"SyntaxError: {exc}")
                lines.append("```")
        else:
            heading = "원본 파일" if source.is_file() else relative
            lines.extend(["", f"## {heading}", "", "```text"])
            try:
                tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
                lines.append(ast.dump(tree, indent=2))
            except (OSError, SyntaxError, UnicodeError) as exc:
                lines.append(f"{type(exc).__name__}: {exc}")
            lines.append("```")

    return "\n".join(lines) + "\n"


def markdown_structure(report: dict) -> str:
    lines = [
        "# AST 코드 구조 분석",
        "",
        f"- 분석 경로: `{report['source']}`",
        f"- Python 모듈/노트북 코드 셀: {report['module_count']}개",
        "",
        "| 기능 그룹 | 모듈 | 파일 | 심볼 수 | 실행 요소 | import 수 | 상태 |",
        "|---|---|---|---:|---:|---:|---|",
    ]
    for module in report["modules"]:
        status = module["error"] or "정상"
        lines.append(
            f"| {module['feature_group']} | `{module['module']}` | `{module['path']}` | "
            f"{len(module['symbols'])} | "
            f"{len(module['execution_items'])} | "
            f"{len(module['imports'])} | {status} |"
        )
    for module in report["modules"]:
        lines.extend(["", f"## {module['module']}", ""])
        if module["imports"]:
            lines.append("- imports: " + ", ".join(f"`{item}`" for item in module["imports"]))
        else:
            lines.append("- imports: 없음")
        if module["error"]:
            lines.append(f"- 파싱 오류: {module['error']}")
            continue
        lines.extend(
            [
                "",
                "### 셀·모듈 실행 내용",
                "",
                "| 원본 줄 | 구분 | 코드 요약 |",
                "|---:|---|---|",
            ]
        )
        if not module["execution_items"]:
            lines.append("| — | — | 최상위 실행 코드 없음 |")
        for item in module["execution_items"]:
            kind = item["kind"]
            value = item["value"]
            prefix = "↳ " * int(item["depth"])
            escaped = value.replace("|", "\\|").replace("`", "'")
            lines.append(f"| {item['line']} | {kind} | `{prefix}{escaped}` |")
        lines.extend(["", "| 종류 | 심볼 | 줄 | 호출 대상 |", "|---|---|---:|---|"])
        if not module["symbols"]:
            lines.append("| module | `(정의 없음)` | — | — |")
        for symbol in module["symbols"]:
            calls = ", ".join(f"`{item}`" for item in symbol["calls"]) or "—"
            lines.append(
                f"| {symbol['kind']} | `{symbol['qualified_name']}` | "
                f"{symbol['start_line']}-{symbol['end_line']} | {calls} |"
            )
    return "\n".join(lines) + "\n"


def markdown_diff(report: dict) -> str:
    lines = [
        "# AST 기반 변경 영향 분석",
        "",
        f"- 저장소: `{report['repository']}`",
        f"- 비교: `{report['base']}` → `{report['target']}`",
        f"- 변경 항목: {report['change_count']}개",
        "",
        "## 1. 변경 기준 분석",
        "",
        "| ID | 파일 | 변경 심볼 | 유형 | 이전 값 | 변경 값 | 연관 모듈 |",
        "|---|---|---|---|---|---|---|",
    ]
    if not report["changes"]:
        lines.append("| — | Python 변경 없음 | — | — | — | — | — |")
    for change in report["changes"]:
        related = ", ".join(f"`{item['module']}`" for item in change["related_modules"]) or "—"
        lines.append(
            f"| {change['change_id']} | `{change['path']}` | `{change['symbol']}` | "
            f"{change['change_type']} | {change['old_value']} | {change['new_value']} | {related} |"
        )

    lines.extend(["", "## 2. 기능·모듈별 변경 값", ""])
    grouped: dict[str, list[dict]] = {}
    for change in report["changes"]:
        for group in change["feature_groups"]:
            grouped.setdefault(group, []).append(change)
    if not grouped:
        lines.append("Python 변경 없음")
    for group, changes in sorted(grouped.items()):
        lines.extend(
            [
                f"### 기능 그룹: {group}",
                "",
                "| ID | 모듈 | 변경 심볼 | 이전 값 | 변경 값 | 연결 근거 |",
                "|---|---|---|---|---|---|",
            ]
        )
        for change in changes:
            evidence = ", ".join(
                f"{item['module']}({item['evidence']})" for item in change["related_modules"]
                if item["feature_group"] == group
            ) or "직접 변경"
            evidence = evidence.replace("|", "\\|")
            lines.append(
                f"| {change['change_id']} | `{change['module']}` | `{change['symbol']}` | "
                f"{change['old_value']} | {change['new_value']} | {evidence} |"
            )

    if report["parse_errors"]:
        lines.extend(["", "## 파싱 확인 필요", ""])
        for item in report["parse_errors"]:
            lines.append(f"- `{item['path']}`: {item['error']}")
    return "\n".join(lines) + "\n"


def default_output_path(report: dict, output_format: str) -> Path:
    reports_dir = Path(__file__).resolve().parent / "reports"
    extension = ".json" if output_format == "json" else ".md"
    if report["mode"] == "structure":
        source = Path(report["source"])
        source_name = source.stem if source.is_file() else source.name
        filename = f"{source_name}_ast_structure{extension}"
        reports_dir = reports_dir / "structure"
    else:
        repository_name = Path(report["repository"]).name
        base = re.sub(r"[^0-9A-Za-z._-]+", "_", report["base"])[:24]
        target = re.sub(r"[^0-9A-Za-z._-]+", "_", report["target"])[:24]
        filename = f"{repository_name}_{base}_to_{target}_ast_diff{extension}"
        reports_dir = reports_dir / "diff"
    filename = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", filename)
    return reports_dir / filename


def default_tree_output_path(source: Path) -> Path:
    source = source.resolve()
    source_name = source.stem if source.is_file() else source.name
    filename = re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", f"{source_name}_ast_tree.md")
    return Path(__file__).resolve().parent / "reports" / "tree" / filename


def write_output(report: dict, output_format: str, output: str | None) -> None:
    if output_format == "json":
        rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    elif report["mode"] == "structure":
        rendered = markdown_structure(report)
    else:
        rendered = markdown_diff(report)
    output_path = Path(output).resolve() if output else default_output_path(report, output_format)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"작성 완료: {output_path}")


def write_tree_output(source: Path, output: str | None) -> None:
    output_path = Path(output).resolve() if output else default_tree_output_path(source)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(markdown_ast_tree(source), encoding="utf-8")
    print(f"AST 트리 작성 완료: {output_path}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Python AST 구조·변경 영향 분석과 QA 입력 변환·비교 도구"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    structure = subparsers.add_parser("structure", help="파일 또는 폴더의 코드 구조 분석")
    structure.add_argument("source", help="Python .py/.ipynb 파일 또는 프로젝트 폴더")
    structure.add_argument("--format", choices=("markdown", "json"), default="markdown")
    structure.add_argument("--output", help="가공형 결과 파일 경로")

    tree = subparsers.add_parser("tree", help="파일 또는 폴더의 원본 AST 트리 출력")
    tree.add_argument("source", help="Python .py/.ipynb 파일 또는 프로젝트 폴더")
    tree.add_argument("--output", help="AST 트리형 결과 파일 경로")

    diff = subparsers.add_parser("diff", help="Git diff의 변경 심볼과 연관 모듈 분석")
    diff.add_argument("repository", help="Git 저장소 경로")
    diff.add_argument("--base", default="HEAD", help="기준 ref. 기본값: HEAD")
    diff.add_argument("--target", help="대상 ref. 생략 시 working tree")
    diff.add_argument("--format", choices=("markdown", "json"), default="markdown")
    diff.add_argument("--output", help="결과 파일 경로")

    convert = subparsers.add_parser("convert", help="로컬·Git·엔진·APK·IPA 입력을 비교용 스냅샷으로 준비")
    convert.add_argument("source", help="입력 파일, 프로젝트 또는 Git 저장소 경로")
    convert.add_argument("--kind", choices=("auto", "local", "engine", "git", "apk", "ipa"), default="auto")
    convert.add_argument("--output", help="새로 만들 스냅샷 폴더")
    convert.add_argument("--ref", help="kind=git에서 고정할 브랜치·태그·커밋")
    convert.add_argument("--source-root", default=".", help="저장소 또는 프로젝트 안의 비교 루트")
    convert.add_argument("--jadx", help="APK DEX 복원에 사용할 JADX 실행 파일 또는 CLI JAR")

    compare = subparsers.add_parser("compare", help="Ver.A와 Ver.B의 Python 코드 영향 비교")
    compare.add_argument("base", help="Ver.A 원본 또는 변환 스냅샷")
    compare.add_argument("target", help="Ver.B 원본 또는 변환 스냅샷")
    compare.add_argument("--features", help="기능·TC 매핑 JSON")
    compare.add_argument("--max-depth", type=int, default=10, help="호출·참조 역추적 깊이")
    compare.add_argument("--format", choices=("both", "markdown", "json"), default="both")
    compare.add_argument("--output", help="비교 보고서 경로 또는 확장자 없는 stem")
    return parser


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    try:
        if args.command == "structure":
            report = structure_report(Path(args.source))
            write_output(report, args.format, args.output)
            return 0
        if args.command == "tree":
            write_tree_output(Path(args.source), args.output)
            return 0
        if args.command == "diff":
            report = build_diff_report(Path(args.repository), args.base, args.target)
            write_output(report, args.format, args.output)
            return 0
        if args.command == "convert":
            from artifact_conversion import convert_input

            manifest = convert_input(
                Path(args.source),
                kind=args.kind,
                output=args.output,
                ref=args.ref,
                source_root=args.source_root,
                jadx=args.jadx,
            )
            print(f"입력 스냅샷 작성 완료: {manifest['output_path']}")
            return 2 if manifest.get("status") == "partial" else 0

        from code_comparison import build_comparison, write_comparison

        report = build_comparison(
            Path(args.base),
            Path(args.target),
            features_path=args.features,
            max_depth=args.max_depth,
        )
        write_comparison(report, args.format, args.output)
        return 2 if report.get("status") == "incomplete" else 0
    except (OSError, RuntimeError, ValueError, zipfile.BadZipFile, subprocess.SubprocessError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
