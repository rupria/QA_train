"""Session-isolated Streamlit UI for QA snapshot preparation and comparison."""
from __future__ import annotations

import hashlib
import difflib
import json
import os
from pathlib import Path

import streamlit as st

from code_comparison import code_block, markdown_comparison
from flow_ui import flow_view
from qa_web_service import (
    compare_inventory, compare_prepared, make_snapshot_download, new_session,
    list_git_history, prepare_git, prepare_local, prepare_upload,
)

LABELS = {"local": "로컬 소스", "engine": "엔진 프로젝트", "git": "Git", "apk": "APK", "ipa": "IPA"}
CHANGE_LABELS = {"added": "추가", "deleted": "삭제", "modified": "수정", "unchanged": "동일"}
LOCAL_ALLOWED = os.environ.get("QA_WEB_ALLOW_LOCAL", "1") == "1"


def initialize():
    if "work_session" not in st.session_state:
        st.session_state.work_session = new_session()
    st.session_state.setdefault("snapshots", [])
    if "pair_analysis" not in st.session_state:
        ids = {snapshot_id(item) for item in st.session_state.snapshots}
        for side, legacy_key in (("base", "base_choice"), ("target", "target_choice")):
            if st.session_state.get(legacy_key) in ids:
                st.session_state[f"{side}_method"] = "준비된 입력"
    st.session_state.setdefault("pair_analysis", None)
    st.session_state.setdefault("history_pool", {})
    st.session_state.setdefault("flow_result", None)
    if "current_pair_signature" not in st.session_state and st.session_state.pair_analysis:
        st.session_state.current_pair_signature = st.session_state.pair_analysis["signature"]
    # Remove only legacy sample entries; preserve the user's real prepared inputs.
    if st.session_state.pop("demo_features", None) is not None:
        example = Path(__file__).resolve().parent / "examples" / "code_compare"
        demo_paths = {str(example / "base"), str(example / "target")}
        st.session_state.snapshots = [item for item in st.session_state.snapshots
            if not (item["manifest"]["source"].get("path") in demo_paths
                    and item["label"] in {"Python 예제 · 이전", "Python 예제 · 최신"})]
    if st.session_state.get("view") not in {"비교", "AST 연결·해석", "스냅샷"}:
        st.session_state.view = "비교"
    st.session_state.pop("pending_view", None)


def snapshot_id(item):
    return item["manifest"]["id"]


def input_label(item):
    label = item["label"]
    for old, new in (("이전 · ", "Ver.A · "), ("최신 · ", "Ver.B · ")):
        if label.startswith(old):
            return new + label[len(old):]
    return label


def display_label(item):
    manifest = item["manifest"]
    kind = LABELS.get(manifest["source"]["kind"], manifest["source"]["kind"])
    version = (manifest["source"].get("commit_sha") or "")[:8]
    return f"{input_label(item)} · {kind}" + (f" · {version}" if version else "")


