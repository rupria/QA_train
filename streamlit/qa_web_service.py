"""Session-isolated web backend; analyzed projects and apps are never executed."""
from __future__ import annotations

import hashlib
import io
import json
import os
import re
import shutil
import stat
import subprocess
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from ast_runtime import AST_ROOT

import artifact_conversion as conversion
from code_comparison import build_comparison


MAX_UPLOAD_BYTES = 200 * 1024**2
MAX_DOWNLOAD_BYTES = 100 * 1024**2
GIT_CLONE_TIMEOUT_SECONDS = 180
UPLOAD_EXTENSIONS = {".py", ".ipynb", ".zip", ".apk", ".ipa"}


def new_session(workspace_root=None) -> Path:
    root = Path(workspace_root or os.environ.get("QA_WEB_WORKSPACE") or
                Path(__file__).resolve().parent / ".web_runs").expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    session = root / ("session-" + uuid.uuid4().hex)
    session.mkdir()
    (session / ".qa-web-session").write_text(session.name, encoding="ascii")
    return session


def _session(path) -> Path:
    raw = Path(path).absolute()
    if not raw.is_dir() or conversion._is_reparse(raw):
        raise ValueError("유효한 웹 세션 폴더가 필요합니다.")
    session = raw.resolve()
    marker = session / ".qa-web-session"
    if not marker.is_file() or conversion._is_reparse(marker) or marker.read_text(encoding="ascii") != session.name:
        raise ValueError("웹 세션 소유 정보를 확인할 수 없습니다.")
    return session


def _job(session) -> tuple[Path, Path]:
    session = _session(session)
    folder = session / "input" / uuid.uuid4().hex
    folder.mkdir(parents=True)
    (folder / ".qa-web-job").write_text(folder.name, encoding="ascii")
    output = session / "snapshots" / folder.name
    return folder, output


def _cleanup_job(folder: Path) -> None:
    expected = folder.absolute()
    if (folder.resolve() != expected or conversion._is_reparse(folder)
            or folder.parent.name != "input"):
        raise RuntimeError("새 웹 입력 폴더의 정리 경로를 확인할 수 없습니다.")
    _session(folder.parent.parent)
    marker = folder / ".qa-web-job"
    if not marker.is_file() or conversion._is_reparse(marker) or marker.read_text(encoding="ascii") != folder.name:
        raise RuntimeError("새 웹 입력 폴더의 소유 정보를 확인할 수 없습니다.")
    def readonly_retry(function, path, error):
        target = Path(path)
        if (not target.resolve().is_relative_to(expected) or conversion._is_reparse(target)):
            raise RuntimeError("웹 입력 폴더 밖의 권한을 변경할 수 없습니다.") from error
        target.chmod(target.stat().st_mode | stat.S_IWRITE)
        function(path)
    shutil.rmtree(expected, onexc=readonly_retry)


def _save_manifest(manifest: dict) -> dict:
    output = Path(manifest["output_path"])
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (output / "conversion.md").write_text(conversion._markdown(manifest), encoding="utf-8")
    return manifest


def prepare_upload(session, filename: str, data: bytes, source_root=".") -> dict:
    conversion._safe_relative(filename)
    if "/" in filename or "\\" in filename or Path(filename).suffix.lower() not in UPLOAD_EXTENSIONS:
        raise ValueError("업로드는 경로 없는 .py/.ipynb/.zip/.apk/.ipa 파일명이어야 합니다.")
    extension = Path(filename).suffix.lower()
    if not isinstance(data, bytes) or (not data and extension != ".py") or len(data) > MAX_UPLOAD_BYTES:
        raise ValueError("빈 파일이거나 업로드 크기 제한을 초과했습니다.")
    conversion._safe_relative(source_root, allow_dot=True)
    archive = None
    try:
        if extension == ".zip":
            archive = zipfile.ZipFile(io.BytesIO(data))
        entries = conversion._validate_zip(archive, "Uploaded project ZIP") if archive else None
        folder, output = _job(session)
        try:
            if archive is not None:
                source = folder / "project"
                source.mkdir()
                total = 0
                for entry, key in entries:
                    destination = source / key
                    if entry.is_dir():
                        destination.mkdir(parents=True, exist_ok=True)
                    else:
                        with archive.open(entry) as reader:
                            size, _, _ = conversion._stream_copy(reader, destination,
                                expected_size=entry.file_size, byte_limit=conversion.MAX_APK_MEMBER_BYTES)
                        total += size
                        if total > conversion.MAX_APK_TOTAL_BYTES:
                            raise ValueError("프로젝트 ZIP의 실제 압축 해제 크기 제한을 초과했습니다.")
            else:
                source = folder / filename
                with source.open("xb") as writer:
                    writer.write(data)
            manifest = conversion.convert_input(source, output=output, source_root=source_root)
            manifest["source"].update(uploaded_name=filename, upload_sha256=hashlib.sha256(data).hexdigest())
            return _save_manifest(manifest)
        except Exception:
            _cleanup_job(folder)
            raise
    except zipfile.BadZipFile as exc:
        raise ValueError("올바른 ZIP 패키지가 아닙니다. 파일이 손상됐거나 지원하지 않는 구조입니다.") from exc
    finally:
        if archive is not None:
            archive.close()


