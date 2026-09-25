"""Two source snapshots -> semantic changes -> upstream QA candidates."""
from __future__ import annotations

import json
import hashlib
import os
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path

from code_relations import build_relations
from code_snapshot import compare_snapshots, load_snapshot


def comparison_input(path):
    """Accept a prepared source snapshot without treating APK payloads as source."""
    path = Path(path).resolve()
    manifest_path = path / "manifest.json"
    if not path.is_dir() or not manifest_path.is_file():
        return path, None
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    except (ValueError, UnicodeError):
        raise ValueError(f"manifest.json을 읽을 수 없습니다: {manifest_path}") from None
    if not isinstance(manifest, dict) or manifest.get("snapshot_type") != "qa_conversion":
        return path, None
    if manifest.get("schema_version") != 1:
        raise ValueError("지원하지 않는 변환 스냅샷 버전입니다.")
    capabilities = manifest.get("capabilities", {})
    if not isinstance(capabilities, dict) or manifest.get("representation") != "original_source" or not capabilities.get("python_ast"):
        raise ValueError("현재 compare는 Python 원본 소스만 분석합니다. APK/IPA 패키지·복원 코드 및 다른 언어는 별도 분석기가 필요합니다.")
    # The on-disk content directory makes snapshots portable between computers.
    content = path / "content"
    if not content.is_dir() or content.is_symlink() or content.is_junction() or content.resolve().parent != path:
        raise ValueError("변환 스냅샷의 content 폴더가 없거나 스냅샷 밖을 가리킵니다.")
    if manifest.get("status") != "prepared":
        raise ValueError("누락·오류가 있는 partial 스냅샷은 직접 비교할 수 없습니다. 변환 보고서를 먼저 확인하세요.")
    recorded = manifest.get("files")
    if not isinstance(recorded, list):
        raise ValueError("변환 스냅샷의 파일 목록이 올바르지 않습니다.")
    expected = {}
    for entry in recorded:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str) or not isinstance(entry.get("sha256"), str):
            raise ValueError("변환 스냅샷의 파일 기록이 올바르지 않습니다.")
        key = entry["path"]
        relative = Path(key)
        if relative.is_absolute() or "\\" in key or ":" in key or ".." in relative.parts or key in expected:
            raise ValueError("변환 스냅샷에 잘못된 상대 경로가 있습니다.")
        expected[key] = entry["sha256"]
    actual = set()
    for directory, dirs, files in os.walk(content, followlinks=False):
        for name in [*dirs, *files]:
            item = Path(directory) / name
            if item.is_symlink() or item.is_junction():
                raise ValueError("변환 스냅샷에 링크가 추가됐습니다. 원본 입력을 다시 변환하세요.")
        for name in files:
            item = Path(directory) / name
            key = item.relative_to(content).as_posix()
            actual.add(key)
            if key not in expected:
                raise ValueError("변환 후 파일이 추가됐습니다. 원본 입력을 다시 변환하세요.")
            with item.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            if digest != expected[key]:
                raise ValueError("변환 후 파일이 수정됐습니다. 원본 입력을 다시 변환하세요.")
    if actual != set(expected):
        raise ValueError("변환 후 파일이 삭제됐습니다. 원본 입력을 다시 변환하세요.")
    provenance = dict(snapshot_path=str(path), source=manifest.get("source"),
                      representation=manifest["representation"], engine=manifest.get("engine"),
                      manifest_path=str(manifest_path), warnings=manifest.get("warnings", []))
    source = manifest.get("source", {})
    if isinstance(source, dict) and (source.get("is_file") or source.get("selected_is_file")) and len(expected) == 1:
        return content / next(iter(expected)), provenance
    return content, provenance


