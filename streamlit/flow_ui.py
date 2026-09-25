"""Native Streamlit views for grounded AST connections and value flow."""
from __future__ import annotations

import json
from collections import defaultdict, deque

import streamlit as st

from qa_flow_service import interpret_prepared, markdown_interpretation


KINDS = {
    "call": "호출", "reference": "참조", "value_argument": "값 → 인자",
    "parameter_binding": "인자 → 매개변수", "attribute_write": "속성 쓰기",
    "subscript_write": "첨자 쓰기", "return": "반환", "assignment": "변수 대입",
    "call_result": "호출 결과", "condition": "조건 사용", "external_boundary": "외부 호출 경계",
    "scope_parameter": "변경 범위의 입력", "expression": "표현식 의존",
    "access_input": "접근 대상·첨자 의존", "state_write_index": "쓰기 위치 의존",
}
RELATIONSHIPS = {"call", "reference"}


def value_paths(result, side):
    graph = result["versions"][side]
    nodes = {node["id"]: node for node in graph["nodes"]}
    outgoing = defaultdict(list)
    for edge in graph["edges"]:
        if edge["kind"] not in RELATIONSHIPS:
            outgoing[edge["source"]].append(edge)
    root = result["root_symbol"]
    starts = [node["id"] for node in graph["nodes"] if node["kind"] == "symbol"
              and node["file"] == root["file"] and node["symbol"] == root["symbol"]]
    queue = deque((identity, []) for identity in starts)
    seen, paths = set(starts), []
    while queue and len(paths) < 8:
        identity, path = queue.popleft()
        if len(path) >= 24:
            continue
        for edge in outgoing[identity]:
            target = edge["target"]
            if target in seen or target not in nodes:
                continue
            seen.add(target)
            chain = [*path, edge]
            node = nodes[target]
            if (node["kind"] in {"attribute_write", "subscript_write", "condition", "external_call"}
                    or node["kind"] == "return" and not outgoing[target]):
                paths.append(chain)
            queue.append((target, chain))
    return paths[:8], nodes


def render_paths(result, side):
    paths, nodes = value_paths(result, side)
    if not paths:
        return
    st.subheader("값이 연결되는 지점")
    st.caption("확인한 연결 중 대표 경로를 최대 8개·24단계까지 표시합니다. 모든 실행 경로나 실제 기능 결과를 뜻하지 않습니다.")
    for path in paths:
        last = path[-1]
        node = nodes[last["target"]]
        identities = [path[0]["source"], *(edge["target"] for edge in path)]
        labels = [nodes[identity]["label"] if nodes[identity]["kind"] == "symbol"
                  else f"{nodes[identity]['symbol']}: {nodes[identity]['label']}" for identity in identities]
        with st.expander(f"{node['symbol']} · {node['label']}"):
            st.write(" → ".join(labels))
            st.write(f"변경 지점의 값 의존이 {node['symbol']}의 {node['label']}까지 연결되는 후보입니다.")
            st.caption(f"도착 근거 · {last['file']}:{last['line']}")
            st.code(last["expression"], language="python", wrap_lines=True)
            st.write(last["interpretation"])


def edge_rows(graph, edges=None):
    names = {node["id"]: node["label"] for node in graph["nodes"]}
    return [{"출발": names.get(edge["source"], edge["source"]),
             "도착": names.get(edge["target"], edge["target"]),
             "연결": KINDS.get(edge["kind"], edge["kind"]),
             "코드 위치": f"{edge['file']}:{edge['line']}", "해석": edge["interpretation"]}
            for edge in (graph["edges"] if edges is None else edges)]


