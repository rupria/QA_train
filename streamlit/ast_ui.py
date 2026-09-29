"""Single-input AST page, independent of comparison and flow interpretation."""
from __future__ import annotations

import streamlit as st

from qa_ast_service import analyze_prepared


FILE_TYPES = {
    "source_code": "소스 코드", "configuration": "설정 파일",
    "asset_or_data": "데이터·리소스", "scene_or_component_asset": "씬·컴포넌트 리소스",
    "asset_metadata": "리소스 메타데이터", "native_binary": "네이티브 바이너리",
    "native_binary_candidate": "네이티브 바이너리 후보", "assembly_candidate": "어셈블리 후보",
}


def ast_view(input_side, prepare_side, input_signature):
    st.caption("소스 하나 또는 Git 커밋 하나를 선택해 AST를 생성하세요.")
    spec = input_side("ast", "분석 입력", ast_only=True)
    signature = input_signature(spec)
    if st.button("AST 생성", type="primary", icon=":material/account_tree:",
                 key="run_ast", disabled=not spec["ready"], width="stretch"):
        st.session_state.ast_analysis = None
        try:
            with st.spinner("입력을 준비하고 AST를 생성하고 있습니다."):
                item = prepare_side(spec, "AST")
                result = analyze_prepared(st.session_state.work_session, item["manifest"])
            if item["manifest"]["id"] not in {entry["manifest"]["id"] for entry in st.session_state.snapshots}:
                st.session_state.snapshots.append(item)
            st.session_state.ast_analysis = {"signature": signature, "input": item, **result}
        except (ValueError, OSError, RuntimeError) as error:
            st.error(f"AST를 생성하지 못했습니다: {error}")
    if not spec["ready"]:
        st.info("분석할 입력을 지정하면 AST 생성 버튼이 활성화됩니다.")
    result = st.session_state.ast_analysis
    if result and result["signature"] != signature:
        st.info("입력이 바뀌었습니다. AST 생성을 다시 실행하세요.")
    elif result:
        render_ast(result)


def render_ast(result):
    report = result["report"]
    if report["status"] == "complete":
        st.success("AST 생성 완료")
    else:
        st.warning("AST 생성에 확인 사항이 있습니다. 파싱 오류와 분석 범위를 확인하세요.")
    st.caption(report["source"])
    for column, label, value in zip(st.columns(3), ["파일·코드 셀", "파싱 완료", "파싱 오류"],
                                   [report["module_count"], report["module_count"] - len(report["errors"]), len(report["errors"])]):
        column.metric(label, value)
    selected_file = render_file_tree(result)
    view = st.segmented_control("결과 형식", ["트리형", "정리형"], default="트리형",
                                required=True, key="ast_output_view", persist_state="session")
    if view == "트리형":
        st.caption("Python AST 원형 · 들여쓰기 2칸 · 파일과 원본 코드 셀 순서 유지")
        paths = selected_file["ast_paths"] if selected_file else []
        if paths:
            if st.session_state.get("ast_tree_path") not in paths:
                st.session_state.ast_tree_path = paths[0]
            path = st.selectbox("파일·코드 셀 선택", paths, key="ast_tree_path", persist_state="session")
            entry = next(entry for entry in result["trees"] if entry["path"] == path)
            if entry["preprocessed"]:
                st.caption("Jupyter 전용 명령을 제외한 Python 본문의 트리입니다.")
            text = entry["tree"]
            st.code(text[:256 * 1024], language="text", wrap_lines=False)
            if len(text) > 256 * 1024:
                st.caption("화면에는 앞부분만 표시합니다. 전체 트리는 Markdown으로 내려받으세요.")
        elif selected_file:
            if selected_file["path"].lower().endswith((".py", ".ipynb")):
                st.info("이 파일에는 분석된 Python 코드 셀이 없습니다.")
            else:
                st.info("이 파일은 Python AST 대상이 아닙니다. 위에서 파일 경로와 종류를 확인할 수 있습니다.")
    else:
        st.caption("프로젝트 전체의 Python 코드 정리입니다.")
        st.markdown(result["documents"]["ast_structure.md"])
    with st.container(horizontal=True):
        for filename, label in (("ast_tree.md", "트리형 Markdown"),
                                ("file_tree.md", "파일 트리 Markdown"),
                                ("ast_structure.md", "정리형 Markdown"),
                                ("ast_structure.json", "정리형 JSON")):
            st.download_button(label, result["documents"][filename], file_name=filename,
                               mime="application/json" if filename.endswith(".json") else "text/markdown",
                               on_click="ignore", key="ast_download_" + filename)
        st.download_button("AST 보고서 ZIP", result["zip"], file_name="ast_reports.zip",
                           mime="application/zip", on_click="ignore", key="ast_download_zip")
    if report["errors"]:
        st.dataframe(report["errors"], hide_index=True, width="stretch")
    if report["warnings"] or report["skipped_files"]:
        with st.expander("분석 범위·확인 사항"):
            for text in report["warnings"]:
                st.write(text)
            if report["skipped_files"]:
                st.dataframe(report["skipped_files"], hide_index=True, width="stretch")


def render_file_tree(result):
    st.subheader("프로젝트 파일 트리")
    files = result["report"]["files"]
    st.caption(f"분석 루트: {result['report']['root']} · 파일 {len(files)}개 · 데이터·설정 파일 포함")
    st.caption("준비된 스냅샷의 상대 경로입니다. 빈 폴더와 제외된 파일은 포함하지 않습니다.")
    text = result["file_tree"]
    st.code(text[:256 * 1024], language="text", wrap_lines=False, height=320)
    if len(text) > 256 * 1024:
        st.caption("화면에는 앞부분만 표시합니다. 전체 파일 트리는 Markdown으로 내려받으세요.")
    if not files:
        return None
    by_path = {entry["path"]: entry for entry in files}
    if st.session_state.get("ast_file_path") not in by_path:
        st.session_state.ast_file_path = next((entry["path"] for entry in files if entry["ast_paths"]), files[0]["path"])
    path = st.selectbox("파일 선택", list(by_path), key="ast_file_path", persist_state="session")
    entry = by_path[path]
    st.dataframe([{
        "상대 경로": path, "종류": FILE_TYPES.get(entry["category"], entry["category"]),
        "언어": entry.get("language", "—"), "크기 (bytes)": entry["size"],
        "AST 파일·셀": len(entry["ast_paths"]),
    }], hide_index=True, width="stretch")
    with st.expander("파일 식별 정보"):
        st.text("SHA-256: " + entry["sha256"])
    return entry