def input_side(side, title):
    with st.container(border=True):
        st.subheader(title)
        options = ["파일 업로드", "Git"] + (["로컬 경로"] if LOCAL_ALLOWED else [])
        if st.session_state.snapshots:
            options.append("준비된 입력")
        key = f"{side}_method"
        if st.session_state.get(key) not in options:
            st.session_state[key] = "파일 업로드"
        method = st.segmented_control("입력 방식", options, required=True, key=key, persist_state="session")
        spec = {"method": method, "source_root": ".", "ready": False}
        if method == "준비된 입력":
            by_id = {snapshot_id(item): item for item in st.session_state.snapshots}
            key = f"{side}_snapshot"
            if st.session_state.get(key) not in by_id:
                legacy_key = "base_choice" if side == "base" else "target_choice"
                legacy_id = st.session_state.get(legacy_key)
                st.session_state[key] = legacy_id if legacy_id in by_id else list(by_id)[0 if side == "base" else -1]
            selected = st.selectbox("준비된 입력 선택", list(by_id), format_func=lambda value: display_label(by_id[value]), key=key, persist_state="session")
            spec.update(item=by_id[selected], ready=True)
            snapshot_brief(by_id[selected]["manifest"])
            return spec
        if method == "파일 업로드":
            st.caption("APK · IPA · Python 파일 · 프로젝트 ZIP (폴더는 ZIP으로 올려주세요)")
            upload = st.file_uploader("파일 선택", type=["apk", "ipa", "py", "ipynb", "zip"], max_upload_size=200, key=f"{side}_upload")
            if upload is not None:
                spec.update(filename=upload.name, data=upload.getvalue(), ready=True)
            root_label = "ZIP 내부 비교 루트"
        else:
            is_git = method == "Git"
            label = "Git 저장소" if is_git else "로컬 경로"
            placeholder = ("https://github.com/owner/repository 또는 로컬 Git 경로" if LOCAL_ALLOWED else "https://github.com/owner/repository") if is_git else r"C:\projects\game 또는 C:\builds\game.apk"
            location = st.text_input(label, placeholder=placeholder, key=f"{side}_location", persist_state="session").strip()
            spec["location"] = location
            spec["ready"] = bool(location)
            root_label = "저장소 내부 비교 루트" if is_git else "프로젝트 내부 비교 루트"
            if not is_git:
                st.caption("Streamlit 서버가 실행되는 PC의 경로입니다.")
        spec["source_root"] = st.text_input(root_label, value=".", help="전체는 . 그대로 사용하세요. 폴더만 비교하려면 src 또는 Assets처럼 입력합니다.", key=f"{side}_root", persist_state="session").strip()
        if method == "Git":
            spec.update(git_version(side, spec["location"]))
        return spec


def git_version(side, location):
    mode = st.segmented_control("버전 선택", ["커밋 목록", "직접 입력"], default="커밋 목록", required=True, key=f"{side}_git_mode", persist_state="session")
    if mode == "직접 입력":
        ref = st.text_input("브랜치·태그·커밋", value="HEAD", key=f"{side}_ref", persist_state="session").strip()
        st.caption("직전 커밋은 HEAD~1, 최신 커밋은 HEAD로 지정할 수 있습니다.")
        return {"ref": ref, "ready": bool(location and ref)}
    history_ref = st.text_input("커밋 기록 기준", value="HEAD", help="현재 브랜치의 최신 기록은 HEAD입니다. 다른 브랜치·태그도 지정할 수 있습니다.", key=f"{side}_history_ref", persist_state="session").strip()
    query = (location, history_ref)
    pool = st.session_state.history_pool
    if st.button("커밋 목록 불러오기", icon=":material/history:", key=f"{side}_load_history", disabled=not (location and history_ref)):
        pool.pop(query, None)
        try:
            with st.spinner("Git 커밋 기록을 가져오고 있습니다."):
                pool[query] = list_git_history(st.session_state.work_session, location, ref=history_ref, limit=50)
            # Refresh both columns when a shared history is loaded on the right.
            st.rerun()
        except (ValueError, OSError, RuntimeError) as error:
            st.error(f"커밋 목록을 가져오지 못했습니다: {error}")
    commits = pool.get(query)
    if not commits:
        st.info("저장소를 입력하고 커밋 목록을 불러오세요. 같은 저장소의 조회 기록은 양쪽에서 함께 사용합니다.")
        return {"ref": None, "ready": False}
    by_sha = {commit["sha"]: commit for commit in commits}
    shas = list(by_sha)
    token = hashlib.sha256(repr((query, shas)).encode()).hexdigest()
    token_key, commit_key = f"{side}_history_token", f"{side}_commit"
    if st.session_state.get(token_key) != token or st.session_state.get(commit_key) not in by_sha:
        st.session_state[commit_key] = shas[min(1, len(shas) - 1) if side == "base" else 0]
        st.session_state[token_key] = token
    def commit_label(sha):
        item = by_sha[sha]
        return f"{item['date'][:16].replace('T', ' ')} · {item['subject']} · {item['short_sha']}"
    ref = st.selectbox("비교할 커밋", shas, format_func=commit_label, key=commit_key, persist_state="session")
    st.caption("기본 선택: 직전 커밋" if side == "base" else "기본 선택: 최신 커밋")
    if len(shas) == 1:
        st.warning("커밋이 1개만 조회됐습니다. 다른 기준 또는 다른 입력과 비교하세요.")
    with st.expander("커밋 기록 전체 보기"):
        st.dataframe([{"날짜": item["date"], "커밋 메시지": item["subject"], "해시": item["sha"]} for item in commits], hide_index=True, width="stretch")
    return {"ref": ref, "ready": bool(location and ref in by_sha)}


