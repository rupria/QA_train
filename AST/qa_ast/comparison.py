"""Language-neutral AST comparison and upstream impact candidates."""

from __future__ import annotations

import difflib
import json
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from .common.models import CommonEdge, CommonNode, EdgeKind, NodeKind, ProjectGraph
from .registry import default_registry


_STRUCTURAL_KINDS = {
    NodeKind.MODULE,
    NodeKind.NAMESPACE,
    NodeKind.CLASS,
    NodeKind.INTERFACE,
    NodeKind.ENUM,
    NodeKind.FUNCTION,
    NodeKind.METHOD,
    NodeKind.CONSTRUCTOR,
    NodeKind.PROPERTY,
    NodeKind.FIELD,
    NodeKind.VARIABLE,
    NodeKind.UI_PAGE,
    NodeKind.UI_COMPONENT,
    NodeKind.CONTENT,
    NodeKind.EVENT,
    NodeKind.API,
    NodeKind.CONFIGURATION,
}
_IMPACT_EDGES = {EdgeKind.CALLS, EdgeKind.REFERENCES}


def build_language_comparison(base_path: Path, target_path: Path,
                              language_ids: list[str] | tuple[str, ...],
                              max_depth: int = 10) -> dict:
    """Compare selected non-Python adapters using the common graph contract."""
    if not 1 <= max_depth <= 100:
        raise ValueError("max-depth는 1~100이어야 합니다.")
    languages = sorted({item.strip().lower() for item in language_ids if item.strip()})
    if not languages:
        raise ValueError("비교할 공통 파서 언어가 없습니다.")
    if "python" in languages:
        raise ValueError("Python은 정밀 Python 비교기로 분석해야 합니다.")
    base_path, target_path = Path(base_path).resolve(), Path(target_path).resolve()
    registry = default_registry()
    graph_pairs: dict[str, tuple[ProjectGraph, ProjectGraph]] = {}
    for language in languages:
        adapter = registry.get(language)
        graph_pairs[language] = (adapter.analyze(base_path), adapter.analyze(target_path))

    changes: list[dict] = []
    errors: list[dict] = []
    relations = {"base": _empty_relations(), "target": _empty_relations()}
    warnings: list[str] = []
    base_symbol_count = target_symbol_count = 0
    single_file_pair = base_path.is_file() and target_path.is_file()

    for language, (base_graph, target_graph) in graph_pairs.items():
        errors.extend(_boundary_errors("base", base_graph))
        errors.extend(_boundary_errors("target", target_graph))
        _append_relations(relations["base"], base_graph)
        _append_relations(relations["target"], target_graph)
        base_nodes = _comparable_nodes(base_graph, single_file_pair)
        target_nodes = _comparable_nodes(target_graph, single_file_pair)
        base_symbol_count += len(base_nodes)
        target_symbol_count += len(target_nodes)
        candidate_changes = []
        for key in sorted(set(base_nodes) | set(target_nodes), key=str):
            before, after = base_nodes.get(key), target_nodes.get(key)
            if before and after and _fingerprint(before) == _fingerprint(after):
                continue
            node = after or before
            candidate_changes.append((key, before, after, node))

        # A module fingerprint covers the whole file. Suppress that broad result
        # when a more precise symbol in the same file already explains the change.
        detailed_files = {
            (node.file or "", language)
            for _, before, after, node in candidate_changes
            if node.kind is not NodeKind.MODULE
        }
        for _, before, after, node in candidate_changes:
            if node.kind is NodeKind.MODULE and (node.file or "", language) in detailed_files:
                continue
            change_type = "added" if before is None else "deleted" if after is None else "modified"
            base_data = _node_data(before, base_path)
            target_data = _node_data(after, target_path)
            impacts, truncated = [], []
            for side, graph, changed_node in (
                ("base", base_graph, before), ("target", target_graph, after)
            ):
                if changed_node is None:
                    continue
                side_impacts, cutoff = _upstream(graph, changed_node.id, max_depth)
                impacts.extend(dict(side=side, **item) for item in side_impacts)
                if cutoff:
                    truncated.append(side)
            change_id = f"CODE-{len(changes) + 1:03d}"
            if truncated:
                warnings.append(
                    f"{change_id}: {', '.join(truncated)} 호출 역추적이 깊이 {max_depth}에서 제한됐습니다."
                )
            symbol = node.qualified_name or node.name
            label = f"{node.file or language}::{symbol}"
            changes.append({
                "id": change_id,
                "file": node.file or "",
                "symbol": symbol,
                "kind": node.kind.value,
                "language": language,
                "change_type": change_type,
                "base": base_data,
                "target": target_data,
                "ast_diff": _diff(
                    _ast_summary(before), _ast_summary(after), label + ".ast"
                ),
                "source_diff": _diff(
                    (base_data or {}).get("source", ""),
                    (target_data or {}).get("source", ""), label,
                ),
                "impacts": impacts,
                "features": [],
                "traversal_truncated": truncated,
            })

    changed_files = {item["file"] for item in changes}
    counts = {
        name: sum(item["change_type"] == name for item in changes)
        for name in ("added", "deleted", "modified")
    }
    now = datetime.now(timezone.utc)
    return {
        "mode": "compare",
        "schema_version": 1,
        "run_id": now.strftime("%Y%m%dT%H%M%S%fZ"),
        "created_at": now.isoformat(),
        "base": str(base_path),
        "target": str(target_path),
        "feature_mapping": None,
        "status": "incomplete" if errors else "analyzed",
        "max_depth": max_depth,
        "analysis_engine": "tree-sitter-language-pack",
        "languages": languages,
        "conversion_inputs": {},
        "changes": changes,
        "errors": errors,
        "relations": relations,
        "skipped_files": [],
        "ignored_text_changes": [],
        "summary": {
            **counts,
            "total_changes": len(changes),
            "changed_files": len(changed_files),
            "skipped_files": 0,
            "ignored_text_changes": 0,
            "base_units": 0,
            "target_units": 0,
            "base_symbols": base_symbol_count,
            "target_symbols": target_symbol_count,
            "parse_errors": len(errors),
            "affected_features": 0,
        },
        "warnings": list(dict.fromkeys(warnings)),
        "limitations": [
            "비-Python 언어는 Tree-sitter 구문·심볼·import·호출 후보를 분석합니다. 타입 추론과 값 흐름은 아직 Python 정밀 분석 범위입니다.",
            "동적 호출, 리플렉션, 매크로, 프레임워크 자동 연결은 정적으로 확정할 수 없어 누락되거나 후보로만 표시될 수 있습니다.",
            "비교는 구현 변경 근거를 제공하며 실제 실행 결과나 제품 요구사항 충족을 보장하지 않습니다.",
            "기능명·TC 연결은 현재 Python 정밀 비교의 기능 매핑에서만 지원합니다.",
        ],
    }