def load_features(path, snapshots):
    if path is None:
        return [], ["기능 매핑을 지정하지 않아 제품 기능명·TC 연결은 미확정입니다."]
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("features"), list):
        raise ValueError("기능 매핑은 features 배열을 가진 JSON 객체여야 합니다.")
    features, warnings, ids = [], [], set()
    symbols = set().union(*(s.symbols for s in snapshots))
    for item in data["features"]:
        if not isinstance(item, dict) or not all(isinstance(item.get(k), str) and item[k].strip() for k in ("id", "name")):
            raise ValueError("각 기능에 문자열 id와 name이 필요합니다.")
        if item["id"] in ids:
            raise ValueError(f"중복 기능 ID: {item['id']}")
        ids.add(item["id"])
        entries, tc_ids = item.get("entry_points"), item.get("tc_ids", [])
        if not isinstance(entries, list) or not entries:
            raise ValueError(f"{item['id']}: entry_points 배열이 필요합니다.")
        if not isinstance(tc_ids, list) or not all(isinstance(v, str) for v in tc_ids):
            raise ValueError(f"{item['id']}: tc_ids는 문자열 배열이어야 합니다.")
        entry_ids = []
        for entry in entries:
            if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) and entry[k] for k in ("file", "symbol")):
                raise ValueError(f"{item['id']}: 각 진입점에 file과 symbol이 필요합니다.")
            file = entry["file"].replace("\\", "/")
            if file.startswith("/") or ":" in file or ".." in file.split("/"):
                raise ValueError("진입점 file은 비교 루트 기준 상대 경로여야 합니다.")
            key = f"{file}::{entry['symbol']}"
            if key not in symbols:
                warnings.append(f"매핑 진입점 미확인: {item['id']} → {key}")
            entry_ids.append(key)
        features.append(dict(id=item["id"], name=item["name"], entry_points=entry_ids, tc_ids=tc_ids))
    return features, warnings


def upstream(snapshot, relations, changed, max_depth):
    reverse = defaultdict(list)
    for edge in relations["edges"]:
        reverse[edge["callee"]].append(edge)
    queue, seen, results = deque([(changed, [])]), {changed}, []
    truncated = False
    while queue:
        current, chain = queue.popleft()
        if current in snapshot.symbols:
            symbol = snapshot.symbols[current]
            results.append(dict(symbol_id=current, file=symbol.file, symbol=symbol.qualified_name,
                                kind=symbol.kind, depth=len(chain), evidence_chain=chain))
        if len(chain) >= max_depth:
            if any(e["caller"] not in seen for e in reverse[current]):
                truncated = True
            continue
        for edge in reverse[current]:
            if edge["caller"] not in seen:
                seen.add(edge["caller"])
                queue.append((edge["caller"], [edge, *chain]))
    return results, truncated