def input_signature(spec):
    if spec["method"] == "준비된 입력":
        return (spec["method"], snapshot_id(spec["item"]))
    if spec["method"] == "파일 업로드":
        return (spec["method"], spec.get("filename"), hashlib.sha256(spec.get("data", b"")).hexdigest(), spec["source_root"], spec["ready"])
    return (spec["method"], spec.get("location"), spec.get("ref"), spec["source_root"], spec["ready"])


def prepare_side(spec, title):
    if spec["method"] == "준비된 입력":
        return spec["item"]
    if spec["method"] == "파일 업로드":
        manifest = prepare_upload(st.session_state.work_session, spec["filename"], spec["data"], source_root=spec["source_root"])
        name = spec["filename"]
    elif spec["method"] == "Git":
        manifest = prepare_git(st.session_state.work_session, spec["location"], ref=spec["ref"], source_root=spec["source_root"])
        name = f"{spec['location'].rstrip('/').split('/')[-1]} @ {spec['ref']}"
    else:
        manifest = prepare_local(st.session_state.work_session, spec["location"], source_root=spec["source_root"])
        name = Path(spec["location"]).name
    return {"label": f"{title} · {name}", "manifest": manifest}


def pair_view():
    st.caption("왼쪽에 Ver.A, 오른쪽에 Ver.B를 지정하세요. 한 번의 버튼으로 두 입력 준비와 비교를 진행합니다.")
    left, right = st.columns(2)
    with left:
        base_spec = input_side("base", "Ver.A")
    with right:
        target_spec = input_side("target", "Ver.B")
    mode = st.segmented_control("비교 방식", ["자동", "코드 영향", "파일 구성"], default="자동", required=True, key="pair_mode", persist_state="session")
    st.caption("자동: 양쪽에 Python 소스가 있으면 코드 영향 분석, 그 외에는 파일 구성 비교를 진행합니다.")
    with st.expander("기능·TC 매핑과 분석 설정"):
        mapping = st.file_uploader("기능 매핑 JSON", type=["json"], max_upload_size=1, key="pair_features")
        depth = st.slider("호출 역추적 깊이", 1, 100, 10, key="pair_depth", persist_state="session")
        st.caption("코드 영향 분석에서 사용합니다. 제품의 기능명·TC는 매핑 JSON에 지정한 항목으로만 연결합니다.")
    features = mapping.getvalue() if mapping is not None else None
    signature = (input_signature(base_spec), input_signature(target_spec), mode, hashlib.sha256(features or b"").hexdigest(), depth)
    st.session_state.current_pair_signature = signature
    ready = base_spec["ready"] and target_spec["ready"]
    if st.button("두 입력 비교", type="primary", icon=":material/compare_arrows:", key="run_pair", disabled=not ready, width="stretch"):
        st.session_state.pair_analysis = None
        st.session_state.flow_result = None
        try:
            if (base_spec["method"] == target_spec["method"] == "Git"
                    and base_spec["location"] == target_spec["location"]
                    and base_spec["ref"] == target_spec["ref"]
                    and base_spec["source_root"] == target_spec["source_root"]):
                raise ValueError("두 입력이 같은 커밋과 비교 루트입니다. Ver.A와 Ver.B에 서로 다른 커밋을 선택하세요.")
            with st.spinner("Ver.A 입력을 준비하고 있습니다."):
                base = prepare_side(base_spec, "Ver.A")
            with st.spinner("Ver.B 입력을 준비하고 있습니다."):
                target = prepare_side(target_spec, "Ver.B")
            existing = {snapshot_id(item) for item in st.session_state.snapshots}
            for item in (base, target):
                if snapshot_id(item) not in existing:
                    st.session_state.snapshots.append(item)
                    existing.add(snapshot_id(item))
            ast_possible, inventory_possible, reason = comparison_availability(base, target)
            if not inventory_possible:
                raise ValueError(reason)
            actual_mode = ("코드 영향" if ast_possible else "파일 구성") if mode == "자동" else mode
            if actual_mode == "코드 영향" and not ast_possible:
                raise ValueError("코드 영향 분석에는 양쪽 모두 원본 Python 소스가 필요합니다. 파일 구성 비교를 선택하세요.")
            b, t = base["manifest"], target["manifest"]
            with st.spinner("두 입력의 변경 내용을 비교하고 있습니다."):
                report = compare_prepared(st.session_state.work_session, b, t, features_json=features, max_depth=depth) if actual_mode == "코드 영향" else compare_inventory(b, t)
                evidence = file_evidence(b, t) if b["representation"] == "original_source" else None
            if evidence:
                report["file_comparison"] = evidence
            st.session_state.pair_analysis = {"signature": signature, "report": report, "mode": actual_mode, "file_evidence": evidence, "base": base, "target": target}
        except (ValueError, OSError, RuntimeError) as error:
            st.error(f"두 입력을 비교하지 못했습니다: {error}")
    if not ready:
        st.info("Ver.A·Ver.B 양쪽 입력을 지정하면 비교 버튼이 활성화됩니다.")
    result = st.session_state.pair_analysis
    if result and result["signature"] != signature:
        st.info("입력 또는 설정이 바뀌었습니다. 두 입력 비교를 다시 실행하세요.")
    elif result:
        st.success(f"비교 완료 · {result['mode']}")
        for column, side in zip(st.columns(2), ("base", "target")):
            with column:
                st.write(display_label(result[side]))
                snapshot_brief(result[side]["manifest"])
        if result.get("file_evidence"):
            render_file_evidence(result["file_evidence"])
        if result["mode"] == "코드 영향":
            render_code_report(result["report"])
        else:
            render_inventory_report(result["report"])