def prepare_local(session, path, kind="auto", ref=None, source_root=".") -> dict:
    if os.environ.get("QA_WEB_ALLOW_LOCAL", "1") == "0":
        raise ValueError("이 서버는 로컬 경로 입력을 허용하지 않습니다. 파일 업로드 또는 공개 GitHub HTTPS 주소를 사용하세요.")
    if path is None or isinstance(path, str) and not path.strip():
        raise ValueError("로컬 입력 경로를 지정하세요.")
    folder, output = _job(session)
    try:
        return conversion.convert_input(Path(path), kind=kind, output=output, ref=ref, source_root=source_root)
    except Exception:
        _cleanup_job(folder)
        raise


def _github_url(location: str) -> str:
    if not isinstance(location, str) or location != location.strip() or any(ord(c) < 32 for c in location):
        raise ValueError("GitHub HTTPS 저장소 주소가 올바르지 않습니다.")
    parsed = urlsplit(location)
    parts = parsed.path.split("/")
    if (parsed.scheme != "https" or parsed.netloc != "github.com" or parsed.query or parsed.fragment
            or len(parts) != 3 or parts[0] or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]{0,99}", parts[1])
            or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}", parts[2])):
        raise ValueError("https://github.com/owner/repository 형식만 지원합니다. 인증정보·query·fragment·추가 경로는 사용할 수 없습니다.")
    name = parts[2][:-4] if parts[2].endswith(".git") else parts[2]
    if not name:
        raise ValueError("GitHub 저장소 이름이 비어 있습니다.")
    return f"https://github.com/{parts[1]}/{name}.git"