def graph_spec(graph, relationships):
    edges = [edge for edge in graph["edges"] if relationships or edge["kind"] not in RELATIONSHIPS]
    linked = {value for edge in edges for value in (edge["source"], edge["target"])}
    nodes = [node for node in graph["nodes"] if node["id"] in linked]
    kinds = list(dict.fromkeys(node["kind"] for node in nodes))
    return {
        "animation": False,
        "tooltip": {"trigger": "item", "renderMode": "richText", "formatter": "{b}"},
        "aria": {"enabled": True},
        "series": [{"type": "graph", "layout": "force", "roam": True,
                    "categories": [{"name": kind} for kind in kinds],
                    "data": [{"id": node["id"], "name": node["label"], "category": kinds.index(node["kind"]),
                              "symbolSize": 26, "label": {"show": True, "width": 130, "overflow": "truncate"}}
                             for node in nodes],
                    "links": [{"source": edge["source"], "target": edge["target"],
                               "name": edge["interpretation"], "value": KINDS.get(edge["kind"], edge["kind"]),
                               "lineStyle": {"type": "dashed" if edge["kind"] in RELATIONSHIPS else "solid"}}
                              for edge in edges],
                    "edgeSymbol": ["none", "arrow"], "edgeSymbolSize": 7,
                    "force": {"repulsion": 280, "edgeLength": [100, 180], "gravity": 0.08},
                    "lineStyle": {"opacity": 0.6, "curveness": 0.12},
                    "emphasis": {"focus": "adjacency"}}],
    }


def render_feature_links(result):
    st.subheader("기능까지 연결된 범위")
    features = result.get("features", [])
    if not features:
        st.info("연결된 기능 매핑이 없습니다. 기능 진입점과 TC를 매핑하면 코드 경로와 함께 확인할 수 있습니다.")
        return
    rows = []
    for feature in features:
        evidence = feature.get("flow_evidence", [])
        for side, label in (("base", "Ver.A"), ("target", "Ver.B")):
            matching = [item for item in evidence if item["side"] == side]
            if not matching:
                continue
            rows.append({"버전": label, "기능": feature["name"],
                         "코드 연결": ", ".join(item["symbol_id"] for item in matching),
                         "값 흐름": "해당 코드 범위에 도달" if any(item.get("value_flow_reached") for item in matching) else "호출·참조 관계로 연결",
                         "TC 후보": ", ".join(feature["tc_ids"]) or "미지정", "실행 결과": "미실행"})
    if rows:
        st.dataframe(rows, hide_index=True, width="stretch")
    else:
        st.dataframe([{"기능": item["name"], "TC 후보": ", ".join(item["tc_ids"]), "근거": "기존 호출·참조 매핑"} for item in features], hide_index=True, width="stretch")
    st.caption("값이 해당 함수·모듈 범위에 도달한 근거와 기능 진입점 매핑을 함께 표시합니다. 화면 표시·저장 성공·실제 기능 영향은 확정하지 않습니다.")


def render_version(result, side, relationships):
    graph = result["versions"][side]
    label = "Ver.A" if side == "base" else "Ver.B"
    if graph.get("root_present") is False:
        st.info(f"{label}에는 이 심볼이 없습니다. 추가·삭제 여부를 다른 버전과 함께 확인하세요.")
        return
    render_paths(result, side)
    edges = [edge for edge in graph["edges"] if relationships or edge["kind"] not in RELATIONSHIPS]
    if edges:
        st.echarts_chart(graph_spec(graph, relationships), height=480, key=f"flow_graph_{result['run_id']}_{side}")
        st.caption("화살표는 표에 표시한 연결 방향입니다. 그래프를 끌어 이동하거나 확대하고, 코드 근거는 아래에서 확인하세요.")
        st.dataframe(edge_rows(graph, edges), hide_index=True, width="stretch")
        selected = st.selectbox("연결 상세", range(len(edges)), format_func=lambda index: f"{edges[index]['file']}:{edges[index]['line']} · {KINDS.get(edges[index]['kind'], edges[index]['kind'])}", key=f"flow_edge_{result['run_id']}_{side}")
        edge = edges[selected]
        with st.container(border=True):
            st.write(edge["interpretation"])
            st.caption(f"{edge['file']}:{edge['line']} · {edge['symbol']}")
            st.code(edge["expression"], language="python", wrap_lines=True)
    else:
        st.info("표시할 직접 값 전달 연결이 없습니다. 호출·참조 관계를 켜거나 추적이 멈춘 부분을 확인하세요.")
    if graph.get("truncated"):
        st.warning("깊이 또는 노드 수 제한에 도달했습니다. 표시된 범위 밖의 흐름은 추가 확인이 필요합니다.")
    with st.expander(f"{label} · 추적이 멈춘 부분 ({len(graph['unresolved'])})"):
        if graph["unresolved"]:
            st.dataframe(graph["unresolved"], hide_index=True, width="stretch")
        else:
            st.caption("분석한 범위에 기록된 미해결 항목이 없습니다. 모든 실행 경로를 추적했다는 뜻은 아닙니다.")


