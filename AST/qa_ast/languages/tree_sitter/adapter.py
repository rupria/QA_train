"""Generic Tree-sitter adapter emitting the QA Train common graph."""

from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path
from typing import Any

from ...common.adapter import LanguageAdapter
from ...common.capabilities import AnalysisCapabilities
from ...common.models import (
    AnalysisBoundary,
    CommonEdge,
    CommonNode,
    EdgeKind,
    Evidence,
    NodeKind,
    ProjectGraph,
    Resolution,
    SourceRange,
)
from .catalog import TreeSitterSpec


MAX_SOURCE_BYTES = 4 * 1024 * 1024
PARSE_TIMEOUT_MS = 5_000
IGNORED_DIRS = frozenset({
    ".git", ".venv", ".venv-ast", "__pycache__", ".pytest_cache",
    ".mypy_cache", ".ruff_cache", "node_modules", "build", "dist",
})
CALL_NODE_TYPES = frozenset({
    "call", "call_expression", "function_call", "function_call_expression",
    "invocation_expression", "method_invocation", "method_call", "command",
    "remote_call", "apply_expression", "application_expression",
})
CALLEE_FIELDS = ("function", "name", "method", "method_name", "function_name", "selector")


class TreeSitterAdapter(LanguageAdapter):
    capabilities = AnalysisCapabilities(
        parse=True,
        symbols=True,
        imports=True,
        calls=True,
        references=False,
        value_flow=False,
    )

    def __init__(self, spec: TreeSitterSpec, backend: Any | None = None) -> None:
        self.spec = spec
        self.language_id = spec.language_id
        self.display_name = spec.display_name
        self.extensions = spec.extensions
        self._backend = backend

    def supports_file(self, path: Path) -> bool:
        path = Path(path)
        if self.spec.grammar_for(path) is None:
            return False
        # .m is shared by Objective-C and MATLAB/Octave. Do not feed ordinary
        # matrix scripts to the Objective-C grammar based on the suffix alone.
        if self.language_id in {"objective_c", "matlab"} and path.suffix.lower() == ".m" and path.is_file():
            try:
                sample = path.read_bytes()[:16 * 1024].decode("utf-8-sig", "ignore")
            except OSError:
                return False
            objective_c = bool(re.search(
                r"(?m)^\s*(?:#\s*import\b|@(?:interface|implementation|protocol|property|autoreleasepool|end)\b)",
                sample,
            ))
            return objective_c if self.language_id == "objective_c" else not objective_c
        return True

    def analyze(self, source: Path) -> ProjectGraph:
        source = Path(source).resolve()
        if not source.exists():
            raise FileNotFoundError(f"source root does not exist: {source}")
        backend = self._backend or _load_backend()
        project_id = f"project:{self.language_id}"
        nodes = [CommonNode(
            id=project_id,
            kind=NodeKind.PROJECT,
            name=source.name,
            qualified_name=str(source),
            language="common",
        )]
        edges: list[CommonEdge] = []
        boundaries: list[AnalysisBoundary] = []
        parsed_files = 0
        for path in self._source_files(source):
            grammar = self.spec.grammar_for(path)
            if grammar is None:
                continue
            relative = path.name if source.is_file() else path.relative_to(source).as_posix()
            file_id = f"file:{self.language_id}:{relative}"
            module_id = f"{self.language_id}:{relative}::<module>"
            nodes.append(CommonNode(id=file_id, kind=NodeKind.FILE, name=path.name,
                                    qualified_name=relative, file=relative, language="common"))
            edges.append(CommonEdge(id=f"contains:{self.language_id}:{relative}", kind=EdgeKind.CONTAINS,
                                    source=project_id, target=file_id,
                                    resolution=Resolution.EXACT, confidence=1.0))
            try:
                raw = path.read_bytes()
                if len(raw) > MAX_SOURCE_BYTES:
                    raise ValueError(f"source exceeds {MAX_SOURCE_BYTES} bytes")
                text = raw.decode("utf-8-sig")
                result = backend.process(text, backend.ProcessConfig(
                    language=grammar,
                    structure=True,
                    imports=True,
                    exports=True,
                    symbols=True,
                    diagnostics=True,
                    max_source_bytes=MAX_SOURCE_BYTES,
                    parse_timeout_ms=PARSE_TIMEOUT_MS,
                ))
                parser = backend.get_parser(grammar)
                # ProcessConfig parses decoded text, so remove a possible UTF-8
                # BOM before raw byte offsets are used for spans/fingerprints.
                parse_bytes = text.encode("utf-8")
                tree = parser.parse(parse_bytes)
                if tree is None:
                    raise ValueError("parser returned no syntax tree")
            except Exception as exc:
                boundaries.append(AnalysisBoundary(
                    kind="parser_unavailable" if exc.__class__.__name__.endswith(("DownloadError", "LanguageNotFoundError")) else "parse_error",
                    message=str(exc), file=relative, language=self.language_id,
                ))
                continue
            parsed_files += 1
            module_node = CommonNode(
                id=module_id,
                kind=NodeKind.MODULE,
                name=relative,
                qualified_name=relative,
                file=relative,
                language=self.language_id,
                source_range=SourceRange(1, max(1, int(result.metrics.total_lines))),
                language_data={
                    "grammar": grammar,
                    "ast_fingerprint": _ast_fingerprint(tree.root_node, parse_bytes),
                    "node_count": int(result.metrics.node_count),
                    "error_count": int(result.metrics.error_count),
                },
            )
            nodes.append(module_node)
            edges.append(CommonEdge(id=f"declares:{module_id}", kind=EdgeKind.DECLARES,
                                    source=file_id, target=module_id,
                                    resolution=Resolution.EXACT, confidence=1.0,
                                    evidence=[_evidence(relative, grammar, module_node.source_range, "module")]))

            structures: list[tuple[int, int, str, str]] = []
            used_ids: dict[str, int] = {}
            for item in result.structure:
                _add_structure(item, parent_id=module_id, parent_name="", relative=relative,
                               grammar=grammar, raw=parse_bytes, tree=tree, nodes=nodes, edges=edges,
                               structures=structures, used_ids=used_ids, language_id=self.language_id)
            known_spans = {(start, end, name) for start, end, _, name in structures}
            for symbol in result.symbols:
                span = symbol.span
                if (span.start_byte, span.end_byte, symbol.name) in known_spans:
                    continue
                _add_symbol(symbol, module_id, relative, grammar, parse_bytes, tree, nodes, edges,
                            structures, used_ids, self.language_id)
            _add_imports(result.imports, module_id, relative, grammar, nodes, edges, self.language_id)
            _add_calls(tree.root_node, parse_bytes, module_id, relative, grammar, nodes, edges,
                       boundaries, structures, self.language_id)
            for diagnostic in result.diagnostics:
                span = getattr(diagnostic, "span", None)
                boundaries.append(AnalysisBoundary(
                    kind="parse_diagnostic",
                    message=str(getattr(diagnostic, "message", diagnostic)),
                    file=relative,
                    source_range=_range(span) if span else None,
                    language=self.language_id,
                ))
            if tree.root_node.has_error and not result.diagnostics:
                boundaries.append(AnalysisBoundary(
                    kind="parse_diagnostic", message="syntax tree contains error nodes",
                    file=relative, language=self.language_id,
                ))
        return ProjectGraph(
            root=str(source),
            languages=[self.language_id],
            nodes=nodes,
            edges=edges,
            boundaries=boundaries,
            metadata={
                "adapter": self.language_id,
                "parser": "tree-sitter-language-pack",
                "capabilities": self.capabilities.to_dict(),
                "parsed_files": parsed_files,
            },
        )

    def _source_files(self, root: Path):
        if root.is_file():
            if self.supports_file(root):
                yield root
            return
        for directory, dirs, names in os.walk(root, followlinks=False):
            dirs[:] = sorted(name for name in dirs if name not in IGNORED_DIRS and not name.startswith(".venv"))
            for name in sorted(names):
                path = Path(directory) / name
                if self.supports_file(path):
                    yield path


