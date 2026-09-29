"""Single-input AST page, independent of comparison and flow interpretation."""
from __future__ import annotations

import streamlit as st

from qa_ast_service import analyze_prepared


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
    view = st.segmented_control("결과 형식", ["트리형", "정리형"], default="트리형",
                                required=True, key="ast_output_view", persist_state="session")
    if view == "트리형":
        st.caption("Python AST 원형 · 들여쓰기 2칸 · 파일과 원본 코드 셀 순서 유지")
        if result["trees"]:
            paths = [entry["path"] for entry in result["trees"]]
            if st.session_state.get("ast_tree_path") not in paths:
                st.session_state.ast_tree_path = paths[0]
            path = st.selectbox("파일·코드 셀 선택", paths, key="ast_tree_path", persist_state="session")
            entry = result["trees"][paths.index(path)]
            if entry["preprocessed"]:
                st.caption("Jupyter 전용 명령을 제외한 Python 본문의 트리입니다.")
            text = entry["tree"]
            st.code(text[:256 * 1024], language="text", wrap_lines=False)
            if len(text) > 256 * 1024:
                st.caption("화면에는 앞부분만 표시합니다. 전체 트리는 Markdown으로 내려받으세요.")
    else:
        st.markdown(result["documents"]["ast_structure.md"])
    with st.container(horizontal=True):
        for filename, label in (("ast_tree.md", "트리형 Markdown"),
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