def _clone_remote(session, location) -> tuple[Path, Path, Path, str]:
    """Anonymous isolated bare clone shared by preparation and history reads."""
    url = _github_url(location)
    folder, output = _job(session)
    try:
        git = conversion._git_executable()
        env = conversion._git_env()
        # Remote import is deliberately public/anonymous and isolated from
        # global URL rewriting, credential helpers and template hooks.
        config = folder / "empty-git-config"
        config.write_text("", encoding="ascii")
        hooks = folder / "empty-hooks"
        hooks.mkdir()
        env.update(GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never", GIT_CONFIG_NOSYSTEM="1",
                   GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_COUNT="0")
        env.pop("GIT_CONFIG_PARAMETERS", None)
        env.pop("GIT_SSL_NO_VERIFY", None)
        env.pop("GIT_ASKPASS", None)
        env.pop("SSH_ASKPASS", None)
        repo = folder / "repo"
        args = [git, "-c", f"core.hooksPath={hooks}", "-c", f"init.templateDir={hooks}",
            "-c", "credential.helper=", "-c", "core.askPass=", "-c", "submodule.recurse=false", "-c", "http.sslVerify=true",
            "-c", "http.followRedirects=false", "-c", "protocol.ext.allow=never", "-c", "protocol.file.allow=never",
            "clone", "--bare", "--no-local", "--", url, str(repo)]
        try:
            result = subprocess.run(args, shell=False, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, timeout=GIT_CLONE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired as exc:
            raise ValueError("GitHub 가져오기 제한 시간이 지났습니다. 저장소 크기와 네트워크를 확인하세요.") from exc
        if result.returncode:
            raise ValueError("GitHub 가져오기에 실패했습니다: " + result.stderr[-3000:].decode("utf-8", "replace"))
        return folder, output, repo, url
    except Exception:
        _cleanup_job(folder)
        raise


def prepare_git(session, location, ref="HEAD", source_root=".") -> dict:
    if location is None or isinstance(location, str) and not location.strip():
        raise ValueError("GitHub 주소 또는 로컬 저장소 경로를 지정하세요.")
    value = str(location)
    if "://" not in value:
        return prepare_local(session, value, kind="git", ref=ref, source_root=source_root)
    conversion._safe_relative(source_root, allow_dot=True)
    folder, output, repo, url = _clone_remote(session, value)
    try:
        manifest = conversion.convert_input(repo, kind="git", ref=ref, output=output, source_root=source_root)
        manifest["source"]["remote_url"] = url
        manifest["warnings"].append("GitHub 입력은 공개 HTTPS 저장소를 별도 bare 저장소로 가져왔습니다. 프로젝트 코드·hook·submodule·checkout은 실행하지 않았습니다.")
        return _save_manifest(manifest)
    except Exception:
        _cleanup_job(folder)
        raise


def list_git_history(session, location, ref="HEAD", limit=50) -> list[dict]:
    """Return first-parent history without checkout or project execution.

    Dates are ISO 8601 committer dates. The starting ref is pinned to one commit
    SHA before log traversal; remote history uses a fresh temporary bare clone.
    """
    _session(session)
    if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 200:
        raise ValueError("커밋 목록 개수는 1~200 사이의 정수여야 합니다.")
    if (not isinstance(ref, str) or not ref.strip() or ref.startswith("-")
            or any(ord(char) < 32 or ord(char) == 127 for char in ref)):
        raise ValueError("올바른 Git 시작 ref를 지정하세요.")
    if location is None or isinstance(location, str) and not location.strip():
        raise ValueError("GitHub 주소 또는 로컬 저장소 경로를 지정하세요.")
    value, folder = str(location), None
    try:
        if "://" in value:
            folder, _, repo, _ = _clone_remote(session, value)
        else:
            if os.environ.get("QA_WEB_ALLOW_LOCAL", "1") == "0":
                raise ValueError("이 서버는 로컬 저장소 경로 입력을 허용하지 않습니다.")
            raw = Path(value).expanduser().absolute()
            if not raw.is_dir() or conversion._is_reparse(raw):
                raise ValueError("실제 로컬 Git 저장소 폴더를 지정하세요. 링크/junction은 지원하지 않습니다.")
            repo = raw.resolve()
        git = conversion._git_executable()
        sha = conversion._git(git, repo, ["rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}"])
        sha = sha.decode("ascii").strip()
        if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
            raise ValueError("Git 시작 ref를 하나의 commit SHA로 확정할 수 없습니다.")
        payload = conversion._git(git, repo, ["log", "--first-parent", "--no-color", "--no-decorate", "--no-show-signature", "--encoding=UTF-8",
            "--format=%H%x00%h%x00%cI%x00%s", "-z", f"--max-count={limit}", sha, "--"])
        fields = payload.split(b"\x00")
        if fields and fields[-1] == b"":
            fields.pop()
        if len(fields) % 4 or len(fields) // 4 > limit:
            raise ValueError("Git 커밋 목록의 NUL 구분 형식이 올바르지 않습니다.")
        history = []
        for index in range(0, len(fields), 4):
            full, short, date, subject = (field.decode("utf-8", "replace") for field in fields[index:index + 4])
            if (not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", full)
                    or not re.fullmatch(r"[0-9a-f]{4,64}", short) or not full.startswith(short)):
                raise ValueError("Git 커밋 목록의 SHA 기록이 올바르지 않습니다.")
            history.append(dict(sha=full, short_sha=short, date=date, subject=subject))
        return history
    except OSError as exc:
        raise ValueError(f"Git 커밋 목록을 읽을 수 없습니다: {exc}") from exc
    finally:
        if folder is not None:
            _cleanup_job(folder)


def _verified(manifest: dict) -> tuple[dict, Path]:
    output = Path(manifest["output_path"]).resolve()
    if conversion._is_reparse(output) or conversion._is_reparse(output / "manifest.json"):
        raise ValueError("스냅샷 경로에 링크를 사용할 수 없습니다.")
    stored = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    if not isinstance(stored, dict) or stored.get("snapshot_type") != "qa_conversion" or stored.get("schema_version") != 1 or stored.get("id") != manifest.get("id"):
        raise ValueError("준비된 변환 스냅샷을 확인할 수 없습니다.")
    content = output / "content"
    if not content.is_dir() or conversion._is_reparse(content):
        raise ValueError("스냅샷 content 폴더가 올바르지 않습니다.")
    expected = {}
    items = stored.get("files")
    if not isinstance(items, list):
        raise ValueError("스냅샷 파일 목록이 올바르지 않습니다.")
    for item in items:
        if not isinstance(item, dict) or not isinstance(item.get("path"), str) or not isinstance(item.get("sha256"), str) or not isinstance(item.get("size"), int):
            raise ValueError("스냅샷 파일 기록이 올바르지 않습니다.")
        key = conversion._safe_relative(item["path"])
        if key in expected or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
            raise ValueError("스냅샷 파일 기록이 올바르지 않습니다.")
        expected[key] = item
    actual = set()
    for directory, dirs, files in os.walk(content, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(directory) / name
            if conversion._is_reparse(path):
                raise ValueError("변환 스냅샷에 링크가 추가됐습니다.")
        for name in files:
            path = Path(directory) / name
            key = path.relative_to(content).as_posix()
            if key not in expected or not stat.S_ISREG(path.stat().st_mode):
                raise ValueError("변환 스냅샷에 파일이 추가됐습니다.")
            actual.add(key)
            with path.open("rb") as reader:
                digest = hashlib.file_digest(reader, "sha256").hexdigest()
            if digest != expected[key]["sha256"] or path.stat().st_size != expected[key]["size"]:
                raise ValueError("변환 스냅샷 파일이 수정됐습니다. 입력을 다시 준비하세요.")
    if actual != set(expected):
        raise ValueError("변환 스냅샷 파일이 삭제됐습니다.")
    return stored, output


def compare_prepared(session, base, target, features_json=None, max_depth=10) -> dict:
    session = _session(session)
    base, base_path = _verified(base)
    target, target_path = _verified(target)
    if any(path.parent != session / "snapshots" for path in (base_path, target_path)):
        raise ValueError("현재 웹 세션에서 준비한 스냅샷끼리만 비교할 수 있습니다.")
    features_path = None
    if features_json is not None:
        if isinstance(features_json, bytes):
            text = features_json.decode("utf-8-sig")
        elif isinstance(features_json, str):
            text = features_json
        elif isinstance(features_json, dict):
            text = json.dumps(features_json, ensure_ascii=False)
        else:
            raise ValueError("기능 매핑은 JSON 문자열/bytes/object여야 합니다.")
        json.loads(text)
        features_path = session / "features" / (uuid.uuid4().hex + ".json")
        features_path.parent.mkdir(exist_ok=True)
        features_path.write_text(text, encoding="utf-8")
    return build_comparison(base_path, target_path, features_path=features_path, max_depth=max_depth)


def compare_inventory(base, target) -> dict:
    base, _ = _verified(base)
    target, _ = _verified(target)
    if base["representation"] != target["representation"]:
        raise ValueError("원본 프로젝트와 APK/IPA 구성물은 직접 파일 비교할 수 없습니다. Git 버전을 동일 설정의 패키지로 빌드하거나 두 원본 소스를 준비하세요.")
    if base["representation"] == "package_payload" and base["source"]["kind"] != target["source"]["kind"]:
        raise ValueError("APK는 APK끼리, IPA는 IPA끼리 비교하세요. 서로 다른 플랫폼 패키지는 기능 변경으로 판정할 수 없습니다.")
    if base["representation"] not in {"original_source", "package_payload"}:
        raise ValueError("지원하지 않는 스냅샷 표현입니다.")
    before = {item["path"]: item for item in base["files"]}
    after = {item["path"]: item for item in target["files"]}
    unavailable = [item["path"] for m in (base, target) for item in m.get("skipped", []) if not item.get("intentional")]
    summary = dict(added=0, deleted=0, modified=0, unchanged=0, skipped_files=0)
    changes = []
    for path in sorted(set(before) | set(after)):
        if any(path == key or path.startswith(key.rstrip("/") + "/") or key == "." for key in unavailable):
            summary["skipped_files"] += 1
            continue
        left, right = before.get(path), after.get(path)
        kind = "added" if left is None else "deleted" if right is None else (
            "unchanged" if left["sha256"] == right["sha256"] and left["size"] == right["size"] else "modified")
        summary[kind] += 1
        if kind != "unchanged":
            changes.append(dict(path=path, type=kind, change_type=kind, base=left, target=right))
    summary.update(total_changes=len(changes), affected_features=0)
    return dict(mode="inventory", schema_version=1, run_id=uuid.uuid4().hex,
        created_at=datetime.now(timezone.utc).isoformat(),
        status="incomplete" if any(m["status"] != "prepared" for m in (base, target)) else "analyzed",
        base=base["source"], target=target["source"], summary=summary, changes=changes,
        warnings=list(dict.fromkeys([*base.get("warnings", []), *target.get("warnings", [])])),
        limitations=["내용 해시·크기·상대 경로의 변경입니다. 코드 의미·기능 영향·TC·실행 결과를 확정하지 않습니다.",
                     "서명·빌드 도구·백엔드·ABI·최적화·난독화·패키징 차이도 파일 변경으로 나타날 수 있습니다.",
                     "누락 범위는 변경 판정에서 제외하며 서버/다운로드 콘텐츠 변경은 포함되지 않습니다."])


def make_snapshot_download(manifest) -> bytes:
    stored, output = _verified(manifest)
    paths = []
    for root_name in ("content", "restored"):
        root = output / root_name
        if not root.exists():
            continue
        if conversion._is_reparse(root):
            raise ValueError("다운로드 스냅샷에 링크를 사용할 수 없습니다.")
        for directory, dirs, files in os.walk(root, followlinks=False):
            for name in [*dirs, *files]:
                path = Path(directory) / name
                if conversion._is_reparse(path) or not path.resolve().is_relative_to(output):
                    raise ValueError("다운로드 스냅샷 경로가 안전하지 않습니다.")
                if name in files and not stat.S_ISREG(path.stat().st_mode):
                    raise ValueError("다운로드 스냅샷에는 일반 파일만 사용할 수 있습니다.")
            paths.extend(Path(directory) / name for name in files)
    portable = json.loads(json.dumps(stored))
    replacements = {str(output): ".", str(output / "content"): "content"}
    for key in ("path", "repository_root"):
        original = portable["source"].get(key)
        if original:
            replacements[original] = Path(original).name
    def redact(value):
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, str):
            for original, replacement in sorted(replacements.items(), key=lambda item: -len(item[0])):
                value = value.replace(original, replacement)
            return value
        return value
    portable = redact(portable)
    portable.update(output_path=".", content_root="content")
    portable["source"].pop("repository_root", None)
    if "restoration" in portable:
        portable["restoration"]["output_root"] = "restored"
        portable["restoration"].pop("tool", None)
    metadata = json.dumps(portable, ensure_ascii=False, indent=2).encode("utf-8")
    markdown = conversion._markdown(portable).encode("utf-8")
    if sum(path.stat().st_size for path in paths) + len(metadata) + len(markdown) > MAX_DOWNLOAD_BYTES:
        raise ValueError("전체 스냅샷 다운로드는 100MiB 이하만 지원합니다. manifest/보고서를 내려받으세요.")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("manifest.json", metadata)
        archive.writestr("conversion.md", markdown)
        archive.writestr("content/", b"")
        for path in sorted(paths):
            archive.write(path, path.relative_to(output).as_posix())
    data = buffer.getvalue()
    if len(data) > MAX_DOWNLOAD_BYTES:
        raise ValueError("압축된 스냅샷 다운로드 크기 제한을 초과했습니다.")
    return data