def _load_backend():
    import tree_sitter_language_pack
    return tree_sitter_language_pack


def _add_structure(item, *, parent_id: str, parent_name: str, relative: str,
                   grammar: str, raw: bytes, tree, nodes: list[CommonNode],
                   edges: list[CommonEdge], structures: list[tuple[int, int, str, str]],
                   used_ids: dict[str, int], language_id: str) -> None:
    qualified = f"{parent_name}.{item.name}" if parent_name else item.name
    node_id = _unique_id(f"{language_id}:{relative}::{qualified}", used_ids)
    source_range = _range(item.span)
    common = CommonNode(
        id=node_id,
        kind=_node_kind(item.kind),
        name=item.name,
        qualified_name=qualified,
        file=relative,
        language=language_id,
        source_range=source_range,
        signature=item.signature,
        visibility=item.visibility,
        language_data={
            "grammar": grammar,
            "structure_kind": _kind_name(item.kind),
            "ast_fingerprint": _fingerprint_for_span(tree.root_node, raw, item.span.start_byte, item.span.end_byte),
            "start_byte": item.span.start_byte,
            "end_byte": item.span.end_byte,
        },
    )
    nodes.append(common)
    structures.append((item.span.start_byte, item.span.end_byte, node_id, item.name))
    edges.append(CommonEdge(id=f"declares:{node_id}", kind=EdgeKind.DECLARES,
                            source=parent_id, target=node_id,
                            resolution=Resolution.EXACT, confidence=1.0,
                            evidence=[_evidence(relative, grammar, source_range, "structure")]))
    for child in item.children:
        _add_structure(child, parent_id=node_id, parent_name=qualified, relative=relative,
                       grammar=grammar, raw=raw, tree=tree, nodes=nodes, edges=edges,
                       structures=structures, used_ids=used_ids, language_id=language_id)


