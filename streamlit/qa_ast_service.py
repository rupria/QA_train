"""Generate single-input AST reports from a verified, session-owned snapshot."""
from __future__ import annotations

import ast
from dataclasses import asdict
from datetime import datetime, timezone
import io
import json
from pathlib import Path
import platform
import uuid
import zipfile

from ast_runtime import AST_ROOT

from ast_analyzer import (
    ModuleInfo, SourceAnalyzer, collect_execution_details, collect_imports,
    feature_group, markdown_structure,
)
from code_comparison import code_block
from code_snapshot import load_snapshot
from qa_web_service import MAX_DOWNLOAD_BYTES, _session, _verified


def analyze_prepared(session, manifest: dict) -> dict:
    session = _session(session)
    stored, output = _verified(manifest)
    if output.parent != session / "snapshots":
        raise ValueError("현재 웹 세션에서 준비한 스냅샷만 AST로 분석할 수 있습니다.")
    if stored.get("representation") != "original_source" or not stored.get("capabilities", {}).get("python_ast"):
        raise ValueError("AST 생성에는 원본 .py 또는 .ipynb가 필요합니다. APK·IPA나 다른 언어만 있는 입력은 지원하지 않습니다.")
    if stored.get("status") != "prepared":
        raise ValueError("일부 파일이 누락된 입력입니다. 스냅샷의 확인 사항을 해결한 뒤 다시 준비하세요.")

    source = stored["source"]
    label = source.get("uploaded_name") or source.get("remote_url") or source.get("path", "소스")
    if source.get("commit_sha"):
        label += " @ " + source["commit_sha"]
    snapshot = load_snapshot(output / "content")
    single_file = Path(source.get("uploaded_name") or source.get("path", "")).suffix.lower() in {".py", ".ipynb"}
    lines = ["# AST Tree", "", "- 분석 경로: " + label.replace("\n", " ")]
    modules, trees, errors = [], [], []
    warnings = list(stored.get("warnings", []))
    for unit in snapshot.units.values():
        info = ModuleInfo(path=unit.path, module=unit.module,
                          feature_group=feature_group(Path(unit.path.split("#cell-", 1)[0])))
        error, tree_text = unit.error, unit.error or ""
        if unit.tree is not None:
            try:
                tree_text = ast.dump(unit.tree, indent=2)
                visitor = SourceAnalyzer()
                visitor.visit(unit.tree)
                info.imports = collect_imports(unit.tree)
                info.symbols = sorted(visitor.symbols, key=lambda item: (item.start_line, item.end_line))
                info.assignments, info.module_calls, info.control_flow, info.execution_items = collect_execution_details(unit.tree)
            except RecursionError as exc:
                error = tree_text = f"RecursionError: {exc}"
        info.error = error
        if error:
            errors.append({"file": unit.path, "error": error})
        if unit.preprocessed:
            warnings.append(f"{unit.path}: Jupyter 전용 명령을 제외하고 Python 본문을 분석했습니다. 제외된 명령의 실행 결과는 분석하지 않습니다.")
        modules.append(asdict(info))
        trees.append({"path": unit.path, "tree": tree_text, "error": error,
                      "preprocessed": unit.preprocessed})
        heading = unit.path
        if single_file:
            heading = ("원본 코드 셀 " + unit.path.rsplit("#cell-", 1)[1]
                       if "#cell-" in unit.path else "원본 파일")
        lines.extend(["", "## " + heading, "", code_block(tree_text)])
    if any(item["path"].lower().endswith(".ipynb") for item in stored["files"]):
        warnings.append("노트북은 원본 코드 셀 순서로 분석하며, 셀 간 실행 상태와 런타임 연결은 해석하지 않습니다.")
    if not modules:
        warnings.append("분석할 Python 코드 셀이 없습니다.")
    warnings = list(dict.fromkeys(warnings))
    report = {
        "mode": "structure", "source": label, "root": source.get("source_root", "."),
        "run_id": uuid.uuid4().hex, "created_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_id": stored["id"], "language": "python",
        "language_version": platform.python_version(), "parser": "Python ast.parse",
        "input": {key: source[key] for key in ("kind", "uploaded_name", "remote_url", "commit_sha", "source_root") if key in source},
        "status": "incomplete" if errors or not modules else "complete",
        "module_count": len(modules), "modules": modules, "errors": errors,
        "warnings": warnings, "skipped_files": stored.get("skipped", []),
    }
    tree_md = "\n".join(lines) + "\n"
    structure_md = markdown_structure(report)
    if warnings:
        structure_md += "\n## 분석 범위·확인 사항\n\n" + "\n".join("- " + item for item in warnings) + "\n"
    documents = {
        "ast_tree.md": tree_md,
        "ast_structure.md": structure_md,
        "ast_structure.json": json.dumps(report, ensure_ascii=False, indent=2) + "\n",
    }
    if sum(len(value.encode("utf-8")) for value in documents.values()) > MAX_DOWNLOAD_BYTES:
        raise ValueError("AST 보고서가 100MiB를 초과했습니다. 분석 루트를 더 작은 폴더로 지정하세요.")
    directory = session / "ast_reports" / report["run_id"]
    directory.mkdir(parents=True)
    for filename, text in documents.items():
        (directory / filename).write_text(text, encoding="utf-8")
    bundle = io.BytesIO()
    with zipfile.ZipFile(bundle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for filename, text in documents.items():
            archive.writestr(filename, text.encode("utf-8"))
    return {"report": report, "trees": trees, "documents": documents,
            "zip": bundle.getvalue(), "output_path": str(directory)}