def file_evidence(base, target):
    inventory = compare_inventory(base, target)
    details = {}
    remaining = 2 * 1024**2
    for change in inventory["changes"]:
        key = change["path"]
        if base["representation"] != "original_source":
            details[key] = {"note": "설치 패키지는 파일 구성·해시 변경까지 비교합니다."}
            continue
        values = []
        try:
            for manifest, side in ((base, "base"), (target, "target")):
                entry = change[side]
                if entry is None:
                    values.append("")
                    continue
                if entry["size"] > 512 * 1024 or entry["size"] > remaining:
                    raise ValueError("큰 파일은 텍스트 차이 표시 범위를 초과합니다.")
                content = (Path(manifest["output_path"]) / "content" / key).read_bytes()
                remaining -= len(content)
                if b"\x00" in content:
                    raise ValueError("바이너리 파일은 텍스트 차이를 표시하지 않습니다.")
                values.append(content.decode("utf-8-sig"))
            difference = "\n".join(difflib.unified_diff(values[0].splitlines(), values[1].splitlines(), fromfile=f"Ver.A/{key}", tofile=f"Ver.B/{key}", lineterm=""))
            if len(difference) > 128 * 1024:
                details[key] = {"note": "텍스트 차이가 너무 커서 앞부분만 표시합니다.", "diff": difference[:128 * 1024]}
            else:
                details[key] = {"diff": difference or "인코딩·줄바꿈 등 바이트 표현이 변경됐습니다."}
        except (UnicodeError, ValueError) as error:
            details[key] = {"note": str(error)}
    return {"inventory": inventory, "details": details}


