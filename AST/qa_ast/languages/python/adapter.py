"""Translate the existing Python semantic snapshot into the common graph."""

from __future__ import annotations

from pathlib import Path

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
from .relations import build_relations
from .snapshot import CodeSymbol, load_snapshot


class PythonAdapter(LanguageAdapter):
    language_id = "python"
    display_name = "Python"
    extensions = frozenset({".py", ".ipynb"})
    capabilities = AnalysisCapabilities(
        parse=True,
        symbols=True,
        imports=True,
        calls=True,
        references=True,
        value_flow=True,
    )

    def analyze(self, source: Path) -> ProjectGraph:
        snapshot = load_snapshot(Path(source))
        relations = build_relations(snapshot)
        nodes: list[CommonNode] = [
            CommonNode(
                id="project",
                kind=NodeKind.PROJECT,
                name=Path(snapshot.input_path).name,
                qualified_name=snapshot.input_path,
                language="common",
            )
        ]
        edges: list[CommonEdge] = []
        symbol_ids = {legacy_id: f"python:{legacy_id}" for legacy_id in snapshot.symbols}

        for file_key in sorted(snapshot.units):
            file_id = f"file:{file_key}"
            nodes.append(CommonNode(id=file_id, kind=NodeKind.FILE, name=Path(file_key).name,
                                    qualified_name=file_key, file=file_key, language="common"))
            edges.append(CommonEdge(id=f"contains:{file_key}", kind=EdgeKind.CONTAINS,
                                    source="project", target=file_id,
                                    resolution=Resolution.EXACT, confidence=1.0))

        for legacy_id, symbol in sorted(snapshot.symbols.items()):
            nodes.append(_symbol_node(symbol, symbol_ids[legacy_id]))
            parent = _parent_symbol_id(snapshot.symbols, symbol, symbol_ids)
            source_id = parent or f"file:{symbol.file}"
            edges.append(CommonEdge(id=f"declares:{legacy_id}", kind=EdgeKind.DECLARES,
                                    source=source_id, target=symbol_ids[legacy_id],
                                    resolution=Resolution.EXACT, confidence=1.0,
                                    evidence=[_evidence(symbol.file, symbol.start_line, symbol.end_line)]))

        relation_kind = {"call": EdgeKind.CALLS, "reference": EdgeKind.REFERENCES}
        for index, relation in enumerate(relations["edges"], start=1):
            edges.append(CommonEdge(
                id=f"python-relation:{index}",
                kind=relation_kind[relation["kind"]],
                source=symbol_ids[relation["caller"]],
                target=symbol_ids[relation["callee"]],
                resolution=Resolution.STATIC,
                confidence=0.95,
                evidence=[Evidence(
                    file=snapshot.symbols[relation["caller"]].file,
                    parser="python.ast",
                    source_range=SourceRange(relation["line"], relation["line"]),
                    expression=relation["expression"],
                    rule=f"python_{relation['kind']}_resolution",
                )],
            ))

        boundaries = [
            AnalysisBoundary(kind="parse_error", message=item["error"], file=item["path"], language="python")
            for item in snapshot.errors
        ]
        boundaries.extend(
            AnalysisBoundary(
                kind="unresolved_reference",
                message=item["reason"],
                file=snapshot.symbols[item["caller"]].file,
                source_range=SourceRange(item["line"], item["line"]),
                language="python",
            )
            for item in relations["unresolved"]
        )
        return ProjectGraph(
            root=snapshot.input_path,
            languages=[self.language_id],
            nodes=nodes,
            edges=edges,
            boundaries=boundaries,
            metadata={
                "adapter": self.language_id,
                "parser": "python.ast",
                "capabilities": self.capabilities.to_dict(),
                "warnings": snapshot.warnings,
                "external_reference_count": len(relations["external"]),
            },
        )


def _symbol_node(symbol: CodeSymbol, node_id: str) -> CommonNode:
    if symbol.kind == "module":
        kind = NodeKind.MODULE
    elif symbol.kind == "class":
        kind = NodeKind.CLASS
    elif symbol.qualified_name.endswith(".__init__"):
        kind = NodeKind.CONSTRUCTOR
    elif "." in symbol.qualified_name:
        kind = NodeKind.METHOD
    else:
        kind = NodeKind.FUNCTION
    return CommonNode(
        id=node_id,
        kind=kind,
        name=symbol.qualified_name.rsplit(".", 1)[-1],
        qualified_name=symbol.qualified_name,
        file=symbol.file,
        language="python",
        source_range=SourceRange(symbol.start_line, symbol.end_line),
        language_data={"legacy_kind": symbol.kind, "module": symbol.module},
    )


def _parent_symbol_id(symbols: dict[str, CodeSymbol], symbol: CodeSymbol,
                      common_ids: dict[str, str]) -> str | None:
    if symbol.kind == "module":
        return None
    qualified = symbol.qualified_name
    while "." in qualified:
        qualified = qualified.rsplit(".", 1)[0]
        candidate = f"{symbol.file}::{qualified}"
        if candidate in symbols:
            return common_ids[candidate]
    module = f"{symbol.file}::<module>"
    return common_ids.get(module)


def _evidence(file: str, start_line: int, end_line: int) -> Evidence:
    return Evidence(file=file, parser="python.ast",
                    source_range=SourceRange(start_line, end_line),
                    rule="python_declaration")