def merge_comparison_reports(*reports: dict) -> dict:
    """Merge Python and common-adapter reports into one UI-compatible report."""
    reports = tuple(report for report in reports if report)
    if not reports:
        raise ValueError("병합할 비교 결과가 없습니다.")
    if len(reports) == 1:
        return reports[0]
    merged = dict(reports[0])
    merged["analysis_engine"] = "hybrid-static"
    merged["languages"] = sorted({lang for report in reports for lang in report.get("languages", ["python"] if report.get("analysis_engine") is None else [])})
    merged["changes"] = []
    for report in reports:
        for item in report["changes"]:
            copied = dict(item, id=f"CODE-{len(merged['changes']) + 1:03d}")
            merged["changes"].append(copied)
    merged["errors"] = [item for report in reports for item in report.get("errors", [])]
    merged["warnings"] = list(dict.fromkeys(item for report in reports for item in report.get("warnings", [])))
    merged["limitations"] = list(dict.fromkeys(item for report in reports for item in report.get("limitations", [])))
    merged["skipped_files"] = [item for report in reports for item in report.get("skipped_files", [])]
    merged["ignored_text_changes"] = sorted({item for report in reports for item in report.get("ignored_text_changes", [])})
    merged["relations"] = {side: _empty_relations() for side in ("base", "target")}
    for report in reports:
        for side in ("base", "target"):
            current = report.get("relations", {}).get(side, {})
            for key in ("edges", "unresolved", "external", "limitations"):
                merged["relations"][side][key].extend(current.get(key, []))
    counts = {name: sum(item["change_type"] == name for item in merged["changes"])
              for name in ("added", "deleted", "modified")}
    merged["summary"] = {
        **counts,
        "total_changes": len(merged["changes"]),
        "changed_files": len({item["file"] for item in merged["changes"]}),
        "skipped_files": len(merged["skipped_files"]),
        "ignored_text_changes": len(merged["ignored_text_changes"]),
        "base_units": sum(report.get("summary", {}).get("base_units", 0) for report in reports),
        "target_units": sum(report.get("summary", {}).get("target_units", 0) for report in reports),
        "base_symbols": sum(report.get("summary", {}).get("base_symbols", 0) for report in reports),
        "target_symbols": sum(report.get("summary", {}).get("target_symbols", 0) for report in reports),
        "parse_errors": len(merged["errors"]),
        "affected_features": len({feature["id"] for change in merged["changes"] for feature in change["features"]}),
    }
    merged["status"] = "incomplete" if merged["errors"] else "analyzed"
    return merged