def render_file_evidence(evidence):
    inventory = evidence["inventory"]
    changes = inventory["changes"]
    st.subheader("두 입력 사이의 변경 파일")
    st.caption(f"추가 {inventory['summary']['added']} · 삭제 {inventory['summary']['deleted']} · 수정 {inventory['summary']['modified']} · 동일 {inventory['summary']['unchanged']}")
    if not changes:
        st.info("선택한 비교 루트에서 파일 내용의 차이가 없습니다.")
        return
    st.dataframe([{"파일": c["path"], "변경": CHANGE_LABELS[c["type"]]} for c in changes], hide_index=True, width="stretch")
    key = st.selectbox("파일 변경 내용", [c["path"] for c in changes], key=f"file_diff_{inventory['run_id']}")
    detail = evidence["details"][key]
    if detail.get("note"):
        st.caption(detail["note"])
    if detail.get("diff"):
        st.code(detail["diff"].replace("--- 이전/", "--- Ver.A/", 1).replace("+++ 최신/", "+++ Ver.B/", 1), language="diff", wrap_lines=True)


def snapshot_rows():
    return [{"입력": input_label(item), "종류": LABELS.get(item["manifest"]["source"]["kind"], "소스"),
             "파일 수": len(item["manifest"]["files"]),
             "상태": "준비 완료" if item["manifest"]["status"] == "prepared" else "확인 필요",
             "비교 범위": "Python 코드·파일 구성" if item["manifest"]["capabilities"].get("python_ast") else "파일 구성"}
            for item in st.session_state.snapshots]


def snapshot_brief(manifest):
    for app in manifest.get("package", {}).get("applications", []):
        st.write({"앱": app.get("display_name") or app.get("bundle_identifier") or app.get("bundle_path"), "버전": app.get("version"), "빌드": app.get("build")})
    if manifest.get("warnings"):
        with st.expander("입력 확인 사항"):
            for message in manifest["warnings"]:
                st.write(message)


def comparison_availability(base, target):
    if snapshot_id(base) == snapshot_id(target):
        return False, False, "Ver.A와 Ver.B에 서로 다른 입력을 선택하세요."
    b, t = base["manifest"], target["manifest"]
    bs, ts = b["source"], t["source"]
    if (bs["kind"] == ts["kind"] == "git" and bs.get("commit_sha")
            and bs["commit_sha"] == ts.get("commit_sha")
            and bs.get("source_root") == ts.get("source_root")):
        return False, False, "두 입력이 같은 커밋과 비교 루트입니다. Ver.A와 Ver.B에 서로 다른 커밋을 선택하세요."
    if b["representation"] != t["representation"]:
        return False, False, "설치 패키지와 원본 소스는 직접 비교할 수 없습니다. Git의 해당 버전을 같은 설정으로 빌드한 APK·IPA를 준비하거나, 양쪽 모두 원본 프로젝트를 준비하세요."
    if b["representation"] == "package_payload" and b["source"]["kind"] != t["source"]["kind"]:
        return False, False, "APK끼리 또는 IPA끼리 비교하세요. 두 플랫폼은 파일 구조가 다릅니다."
    complete = all(m["status"] == "prepared" for m in (b, t))
    if not complete:
        return False, False, "일부 파일이 누락된 입력입니다. 스냅샷의 확인 사항을 해결한 뒤 다시 준비하세요."
    ast = all(m["capabilities"].get("python_ast") and m["representation"] == "original_source" for m in (b, t))
    return ast, True, ""