def _add_symbol(symbol, module_id: str, relative: str, grammar: str, raw: bytes, tree,
                nodes: list[CommonNode], edges: list[CommonEdge],
                structures: list[tuple[int, int, str, str]], used_ids: dict[str, int],
                language_id: str) -> None:
    node_id = _unique_id(f"{language_id}:{relative}::{symbol.name}", used_ids)
    source_range = _range(symbol.span)
    nodes.append(CommonNode(
        id=node_id, kind=_node_kind(symbol.kind), name=symbol.name,
        qualified_name=symbol.name, file=relative, language=language_id,
        source_range=source_range, signature=getattr(symbol, "type_annotation", None),
        language_data={
            "grammar": grammar,
            "symbol_kind": _kind_name(symbol.kind),
            "ast_fingerprint": _fingerprint_for_span(tree.root_node, raw, symbol.span.start_byte, symbol.span.end_byte),
            "start_byte": symbol.span.start_byte,
            "end_byte": symbol.span.end_byte,
        },
    ))
    structures.append((symbol.span.start_byte, symbol.span.end_byte, node_id, symbol.name))
    edges.append(CommonEdge(id=f"declares:{node_id}", kind=EdgeKind.DECLARES,
                            source=module_id, target=node_id,
                            resolution=Resolution.EXACT, confidence=0.9,
                            evidence=[_evidence(relative, grammar, source_range, "symbol")]))


def _add_imports(imports, module_id: str, relative: str, grammar: str,
                 nodes: list[CommonNode], edges: list[CommonEdge], language_id: str) -> None:
    known = {node.id for node in nodes}
    for index, item in enumerate(imports, start=1):
        target_name = _import_target(item.source)
        digest = hashlib.sha256(target_name.encode()).hexdigest()[:16]
        target_id = f"external:{language_id}:{digest}"
        if target_id not in known:
            nodes.append(CommonNode(id=target_id, kind=NodeKind.MODULE, name=target_name,
                                    qualified_name=target_name, language=language_id,
                                    language_data={"external": True}))
            known.add(target_id)
        edges.append(CommonEdge(
            id=f"import:{language_id}:{relative}:{index}", kind=EdgeKind.IMPORTS,
            source=module_id, target=target_id,
            resolution=Resolution.STATIC, confidence=0.8,
            evidence=[Evidence(file=relative, parser=f"tree-sitter:{grammar}",
                               source_range=_range(item.span), expression=item.source,
                               rule="tree_sitter_import")],
        ))