def build_comparison(base_path: Path, target_path: Path, features_path=None, max_depth=10):
    if not 1 <= max_depth <= 100:
        raise ValueError("max-depth는 1~100이어야 합니다.")
    base_path, base_conversion = comparison_input(base_path)
    target_path, target_conversion = comparison_input(target_path)
    if base_path.is_file() != target_path.is_file():
        raise ValueError("파일끼리 또는 폴더끼리 비교하세요.")
    key = target_path.name if base_path.is_file() and target_path.is_file() else None
    base = load_snapshot(base_path, single_file_key=key)
    target = load_snapshot(target_path, single_file_key=key)
    diff = compare_snapshots(base, target)
    features, warnings = load_features(features_path, [base, target])
    conversion_inputs = {side: value for side, value in (("base", base_conversion), ("target", target_conversion)) if value}
    for side, value in conversion_inputs.items():
        warnings.extend(f"{side} 변환: {warning}" for warning in value["warnings"])
        warnings.append(f"{side}: 현재 AST 비교 범위는 Python .py/.ipynb이며 다른 언어·씬·에셋은 포함하지 않습니다.")
    graphs = {"base": build_relations(base), "target": build_relations(target)}
    snapshots = {"base": base, "target": target}
    for change in diff["changes"]:
        changed_id = f"{change['file']}::{change['symbol']}"
        impacts, cutoffs = [], []
        for side, snapshot in snapshots.items():
            if changed_id not in snapshot.symbols:
                continue
            callers, truncated = upstream(snapshot, graphs[side], changed_id, max_depth)
            impacts.extend(dict(side=side, **caller) for caller in callers)
            if truncated:
                cutoffs.append(side)
        feature_hits = []
        for feature in features:
            evidence = [impact for impact in impacts if impact["symbol_id"] in feature["entry_points"]]
            if evidence:
                feature_hits.append(dict(id=feature["id"], name=feature["name"], tc_ids=feature["tc_ids"], evidence=evidence))
        change.update(impacts=impacts, features=feature_hits, traversal_truncated=cutoffs)
        if cutoffs:
            warnings.append(f"{change['id']}: {', '.join(cutoffs)} 호출 역추적이 깊이 {max_depth}에서 제한됐습니다.")
    errors = [dict(side=side, **error) for side, snapshot in snapshots.items() for error in snapshot.errors]
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%S%fZ")
    report = dict(mode="compare", schema_version=1, run_id=run_id, created_at=now.isoformat(),
                  base=str(base_path), target=str(target_path), feature_mapping=str(Path(features_path).resolve()) if features_path else None,
                  status="incomplete" if errors else "analyzed", max_depth=max_depth,
                  conversion_inputs=conversion_inputs,
                  **diff, errors=errors, relations=graphs,
                  warnings=list(dict.fromkeys([*base.warnings, *target.warnings, *warnings])),
                  limitations=list(dict.fromkeys([*graphs["base"]["limitations"],
                      "비교는 구현의 변경 근거를 제공합니다. 제품 요구사항의 정답이나 실제 동작의 정상 여부는 별도로 검증합니다.",
                      "호출·참조 관계는 영향 후보입니다. 관계가 없다고 영향이 없다고 보장하지 않습니다.",
                      "기능명과 TC ID는 지정한 매핑에서 연결하며 코드 이름으로 임의 확정하지 않습니다."])))
    report["summary"].update(base_symbols=len(base.symbols), target_symbols=len(target.symbols),
                             parse_errors=len(errors), affected_features=len({f["id"] for c in report["changes"] for f in c["features"]}))
    return report