def downloads(report, markdown):
    if report.get("file_comparison") and report["mode"] == "compare":
        markdown += "\n## 파일 내용 변경\n\n"
        for path, detail in report["file_comparison"]["details"].items():
            markdown += code_block(path) + "\n"
            if detail.get("note"):
                markdown += detail["note"] + "\n\n"
            if detail.get("diff"):
                markdown += code_block(detail["diff"], "diff") + "\n"
    with st.container(horizontal=True):
        st.download_button("보고서 JSON", json.dumps(report, ensure_ascii=False, indent=2), file_name="comparison.json", mime="application/json", icon=":material/download:", on_click="ignore", key="report_json")
        st.download_button("보고서 Markdown", markdown, file_name="comparison.md", mime="text/markdown", icon=":material/download:", on_click="ignore", key="report_md")


def render_code_report(report):
    st.divider()
    st.subheader("코드 변경과 QA 영향 후보")
    tc_ids = {tc for c in report["changes"] for f in c["features"] for tc in f["tc_ids"]}
    for column, label, value in zip(st.columns(4), ["코드 변경", "연결 기능", "TC 후보", "파싱 오류"], [len(report["changes"]), report["summary"]["affected_features"], len(tc_ids), len(report["errors"])]):
        column.metric(label, value)
    st.caption("정적 분석 결과입니다. 기능·TC는 검증 후보이며 실제 테스트 결과는 미실행입니다.")
    if report["errors"]:
        st.warning("읽기·파싱 오류가 있는 파일은 변경 판정에서 제외했습니다.")
        st.dataframe(report["errors"], hide_index=True, width="stretch")
    changes = report["changes"]
    if changes:
        st.dataframe([{"변경": CHANGE_LABELS[c["change_type"]], "파일": c["file"], "모듈·컴포넌트": c["symbol"], "연결 기능": ", ".join(f["name"] for f in c["features"]) or "매핑 미연결"} for c in changes], hide_index=True, width="stretch")
        selected = st.selectbox("변경 상세", range(len(changes)), format_func=lambda i: f"{changes[i]['file']} :: {changes[i]['symbol']}", key=f"change_{report['run_id']}")
        change = changes[selected]
        with st.container(border=True):
            st.markdown(f"**{change['symbol']}**")
            st.code(change["source_diff"].replace("--- base/", "--- Ver.A/", 1).replace("+++ target/", "+++ Ver.B/", 1), language="diff", wrap_lines=True)
            if change["features"]:
                st.markdown("**연결 기능·TC 후보**")
                st.dataframe([{"기능": f["name"], "TC": ", ".join(f["tc_ids"]) or "미지정", "테스트 결과": "미실행"} for f in change["features"]], hide_index=True, width="stretch")
            else:
                st.info("연결된 기능 매핑이 없습니다. 호출·참조 후보를 확인하세요.")
            with st.expander("호출·참조 근거"):
                st.dataframe([{"버전": "Ver.A" if p["side"] == "base" else "Ver.B", "심볼": p["symbol_id"], "깊이": p["depth"], "경로": " → ".join([e["caller"] for e in p["evidence_chain"]] + [f"{change['file']}::{change['symbol']}"])} for p in change["impacts"]], hide_index=True, width="stretch")
    else:
        st.success("비교 가능한 Python 범위에서 AST 변경이 없습니다.")
    downloads(report, markdown_comparison(report))
    with st.expander("분석 범위·확인 사항"):
        for text in report["warnings"] + report["limitations"]:
            st.write(text)
        st.write({"텍스트만 변경된 파일": report["ignored_text_changes"], "건너뛴 파일": report["skipped_files"]})