def _add_calls(root, raw: bytes, module_id: str, relative: str, grammar: str,
               nodes: list[CommonNode], edges: list[CommonEdge],
               boundaries: list[AnalysisBoundary], structures: list[tuple[int, int, str, str]],
               language_id: str) -> None:
    by_name: dict[str, list[str]] = {}
    for _, _, node_id, name in structures:
        by_name.setdefault(name, []).append(node_id)
    known = {node.id for node in nodes}
    counter = 0
    for call in _walk(root):
        if call.type not in CALL_NODE_TYPES:
            continue
        callee = next((call.child_by_field_name(field) for field in CALLEE_FIELDS
                       if call.child_by_field_name(field) is not None), None)
        callee = callee or (call.named_children[0] if call.named_children else None)
        if callee is None:
            continue
        expression = raw[callee.start_byte:callee.end_byte].decode("utf-8", "replace")[:500]
        names = re.findall(r"[A-Za-z_$][\w$]*", expression)
        if not names:
            continue
        name = names[-1]
        owner = _owner(structures, call.start_byte, call.end_byte) or module_id
        candidates = by_name.get(name, [])
        if len(candidates) == 1:
            target_id, resolution, confidence = candidates[0], Resolution.STATIC, 0.75
        else:
            digest = hashlib.sha256(f"{relative}:{expression}".encode()).hexdigest()[:16]
            target_id, resolution, confidence = f"external-call:{language_id}:{digest}", Resolution.UNRESOLVED, 0.35
            if target_id not in known:
                nodes.append(CommonNode(id=target_id, kind=NodeKind.FUNCTION, name=name,
                                        qualified_name=expression, language=language_id,
                                        language_data={"external": True, "call_expression": expression}))
                known.add(target_id)
            boundaries.append(AnalysisBoundary(
                kind="unresolved_call",
                message=f"call target could not be resolved uniquely: {expression}",
                file=relative,
                source_range=SourceRange(call.start_point.row + 1, call.end_point.row + 1),
                language=language_id,
            ))
        counter += 1
        edges.append(CommonEdge(
            id=f"call:{language_id}:{relative}:{counter}", kind=EdgeKind.CALLS,
            source=owner, target=target_id, resolution=resolution, confidence=confidence,
            evidence=[Evidence(
                file=relative, parser=f"tree-sitter:{grammar}",
                source_range=SourceRange(call.start_point.row + 1, call.end_point.row + 1),
                expression=expression, rule="tree_sitter_call_candidate",
            )],
        ))


def _owner(structures: list[tuple[int, int, str, str]], start: int, end: int) -> str | None:
    candidates = [(right - left, node_id) for left, right, node_id, _ in structures
                  if left <= start and end <= right]
    return min(candidates)[1] if candidates else None


def _walk(node):
    stack = [node]
    while stack:
        current = stack.pop()
        yield current
        stack.extend(reversed(current.children))


def _fingerprint_for_span(root, raw: bytes, start: int, end: int) -> str:
    node = root.descendant_for_byte_range(start, max(start, end - 1))
    while node.parent is not None and node.parent.start_byte >= start and node.parent.end_byte <= end:
        node = node.parent
    return _ast_fingerprint(node, raw)


def _ast_fingerprint(node, raw: bytes) -> str:
    digest = hashlib.sha256()
    stack = [(node, False)]
    while stack:
        current, closing = stack.pop()
        if "comment" in current.type:
            continue
        if closing:
            digest.update(b")")
            continue
        digest.update(b"(")
        digest.update(current.type.encode("utf-8", "replace"))
        if current.child_count == 0:
            digest.update(b":")
            digest.update(raw[current.start_byte:current.end_byte].strip())
            digest.update(b")")
            continue
        stack.append((current, True))
        stack.extend((child, False) for child in reversed(current.children))
    return digest.hexdigest()


def _node_kind(value) -> NodeKind:
    name = _kind_name(value)
    return {
        "class": NodeKind.CLASS, "interface": NodeKind.INTERFACE, "enum": NodeKind.ENUM,
        "struct": NodeKind.CLASS, "record": NodeKind.CLASS, "trait": NodeKind.INTERFACE,
        "type": NodeKind.CLASS,
        "function": NodeKind.FUNCTION, "method": NodeKind.METHOD,
        "constructor": NodeKind.CONSTRUCTOR, "property": NodeKind.PROPERTY,
        "field": NodeKind.FIELD, "variable": NodeKind.VARIABLE, "constant": NodeKind.VARIABLE,
        "namespace": NodeKind.NAMESPACE, "module": NodeKind.MODULE,
    }.get(name, NodeKind.CONTENT)


def _kind_name(value) -> str:
    return str(getattr(value, "name", value)).rsplit(".", 1)[-1].lower()


def _range(span) -> SourceRange:
    return SourceRange(span.start_line + 1, max(span.start_line + 1, span.end_line + 1),
                       span.start_column, span.end_column)


def _evidence(file: str, grammar: str, source_range: SourceRange | None, rule: str) -> Evidence:
    return Evidence(file=file, parser=f"tree-sitter:{grammar}",
                    source_range=source_range, rule=f"tree_sitter_{rule}")


def _unique_id(base: str, used: dict[str, int]) -> str:
    used[base] = used.get(base, 0) + 1
    return base if used[base] == 1 else f"{base}#{used[base]}"


def _import_target(source: str) -> str:
    quoted = re.findall(r"['\"]([^'\"]+)['\"]", source)
    if quoted:
        return quoted[-1]
    words = re.findall(r"[A-Za-z_$][\w$.:/-]*", source)
    ignored = {"import", "from", "use", "using", "require", "include", "package"}
    return next((word for word in words if word.casefold() not in ignored), source.strip()[:200] or "unknown")
