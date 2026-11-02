"""Local Diff2Html renderer for Streamlit Custom Components v2."""
from __future__ import annotations

from pathlib import Path

import streamlit as st


_VENDOR = Path(__file__).resolve().parent / "vendor" / "diff2html"
_VENDOR_JS = (_VENDOR / "diff2html.min.js").read_text(encoding="utf-8")
_VENDOR_CSS = (_VENDOR / "diff2html.min.css").read_text(encoding="utf-8")
_UMD_MARKER = "}(this,(()"
if _UMD_MARKER not in _VENDOR_JS:
    raise RuntimeError("지원하는 Diff2Html 3.4.56 브라우저 번들을 찾을 수 없습니다.")

# The official browser distribution is UMD. CCv2 evaluates JavaScript as an ES
# module, where top-level `this` is undefined, so bind the unchanged factory to
# a component-local object before mounting the renderer.
_COMPONENT_JS = (
    "const __qaDiff2HtmlGlobal = {};\n"
    + _VENDOR_JS.replace(_UMD_MARKER, "}(__qaDiff2HtmlGlobal,(()", 1)
    + """

export default function(component) {
  const { data, parentElement } = component
  const root = parentElement.querySelector("[data-qa-diff-root]")
  if (!root) return
  const patch = data && typeof data.patch === "string" ? data.patch : ""
  if (!patch) {
    root.textContent = "표시할 텍스트 diff가 없습니다."
    return
  }
  try {
    root.innerHTML = __qaDiff2HtmlGlobal.Diff2Html.html(patch, {
      drawFileList: false,
      outputFormat: "line-by-line",
      matching: "lines",
      diffMaxChanges: 4000,
      diffMaxLineLength: 10000,
      maxLineLengthHighlight: 1000,
      colorScheme: "auto",
      renderNothingWhenEmpty: false,
    })
  } catch (error) {
    root.textContent = "diff를 화면에 표시하지 못했습니다. 원본 패치는 보고서에서 확인하세요."
  }
}
"""
)

_COMPONENT_CSS = _VENDOR_CSS + """

:host {
  color: var(--st-text-color);
  font-family: var(--st-font);
}

[data-qa-diff-root] {
  min-width: 0;
  overflow-x: auto;
}

.d2h-file-wrapper {
  border-color: var(--st-border-color);
  border-radius: var(--st-border-radius);
  margin-bottom: 0;
}

.d2h-file-header {
  position: static;
}
"""

_DIFF_VIEWER = None


def register_diff_viewer() -> None:
    """Register once in the active Streamlit runtime for this script run."""
    global _DIFF_VIEWER
    _DIFF_VIEWER = st.components.v2.component(
        "qa_diff2html_3_4_56",
        html='<div data-qa-diff-root role="region" aria-label="코드 변경 내용"></div>',
        css=_COMPONENT_CSS,
        js=_COMPONENT_JS,
        isolate_styles=True,
    )


def render_diff(patch: str, *, key: str):
    """Mount a locally bundled, read-only Git diff view."""
    if _DIFF_VIEWER is None:
        register_diff_viewer()
    return _DIFF_VIEWER(data={"patch": patch}, key=key, width="stretch")