def render_inventory_report(report):
    st.divider()
    st.subheader("파일 구성 변경")
    for column, key in zip(st.columns(4), ["added", "deleted", "modified", "unchanged"]):
        column.metric(CHANGE_LABELS[key], report["summary"][key])
    if report["changes"]:
        st.dataframe([{"파일": c["path"], "변경": CHANGE_LABELS[c["type"]], "Ver.A SHA-256": (c.get("base") or {}).get("sha256", "—"), "Ver.B SHA-256": (c.get("target") or {}).get("sha256", "—")} for c in report["changes"]], hide_index=True, width="stretch")
    else:
        st.success("파일 구성과 해시가 같습니다.")
    st.caption("해시 변경은 파일 내용의 변경 근거입니다. 실제 기능 변경이나 테스트 통과 여부는 확인하지 않습니다.")
    lines = ["# 파일 구성 변경", "", f"추가 {report['summary']['added']} · 삭제 {report['summary']['deleted']} · 수정 {report['summary']['modified']} · 동일 {report['summary']['unchanged']}", "", "```json", json.dumps(report, ensure_ascii=False, indent=2), "```", ""]
    downloads(report, "\n".join(lines))
    with st.expander("비교 범위·확인 사항"):
        for text in report.get("limitations", []):
            st.write(text)


def snapshots_view():
    st.subheader("준비한 스냅샷")
    if not st.session_state.snapshots:
        st.info("입력을 먼저 준비하세요.")
        return
    st.dataframe(snapshot_rows(), hide_index=True, width="stretch")
    snapshots = st.session_state.snapshots
    selected = st.selectbox("스냅샷 선택", range(len(snapshots)), format_func=lambda i: display_label(snapshots[i]), key="snapshot_choice")
    manifest = snapshots[selected]["manifest"]
    snapshot_brief(manifest)
    st.dataframe([{"경로": f["path"], "종류": f.get("category", "파일"), "크기 (KB)": round(f["size"] / 1024, 2)} for f in manifest["files"]], hide_index=True, width="stretch")
    st.download_button("Manifest JSON", json.dumps(manifest, ensure_ascii=False, indent=2), file_name="manifest.json", mime="application/json", on_click="ignore", key="manifest_json")
    if st.button("스냅샷 ZIP 준비", icon=":material/archive:", key="prepare_zip"):
        try:
            with st.spinner("다운로드할 스냅샷을 묶고 있습니다."):
                data = make_snapshot_download(manifest)
            st.session_state.snapshot_download = (manifest["id"], data)
        except (ValueError, OSError, RuntimeError) as error:
            st.error(f"다운로드를 준비하지 못했습니다: {error}")
    ready = st.session_state.get("snapshot_download")
    if ready and ready[0] == manifest["id"]:
        st.download_button("스냅샷 ZIP 다운로드", ready[1], file_name=f"snapshot-{manifest['id']}.zip", mime="application/zip", icon=":material/download:", on_click="ignore", key="snapshot_zip")
    st.caption("스냅샷 ZIP은 변환 결과 보관용입니다. 비교 입력에는 원본 소스·프로젝트 ZIP 또는 설치 파일을 사용하세요.")
    with st.expander("출처·변환 상세"):
        st.json(manifest)


def main():
    st.set_page_config(page_title="QA compare", page_icon=":material/compare_arrows:", layout="wide")
    initialize()
    with st.sidebar:
        st.markdown("### QA compare")
        st.caption("변경 근거에서 QA 검증 후보까지")
        st.divider()
        st.markdown("**지원하는 입력**")
        st.write("소스 · 엔진 프로젝트 · Git\n\nAPK · IPA 설치 패키지")
        st.caption(f"현재 세션의 입력 {len(st.session_state.snapshots)}개")
        st.divider()
        st.caption("Python: 코드 영향 분석\n\n다른 소스·패키지: 파일 구성 비교")
    st.title("QA compare")
    st.write("Ver.A·Ver.B를 한 화면에서 지정하고 변경 내용을 비교하세요.")
    compare_tab, flow_tab, snapshot_tab = st.tabs(
        ["비교", "AST 연결·해석", "스냅샷"], key="work_tabs",
    )
    # Keep input widgets mounted so uploads and mapping survive tab navigation.
    # Preparation and analysis remain explicit button actions.
    with compare_tab:
        pair_view()
    with flow_tab:
        flow_view()
    with snapshot_tab:
        snapshots_view()


if __name__ == "__main__":
    main()