def table_value(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace("|", "&#124;").replace("\n", "<br>")


def code_block(value, language="text"):
    import re
    longest = max((len(s) for s in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{value.rstrip()}\n{fence}"


def markdown_comparison(report):
    lines = ["# 코드 변경·QA 영향 후보 비교", "", f"- 실행 ID: {report['run_id']}",
             f"- 기준 코드: `{report['base']}`", f"- 대상 코드: `{report['target']}`",
             f"- 상태: {'분석 불완전 — 오류 파일은 변경 판정에서 제외' if report['status'] == 'incomplete' else '파싱 완료 — 정적 분석 후보'}",
             f"- 기능 매핑: `{report['feature_mapping'] or '미지정'}`", "",
             f"변경 {len(report['changes'])}건 · 연결 기능 {report['summary']['affected_features']}개 · 파싱 오류 {len(report['errors'])}건", "",
             "기능·TC는 제공된 매핑과 정적 호출·참조 근거로 연결한 검증 후보입니다. 실제 테스트는 실행하지 않았습니다.", ""]
    if report["errors"]:
        lines += ["## 파싱·읽기 오류", ""]
        for error in report["errors"]:
            lines.append(f"- {error['side']}: {table_value(error)}")
        lines.append("")
    if report.get("conversion_inputs"):
        lines += ["## 변환 입력 출처", "", code_block(json.dumps(report["conversion_inputs"], ensure_ascii=False, indent=2)), ""]
    lines += ["## 변경 목록", "", "| 변경 ID | 유형 | 파일 | 심볼 | 기준 줄 | 대상 줄 | 연결 기능 |", "|---|---|---|---|---|---|---|"]
    for change in report["changes"]:
        positions = [str((change.get(side) or {}).get("start_line", "—")) for side in ("base", "target")]
        values = [change["id"], change["change_type"], change["file"], change["symbol"], *positions,
                  ", ".join(f["name"] for f in change["features"]) or "매핑 미연결"]
        lines.append("| " + " | ".join(table_value(v) for v in values) + " |")
    if not report["changes"]:
        lines += ["", "비교 가능한 범위에서 AST 변경이 없습니다. 오류·건너뛴 파일은 아래 기록을 확인하세요."]
    for change in report["changes"]:
        lines += ["", f"## {change['id']} — {change['file']}::{change['symbol']}", "", "### 코드 변경 근거", "",
                  code_block(change["source_diff"], "diff"), "", "### AST 변경 근거", "", code_block(change["ast_diff"], "diff"), "",
                  "### 연결 기능·관련 TC 후보", ""]
        if not change["features"]:
            lines.append("기능 매핑과 연결되지 않았습니다. 아래 호출·참조 후보를 검토하세요.")
        for feature in change["features"]:
            lines.append(f"- **{feature['name']}** ({feature['id']}) · TC: {', '.join(feature['tc_ids']) or '미지정'} · 결과: 미실행")
            for evidence in feature["evidence"]:
                chain = evidence["evidence_chain"]
                nodes = [edge["caller"] for edge in chain] + [f"{change['file']}::{change['symbol']}"]
                lines.append(f"  - {evidence['side']}: {' → '.join(nodes)}")
        lines += ["", "### 호출·참조 영향 후보", "", "| 버전 | 심볼 | 깊이 | 근거 |", "|---|---|---|---|"]
        for impact in change["impacts"]:
            chain = impact["evidence_chain"]
            reason = "; ".join(f"{e['caller']}:{e['line']} — {e['kind']} {e['expression']} → {e['callee']}" for e in chain) or "직접 AST 변경"
            lines.append("| " + " | ".join(table_value(v) for v in [impact["side"], impact["symbol_id"], impact["depth"], reason]) + " |")
    lines += ["", "## 텍스트 변경만 있는 파일", "", code_block(json.dumps(report["ignored_text_changes"], ensure_ascii=False, indent=2)),
              "", "## 변경 판정을 건너뛴 파일", "", code_block(json.dumps(report["skipped_files"], ensure_ascii=False, indent=2)),
              "", "## 확인 필요·분석 한계", ""]
    for warning in [*report["warnings"], *report["limitations"]]:
        lines.append(f"- {warning}")
    for side, graph in report["relations"].items():
        lines += ["", f"### {side} 미해결 호출 ({len(graph['unresolved'])}건)", ""]
        for item in graph["unresolved"]:
            lines.append(f"- `{item['caller']}`:{item['line']} · `{item['expression']}` · {item['reason']}")
        lines.append(f"외부·내장 호출 {len(graph.get('external', []))}건은 로컬 코드 영향 추적에서 제외했습니다.")
    return "\n".join(lines).rstrip() + "\n"


def write_comparison(report, output_format="both", output=None):
    if output_format not in {"both", "markdown", "json"}:
        raise ValueError("지원하지 않는 출력 형식입니다.")
    if output:
        stem = Path(output).resolve()
        if stem.suffix.lower() in {".py", ".ipynb"}:
            raise ValueError("보고서를 .py/.ipynb 원본 경로에 저장할 수 없습니다.")
    else:
        stem = Path(__file__).resolve().parent / "reports" / "compare" / report["run_id"] / "comparison"
    formats = ["markdown", "json"] if output_format == "both" else [output_format]
    paths = [stem.with_suffix(".md" if fmt == "markdown" else ".json").resolve() for fmt in formats]
    protected = {Path(report[k]).resolve() for k in ("base", "target")}
    if report["feature_mapping"]:
        protected.add(Path(report["feature_mapping"]).resolve())
    snapshots = []
    for value in report.get("conversion_inputs", {}).values():
        protected.add(Path(value["manifest_path"]).resolve())
        snapshots.append(Path(value["snapshot_path"]).resolve())
    if any(path == snapshot or path.is_relative_to(snapshot) for path in paths for snapshot in snapshots):
        raise ValueError("보고서를 보존한 변환 스냅샷 안에 저장할 수 없습니다.")
    if any(path in protected for path in paths):
        raise ValueError("보고서 경로가 입력 코드 또는 기능 매핑과 같습니다.")
    for fmt, path in zip(formats, paths):
        path.parent.mkdir(parents=True, exist_ok=True)
        value = markdown_comparison(report) if fmt == "markdown" else json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        path.write_text(value, encoding="utf-8")
        print(f"비교 보고서 작성 완료: {path}")
    return paths
