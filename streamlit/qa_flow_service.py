"""Interpret verified comparison inputs without executing analyzed projects."""
from __future__ import annotations

import json
from pathlib import Path

from code_comparison import code_block, comparison_input, table_value
from qa_web_service import _session, _verified


def interpret_prepared(session, base, target, comparison, change_id, max_depth=10):
    from code_flow import interpret_comparison

    session = _session(session)
    if not isinstance(max_depth, int) or isinstance(max_depth, bool) or not 1 <= max_depth <= 30:
        raise ValueError("흐름 추적 깊이는 1~30 사이의 정수여야 합니다.")
    if not isinstance(comparison, dict) or comparison.get("mode") != "compare":
        raise ValueError("먼저 두 원본 Python 입력의 코드 영향 비교를 실행하세요.")
    changes = comparison.get("changes")
    if not isinstance(changes, list) or not isinstance(change_id, str) or not any(
            isinstance(change, dict) and change.get("id") == change_id for change in changes):
        raise ValueError("현재 비교 결과에 있는 변경 지점을 선택하세요.")
    inputs = comparison.get("conversion_inputs")
    if not isinstance(inputs, dict):
        raise ValueError("비교 결과에 검증된 입력 정보가 없습니다. 두 입력 비교를 다시 실행하세요.")
    paths = []
    for side, manifest in (("base", base), ("target", target)):
        stored, output = _verified(manifest)
        if output.parent != session / "snapshots":
            raise ValueError("현재 웹 세션에서 준비한 스냅샷만 해석할 수 있습니다.")
        if (stored.get("representation") != "original_source" or stored.get("status") != "prepared"
                or not stored.get("capabilities", {}).get("python_ast")):
            raise ValueError("흐름 해석에는 준비가 완료된 원본 Python 소스가 필요합니다.")
        provenance = inputs.get(side)
        if not isinstance(provenance, dict):
            raise ValueError("비교 결과의 입력 정보를 확인할 수 없습니다. 두 입력 비교를 다시 실행하세요.")
        recorded = provenance.get("snapshot_path")
        if not isinstance(recorded, str) or Path(recorded).resolve() != output:
            raise ValueError("비교 결과의 입력과 선택한 스냅샷이 다릅니다. 두 입력 비교를 다시 실행하세요.")
        content, _ = comparison_input(output)
        recorded_content = comparison.get(side)
        if not isinstance(recorded_content, str) or Path(recorded_content).resolve() != content.resolve():
            raise ValueError("비교 결과의 소스 경로를 확인할 수 없습니다. 다시 비교하세요.")
        paths.append(output)
    result = interpret_comparison(paths[0], paths[1], comparison, change_id,
                                  max_depth=max_depth, max_nodes=160)
    result["comparison_run_id"] = comparison.get("run_id")
    result["input_ids"] = {"base": base["id"], "target": target["id"]}
    return result


def markdown_interpretation(result):
    root = result["root_symbol"]
    lines = ["# AST 연결·해석", "", f"변경 지점: {table_value(root['file'])} :: {table_value(root['symbol'])}",
             "", "코드에 나타난 정적 연결·값 전달의 해석입니다. 실제 실행 결과나 기능 영향 확정이 아닙니다.", ""]
    for side, label in (("base", "Ver.A"), ("target", "Ver.B")):
        graph = result["versions"][side]
        names = {node["id"]: node["label"] for node in graph["nodes"]}
        lines += [f"## {label}", "", "| 출발 | 도착 | 연결 | 근거 | 해석 |", "|---|---|---|---|---|"]
        for edge in graph["edges"]:
            values = [names.get(edge["source"], edge["source"]), names.get(edge["target"], edge["target"]),
                      edge["kind"], f"{edge['file']}:{edge['line']}", edge["interpretation"]]
            lines.append("| " + " | ".join(table_value(value) for value in values) + " |")
        if graph["unresolved"]:
            lines += ["", "### 추적이 멈춘 부분", "", code_block(json.dumps(graph["unresolved"], ensure_ascii=False, indent=2), "json")]
    lines += ["", "## 기능·TC 매핑", "", code_block(json.dumps(result.get("features", []), ensure_ascii=False, indent=2), "json"),
              "", "## 연결 차이", "", code_block(json.dumps(result["connection_changes"], ensure_ascii=False, indent=2), "json"),
              "", "## 확인 사항", ""]
    lines.extend(f"- {text}" for text in [*result.get("warnings", []), *result.get("limitations", [])])
    return "\n".join(lines) + "\n"