def _comparable_nodes(graph: ProjectGraph, single_file: bool) -> dict[tuple, CommonNode]:
    result = {}
    for node in graph.nodes:
        if node.kind not in _STRUCTURAL_KINDS or node.language_data.get("external"):
            continue
        file_key = "__single__" if single_file else (node.file or "")
        key = (node.language, file_key, node.qualified_name or node.name, node.kind.value)
        result[key] = node
    return result


def _fingerprint(node: CommonNode) -> tuple:
    return (node.kind.value, node.signature, node.language_data.get("ast_fingerprint"))


def _node_data(node: CommonNode | None, root: Path) -> dict | None:
    if node is None:
        return None
    source = _source(node, root)
    return {
        "start_line": node.source_range.start_line if node.source_range else None,
        "end_line": node.source_range.end_line if node.source_range else None,
        "source": source,
        "ast": _ast_summary(node),
    }


def _source(node: CommonNode, root: Path) -> str:
    if not node.file or not node.source_range:
        return ""
    path = root if root.is_file() else root / Path(node.file)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return ""
    lines = text.splitlines(keepends=True)
    return "".join(lines[node.source_range.start_line - 1:node.source_range.end_line])


def _ast_summary(node: CommonNode | None) -> str:
    if node is None:
        return ""
    return json.dumps({
        "kind": node.kind.value,
        "qualified_name": node.qualified_name,
        "signature": node.signature,
        "ast_fingerprint": node.language_data.get("ast_fingerprint"),
    }, ensure_ascii=False, sort_keys=True, indent=2)


def _diff(before: str, after: str, label: str) -> str:
    left = [line if line.endswith("\n") else line + "\n" for line in before.splitlines(keepends=True)]
    right = [line if line.endswith("\n") else line + "\n" for line in after.splitlines(keepends=True)]
    return "".join(difflib.unified_diff(left, right, fromfile=f"base/{label}", tofile=f"target/{label}"))


def _upstream(graph: ProjectGraph, changed_id: str, max_depth: int) -> tuple[list[dict], bool]:
    nodes = {node.id: node for node in graph.nodes}
    reverse: dict[str, list[CommonEdge]] = defaultdict(list)
    for edge in graph.edges:
        if edge.kind in _IMPACT_EDGES:
            reverse[edge.target].append(edge)
    queue = deque([(changed_id, [])])
    seen = {changed_id}
    results, truncated = [], False
    while queue:
        current, chain = queue.popleft()
        node = nodes.get(current)
        if node and not node.language_data.get("external"):
            results.append({
                "symbol_id": current,
                "file": node.file,
                "symbol": node.qualified_name or node.name,
                "kind": node.kind.value,
                "depth": len(chain),
                "evidence_chain": chain,
            })
        if len(chain) >= max_depth:
            truncated = truncated or any(edge.source not in seen for edge in reverse[current])
            continue
        for edge in reverse[current]:
            if edge.source in seen:
                continue
            seen.add(edge.source)
            evidence = edge.evidence[0] if edge.evidence else None
            item = {
                "caller": edge.source,
                "callee": edge.target,
                "line": evidence.source_range.start_line if evidence and evidence.source_range else None,
                "kind": edge.kind.value,
                "expression": evidence.expression if evidence else None,
            }
            queue.append((edge.source, [item, *chain]))
    return results, truncated


def _boundary_errors(side: str, graph: ProjectGraph) -> list[dict]:
    return [{
        "side": side,
        "path": item.file or "",
        "error": item.message,
        "kind": item.kind,
        "language": item.language,
    } for item in graph.boundaries if item.kind in {"parse_error", "parser_unavailable", "parse_diagnostic"}]


def _empty_relations() -> dict:
    return {"edges": [], "unresolved": [], "external": [], "limitations": []}


def _append_relations(target: dict, graph: ProjectGraph) -> None:
    nodes = {node.id: node for node in graph.nodes}
    for edge in graph.edges:
        if edge.kind not in _IMPACT_EDGES:
            continue
        evidence = edge.evidence[0] if edge.evidence else None
        item = {
            "caller": edge.source,
            "callee": edge.target,
            "kind": edge.kind.value.removesuffix("s"),
            "line": evidence.source_range.start_line if evidence and evidence.source_range else None,
            "expression": evidence.expression if evidence else None,
        }
        if nodes.get(edge.target) and nodes[edge.target].language_data.get("external"):
            if edge.resolution.value == "unresolved":
                target["unresolved"].append({**item, "reason": "정적 대상이 하나로 해석되지 않았습니다."})
            else:
                target["external"].append(item)
        else:
            target["edges"].append(item)