def render_changes(result):
    changes = result["connection_changes"]
    for column, kind, label in zip(st.columns(3), ("added", "deleted", "unchanged"), ("Ver.B에 추가", "Ver.B에서 삭제", "공통 연결")):
        column.metric(label, len(changes[kind]))
    for kind, title, side in (("added", "추가된 연결", "target"), ("deleted", "삭제된 연결", "base")):
        st.subheader(title)
        if changes[kind]:
            st.dataframe(edge_rows(result["versions"][side], changes[kind]), hide_index=True, width="stretch")
        else:
            st.caption("없음")
    st.caption("선택한 변경 심볼에서 해석한 연결의 차이입니다. 코드 변경이 있어도 연결 구조는 같을 수 있습니다.")


def flow_view():
    st.subheader("AST 연결·해석")
    st.caption("변경 지점에서 값이 전달되는 코드와 연결된 기능을 코드 근거로 확인합니다.")
    pair = st.session_state.get("pair_analysis")
    if not pair:
        st.info("비교 탭에서 두 입력의 코드 영향 비교를 먼저 실행하세요.")
        return
    if pair["signature"] != st.session_state.get("current_pair_signature", pair["signature"]):
        st.warning("비교 입력 또는 설정이 바뀌었습니다. 두 입력 비교를 다시 실행한 뒤 해석하세요.")
        return
    comparison = pair["report"]
    if comparison.get("mode") != "compare":
        st.info("AST 연결·해석은 원본 Python 코드 영향 비교에서 사용할 수 있습니다. APK·IPA와 파일 구성 결과는 값 흐름을 해석하지 않습니다.")
        return
    if not comparison["changes"]:
        st.info("해석할 AST 변경 지점이 없습니다.")
        return
    by_id = {change["id"]: change for change in comparison["changes"]}
    if st.session_state.get("flow_change") not in by_id:
        st.session_state.flow_change = next(iter(by_id))
    change_id = st.selectbox("해석할 변경 지점", list(by_id), format_func=lambda value: f"{by_id[value]['file']} :: {by_id[value]['symbol']} · {value}", key="flow_change", persist_state="session")
    depth = st.slider("흐름 추적 깊이", 1, 30, 10, key="flow_depth", persist_state="session")
    signature = (comparison["run_id"], change_id, depth)
    if st.button("흐름 해석", type="primary", icon=":material/account_tree:", key="interpret_flow"):
        st.session_state.flow_result = None
        try:
            with st.spinner("두 버전의 코드 연결과 값 전달을 해석하고 있습니다."):
                result = interpret_prepared(st.session_state.work_session, pair["base"]["manifest"], pair["target"]["manifest"], comparison, change_id, max_depth=depth)
            st.session_state.flow_result = {"signature": signature, "interpretation": result}
        except (ValueError, OSError, RuntimeError, RecursionError) as error:
            st.error(f"흐름을 해석하지 못했습니다: {error}")
    ready = st.session_state.get("flow_result")
    if ready and ready["signature"] != signature:
        st.info("변경 지점 또는 깊이가 바뀌었습니다. 흐름 해석을 다시 실행하세요.")
        return
    if not ready:
        return
    result = ready["interpretation"]
    st.success("코드 연결·값 흐름 해석 완료")
    st.caption("정적 분석 후보입니다. 분석 대상 코드를 실행하거나 LLM으로 해석하지 않습니다.")
    render_feature_links(result)
    version = st.segmented_control("흐름 보기", ["Ver.A", "Ver.B", "연결 차이"], default="Ver.B", required=True, key="flow_version", persist_state="session")
    relationships = st.toggle("호출·참조 관계도 함께 표시", key="flow_relationships", persist_state="session")
    if version == "연결 차이":
        render_changes(result)
    else:
        render_version(result, "base" if version == "Ver.A" else "target", relationships)
    with st.container(horizontal=True):
        st.download_button("흐름 해석 JSON", json.dumps(result, ensure_ascii=False, indent=2), file_name="flow.json", mime="application/json", on_click="ignore", key="flow_json")
        st.download_button("흐름 해석 Markdown", markdown_interpretation(result), file_name="flow.md", mime="text/markdown", on_click="ignore", key="flow_md")
    with st.expander("해석 범위·확인 사항"):
        for message in [*result.get("warnings", []), *result.get("limitations", [])]:
            st.write(message)
