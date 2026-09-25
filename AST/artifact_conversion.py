"""Prepare immutable input snapshots; never execute project/application code.

Local inputs and committed Git blobs retain their original bytes. APK/IPA content
is package payload, not original Java/C#/Python source. Optional JADX output
is stored separately and remains derived, potentially incomplete source.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import unicodedata
import uuid
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath


MAX_APK_MEMBERS = 100_000
# Shared package extraction limits; original constant names remain compatible.
MAX_APK_TOTAL_BYTES = 2 * 1024**3
MAX_APK_MEMBER_BYTES = 512 * 1024**2
JADX_TIMEOUT_SECONDS = 180
CHUNK_BYTES = 1024 * 1024

EXCLUDED_DIRS = {
    ".git", ".venv", "__pycache__", "node_modules",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".ipynb_checkpoints",
}
ROOT_EXCLUDED_DIRS = {".test_tmp"}
ENGINE_ROOT_CACHES = {
    "Unity": {"Library", "Temp", "Logs", "obj", "bin"},
    "Unreal": {"Binaries", "Intermediate", "DerivedDataCache", "Saved"},
    "Godot": {".godot"},
}
SOURCE_LANGUAGES = {
    ".py": "Python", ".ipynb": "Python notebook", ".cs": "C#", ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin", ".c": "C", ".h": "C/C++",
    ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++",
    ".gd": "GDScript", ".lua": "Lua", ".js": "JavaScript", ".ts": "TypeScript",
    ".ps1": "PowerShell", ".sh": "shell", ".swift": "Swift",
}
_RESERVED = {"con", "prn", "aux", "nul", *[f"com{i}" for i in "123456789¹²³"],
             *[f"lpt{i}" for i in "123456789¹²³"]}


def _safe_relative(value: str, *, allow_dot: bool = False) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("A nonempty relative path is required.")
    if allow_dot and value == ".":
        return "."
    if "\\" in value or value.startswith("/"):
        raise ValueError(f"Unsafe relative path: {value!r}")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValueError(f"Unsafe path component: {value!r}")
    for part in parts:
        if (part.endswith((".", " ")) or ":" in part or len(part) > 255
                or any(ord(c) < 32 or ord(c) == 127 or c in '<>"|?*' for c in part)
                or part.split(".", 1)[0].casefold() in _RESERVED):
            raise ValueError(f"Unsupported/unsafe portable path: {value!r}")
    return "/".join(parts)


def _is_reparse(path: Path) -> bool:
    info = path.lstat()
    return stat.S_ISLNK(info.st_mode) or bool(
        getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


def _within(path: Path, parent: Path) -> bool:
    return path == parent or parent in path.parents


def _skip(manifest: dict, path: str, reason: str, *, intentional: bool = False,
          reason_code: str = "unavailable") -> None:
    manifest["skipped"].append(dict(path=path, reason=reason, reason_code=reason_code,
                                    intentional=intentional))
    if not intentional:
        manifest["status"] = "partial"


def _excluded(path: str, *, engine_name=None, source_root=".", is_directory=False) -> bool:
    selected_parts = PurePosixPath(path).parts
    directories = selected_parts if is_directory else selected_parts[:-1]
    if any(part in EXCLUDED_DIRS or part.startswith(".venv") for part in directories):
        return True
    original_parts = ((*PurePosixPath(source_root).parts, *directories)
                      if source_root != "." else directories)
    root_caches = ROOT_EXCLUDED_DIRS | ENGINE_ROOT_CACHES.get(engine_name, set())
    return bool(original_parts and original_parts[0] in root_caches)


def _validate_export_collisions(paths: list[str]) -> None:
    """Fail before writing if distinct source paths cannot coexist portably."""
    spelling, types = {}, {}
    for key in paths:
        parts = key.split("/")
        for index in range(1, len(parts) + 1):
            part = "/".join(parts[:index])
            normalized = unicodedata.normalize("NFC", part).casefold()
            directory = index < len(parts)
            if (normalized in spelling and spelling[normalized] != part
                    or normalized in types and types[normalized] != directory):
                raise ValueError(f"Source paths collide in a portable snapshot: {key}")
            spelling[normalized], types[normalized] = part, directory


def _classification(path: str, header: bytes, *, package: bool = False) -> dict:
    suffix = PurePosixPath(path).suffix.lower()
    if package and re.fullmatch(r"classes\d*\.dex", path):
        valid = bool(re.match(rb"dex\n0\d\d\x00", header[:8]))
        return dict(category="dex_bytecode" if valid else "invalid_dex_payload",
                    language="DEX", signature_valid=valid)
    if package and path == "AndroidManifest.xml":
        kind = "binary_axml" if header.startswith(b"\x03\x00\x08\x00") else (
            "text_xml" if header.lstrip().startswith(b"<") else "unknown")
        return dict(category="android_manifest", format=kind)
    if suffix == ".so":
        return dict(category="native_binary" if header.startswith(b"\x7fELF")
                    else "native_binary_candidate", language="native")
    if suffix == ".dll":
        # PE headers alone cannot establish that a DLL contains managed CIL.
        return dict(category="assembly_candidate", signature="PE" if header[:2] == b"MZ" else "unknown")
    if suffix in SOURCE_LANGUAGES:
        return dict(category="source_code", language=SOURCE_LANGUAGES[suffix])
    if suffix in {".unity", ".prefab", ".uasset", ".umap", ".tscn", ".scn"}:
        return dict(category="scene_or_component_asset")
    if suffix == ".meta":
        return dict(category="asset_metadata")
    if suffix in {".json", ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".uproject"} or path.endswith("project.godot"):
        return dict(category="configuration")
    if package and path.startswith("assets/"):
        return dict(category="packaged_asset")
    return dict(category="asset_or_data")


def _stream_copy(reader, destination: Path, *, expected_size: int | None = None,
                 byte_limit: int | None = None) -> tuple[int, str, bytes]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    size, digest, header = 0, hashlib.sha256(), b""
    with destination.open("xb") as writer:
        while True:
            chunk = reader.read(CHUNK_BYTES)
            if not chunk:
                break
            size += len(chunk)
            if byte_limit is not None and size > byte_limit:
                raise ValueError("Decompressed file exceeds the configured size limit.")
            if len(header) < 4096:
                header += chunk[:4096 - len(header)]
            digest.update(chunk)
            writer.write(chunk)
    if expected_size is not None and size != expected_size:
        raise ValueError(f"File size mismatch: expected {expected_size}, read {size}.")
    return size, digest.hexdigest(), header


def _file_record(path: str, size: int, sha256: str, header: bytes, **extra) -> dict:
    package = extra.pop("package", False)
    return dict(path=path, size=size, sha256=sha256,
                **_classification(path, header, package=package), **extra)


def _local_paths(selected: Path, manifest: dict, *, engine_name=None,
                 source_root=".") -> list[tuple[Path, str]]:
    if selected.is_file():
        _safe_relative(selected.name)
        return [(selected, selected.name)]
    files = []
    # Explicit traversal reports omitted links/junctions rather than following.
    def visit(directory: Path) -> None:
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            _skip(manifest, directory.relative_to(selected).as_posix(), str(exc), reason_code="read_failure")
            return
        for entry in entries:
            path = Path(entry.path)
            key = path.relative_to(selected).as_posix()
            try:
                _safe_relative(key)
                if _is_reparse(path):
                    _skip(manifest, key, "Symlink/junction/reparse point was not followed.", reason_code="unsafe_link")
                elif entry.is_dir(follow_symlinks=False):
                    if _excluded(key, engine_name=engine_name, source_root=source_root, is_directory=True):
                        _skip(manifest, key, "Configured cache/generated/metadata directory excluded.",
                              intentional=True, reason_code="configured_exclusion")
                    else:
                        visit(path)
                elif entry.is_file(follow_symlinks=False):
                    files.append((path, key))
                else:
                    _skip(manifest, key, "Not a regular source file.", reason_code="special_file")
            except (OSError, ValueError) as exc:
                _skip(manifest, key, str(exc), reason_code="unreadable_or_unsafe_path")
    visit(selected)
    return files


def _fingerprint(info) -> tuple:
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns)


def _copy_local(files: list, manifest: dict, content: Path) -> None:
    for path, key in files:
        destination = content / key
        try:
            if _is_reparse(path):
                raise ValueError("Source became a link/reparse point during preparation.")
            before = path.stat()
            flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(path, flags), "rb") as reader:
                opened = os.fstat(reader.fileno())
                if _fingerprint(before) != _fingerprint(opened):
                    raise ValueError("Source changed before it could be copied.")
                size, digest, header = _stream_copy(reader, destination)
                if _fingerprint(opened) != _fingerprint(os.fstat(reader.fileno())):
                    raise ValueError("Source changed while it was being copied.")
            manifest["files"].append(_file_record(key, size, digest, header))
        except (OSError, ValueError) as exc:
            if destination.exists():
                destination.unlink()
            _skip(manifest, key, str(exc), reason_code="read_failure")


def _git_executable() -> str:
    configured = os.environ.get("QA_GIT_EXECUTABLE")
    candidates = [configured, shutil.which("git"), str(Path.home() / ".cache" / "codex-runtimes" /
        "codex-primary-runtime" / "dependencies" / "native" / "git" / "cmd" / "git.exe")]
    for candidate in candidates:
        if candidate and Path(candidate).is_file():
            return str(Path(candidate).resolve())
    raise ValueError("Git executable is unavailable; add Git to PATH or set QA_GIT_EXECUTABLE.")


def _git_env() -> dict:
    env = os.environ.copy()
    for name in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY"):
        env.pop(name, None)
    env["GIT_NO_LAZY_FETCH"] = "1"
    env["GIT_NO_REPLACE_OBJECTS"] = "1"
    env["GIT_OPTIONAL_LOCKS"] = "0"
    for name in ("GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS"):
        env.pop(name, None)
    env["GIT_LITERAL_PATHSPECS"] = "1"
    return env


def _git(git: str, repo: Path, args: list[str], *, check: bool = True) -> bytes:
    result = subprocess.run([git, "-c", f"safe.directory={repo}", "--no-pager", "-C", str(repo), *args], shell=False,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_git_env())
    if check and result.returncode:
        raise ValueError("Git read failed: " + result.stderr.decode("utf-8", "replace").strip())
    return result.stdout if result.returncode == 0 else b""


def _git_entries(git: str, repo: Path, sha: str, source_root: str) -> list[dict]:
    if source_root == ".":
        payload = _git(git, repo, ["ls-tree", "-rz", sha])
    else:
        object_name = f"{sha}:{source_root}"
        kind = _git(git, repo, ["cat-file", "-t", object_name]).strip()
        if kind == b"tree":
            payload = _git(git, repo, ["ls-tree", "-rz", object_name])
        elif kind == b"blob":
            payload = _git(git, repo, ["ls-tree", "-z", sha, "--", source_root])
        else:
            raise ValueError("Git source-root must be a committed directory or regular file.")
    result = []
    for raw in payload.split(b"\x00"):
        if not raw:
            continue
        metadata, path_bytes = raw.split(b"\t", 1)
        mode, object_kind, oid = metadata.decode("ascii").split(" ")
        path = path_bytes.decode("utf-8", "strict")
        if source_root != "." and kind == b"blob":
            path = PurePosixPath(path).name
        result.append(dict(path=path, mode=mode, object_kind=object_kind, oid=oid))
    return result


def _copy_git(git: str, repo: Path, entries: list, manifest: dict, content: Path) -> None:
    accepted = []
    for entry in entries:
        key = entry["path"]
        try:
            _safe_relative(key)
        except ValueError as exc:
            _skip(manifest, key, str(exc), reason_code="unsafe_path")
            continue
        if _excluded(key, engine_name=manifest["engine"]["name"], source_root=manifest["source"]["source_root"]):
            _skip(manifest, key, "Configured cache/generated/metadata directory excluded.",
                  intentional=True, reason_code="configured_exclusion")
        elif entry["mode"] == "120000":
            _skip(manifest, key, "Committed symlink was not followed.", reason_code="unsafe_link")
        elif entry["mode"] == "160000" or entry["object_kind"] == "commit":
            _skip(manifest, key, "Submodule content is not stored in the parent repository snapshot.", reason_code="submodule_unavailable")
        elif entry["object_kind"] != "blob":
            _skip(manifest, key, "Unsupported Git object type.", reason_code="unsupported_object")
        else:
            accepted.append(entry)
    if not accepted:
        return
    # One batch reader avoids spawning a Git process per project asset.
    process = subprocess.Popen([git, "-c", f"safe.directory={repo}", "--no-pager", "-C", str(repo), "cat-file", "--batch"], shell=False,
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=_git_env())
    try:
        for entry in accepted:
            process.stdin.write((entry["oid"] + "\n").encode("ascii"))
            process.stdin.flush()
            response = process.stdout.readline().decode("ascii").strip().split(" ")
            if len(response) != 3 or response[1] != "blob":
                raise ValueError("Git blob unavailable during snapshot export.")
            expected = int(response[2])
            remaining, digest, header = expected, hashlib.sha256(), b""
            destination = content / entry["path"]
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as writer:
                while remaining:
                    chunk = process.stdout.read(min(CHUNK_BYTES, remaining))
                    if not chunk:
                        raise ValueError("Truncated Git blob stream.")
                    remaining -= len(chunk)
                    digest.update(chunk)
                    if len(header) < 4096:
                        header += chunk[:4096 - len(header)]
                    writer.write(chunk)
            if process.stdout.read(1) != b"\n":
                raise ValueError("Malformed Git batch stream.")
            if header.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                _skip(manifest, entry["path"], "Git LFS pointer preserved; large-file payload was not fetched.", reason_code="lfs_payload_unavailable")
            manifest["files"].append(_file_record(entry["path"], expected, digest.hexdigest(), header,
                                                  git_blob=entry["oid"], git_mode=entry["mode"]))
        process.stdin.close()
        code = process.wait(timeout=30)
        if code:
            raise ValueError("Git batch export failed: " + process.stderr.read().decode("utf-8", "replace"))
    finally:
        if process.poll() is None:
            process.kill()
            process.wait()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()


def _validate_zip(archive: zipfile.ZipFile, label="Package") -> list[tuple[zipfile.ZipInfo, str]]:
    entries = archive.infolist()
    if len(entries) > MAX_APK_MEMBERS:
        raise ValueError(f"{label} exceeds the configured ZIP member-count limit.")
    total, seen, spelling, types, accepted = 0, set(), {}, {}, []
    for entry in entries:
        if entry.orig_filename != entry.filename or "\x00" in entry.orig_filename:
            raise ValueError(f"{label} contains a NUL/truncated ZIP filename.")
        key = _safe_relative(entry.filename[:-1] if entry.is_dir() else entry.filename)
        canonical = unicodedata.normalize("NFC", key).casefold()
        if canonical in seen:
            raise ValueError(f"{label} contains duplicate/case-colliding paths: {key}")
        seen.add(canonical)
        parts = key.split("/")
        for index in range(1, len(parts) + 1):
            part = "/".join(parts[:index])
            normalized = unicodedata.normalize("NFC", part).casefold()
            is_directory = index < len(parts) or entry.is_dir()
            if normalized in spelling and spelling[normalized] != part:
                raise ValueError(f"{label} contains case/Unicode-colliding path components: {key}")
            if normalized in types and types[normalized] != is_directory:
                raise ValueError(f"{label} contains file/directory path collisions: {key}")
            spelling[normalized], types[normalized] = part, is_directory
        mode = (entry.external_attr >> 16) & 0xFFFF
        file_type = stat.S_IFMT(mode)
        if file_type not in {0, stat.S_IFREG, stat.S_IFDIR} or entry.external_attr & 0x400:
            raise ValueError(f"{label} contains a link/special/reparse member: {key}")
        if entry.is_dir() and entry.file_size:
            raise ValueError(f"{label} directory member unexpectedly contains payload: {key}")
        if file_type == stat.S_IFDIR and not entry.is_dir():
            raise ValueError(f"{label} directory mode/name mismatch: {key}")
        if entry.flag_bits & 1:
            raise ValueError("Encrypted ZIP members are unsupported.")
        if entry.file_size < 0 or entry.file_size > MAX_APK_MEMBER_BYTES:
            raise ValueError(f"{label} member exceeds configured uncompressed limit: {key}")
        total += entry.file_size
        if total > MAX_APK_TOTAL_BYTES:
            raise ValueError(f"{label} exceeds the configured total uncompressed-size limit.")
        accepted.append((entry, key))
    return accepted


def _validate_apk(archive: zipfile.ZipFile) -> list[tuple[zipfile.ZipInfo, str]]:
    accepted = _validate_zip(archive, "APK")
    if not any(key == "AndroidManifest.xml" and not entry.is_dir() for entry, key in accepted):
        raise ValueError("APK has no root AndroidManifest.xml; input is not a supported APK package.")
    return accepted


def _copy_package(archive: zipfile.ZipFile, entries: list, manifest: dict, content: Path) -> None:
    total = 0
    for entry, key in entries:
        if entry.is_dir():
            (content / key).mkdir(parents=True, exist_ok=True)
            continue
        with archive.open(entry, "r") as reader:
            size, digest, header = _stream_copy(reader, content / key,
                expected_size=entry.file_size, byte_limit=MAX_APK_MEMBER_BYTES)
        total += size
        if total > MAX_APK_TOTAL_BYTES:
            raise ValueError("Actual decompressed package exceeds configured total size.")
        record = _file_record(key, size, digest, header, package=manifest["source"]["kind"] == "apk",
                              compressed_size=entry.compress_size)
        manifest["files"].append(record)
        if record.get("category") == "invalid_dex_payload":
            manifest["warnings"].append(f"{key}: DEX magic is invalid; bytecode analysis unavailable.")
            manifest["status"] = "partial"
        if manifest["source"]["kind"] == "apk" and key == "AndroidManifest.xml":
            manifest["warnings"].append(
                f"AndroidManifest.xml format={record.get('format')}; package/version/permissions "
                "were not decoded by this inventory converter.")


def _read_small(path: Path) -> str:
    if not path.is_file() or _is_reparse(path) or path.stat().st_size > 64 * 1024:
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _engine_from_markers(paths: set[str], read) -> dict:
    if "ProjectSettings/ProjectVersion.txt" in paths:
        text = read("ProjectSettings/ProjectVersion.txt")
        match = re.search(r"^m_EditorVersion:\s*(\S+)", text, re.MULTILINE)
        return dict(name="Unity", version=match.group(1) if match else None,
                    detection="project_marker", version_source="ProjectSettings/ProjectVersion.txt")
    unreal = sorted(path for path in paths if path.endswith(".uproject") and "/" not in path)
    if unreal:
        try:
            association = json.loads(read(unreal[0])).get("EngineAssociation")
        except (ValueError, AttributeError):
            association = None
        version = association if isinstance(association, str) and re.fullmatch(r"\d+(?:\.\d+)+", association) else None
        return dict(name="Unreal", version=version, association=association, detection="project_marker")
    if "project.godot" in paths:
        return dict(name="Godot", version=None, detection="project_marker")
    return dict(name=None, version=None, detection="not_identified")


def _local_engine(root: Path) -> dict:
    if not root.is_dir():
        return _engine_from_markers(set(), lambda path: "")
    paths = set()
    marker = root / "ProjectSettings" / "ProjectVersion.txt"
    try:
        parent = root / "ProjectSettings"
        if parent.exists() and not _is_reparse(parent) and marker.exists() and not _is_reparse(marker):
            paths.add("ProjectSettings/ProjectVersion.txt")
        for entry in root.iterdir():
            if not _is_reparse(entry) and entry.is_file() and (entry.suffix == ".uproject" or entry.name == "project.godot"):
                paths.add(entry.name)
        return _engine_from_markers(paths, lambda path: _read_small(root / path))
    except OSError:
        return _engine_from_markers(set(), lambda path: "")


def _git_engine(git: str, repo: Path, sha: str) -> dict:
    top = _git(git, repo, ["ls-tree", "-z", sha])
    names = {raw.split(b"\t", 1)[1].decode("utf-8", "replace") for raw in top.split(b"\x00") if raw}
    def read(path):
        size = _git(git, repo, ["cat-file", "-s", f"{sha}:{path}"], check=False).strip()
        if not size.isdigit() or int(size) > 64 * 1024:
            return ""
        return _git(git, repo, ["cat-file", "blob", f"{sha}:{path}"], check=False).decode("utf-8-sig", "replace")
    if "ProjectSettings" in names and read("ProjectSettings/ProjectVersion.txt"):
        names.add("ProjectSettings/ProjectVersion.txt")
    return _engine_from_markers(names, read)


def _prepare_jadx(tool) -> list[str] | None:
    if tool is None:
        return None
    path = Path(tool).expanduser().absolute()
    if not path.is_file() or _is_reparse(path):
        raise ValueError("JADX must be an explicit regular tool file, not a link.")
    if path.suffix.lower() == ".jar":
        java = shutil.which("java")
        if java is None:
            raise ValueError("Java is unavailable; an executable JADX JAR requires Java on PATH.")
        return [java, "-jar", str(path.resolve())]
    with path.open("rb") as reader:
        header = reader.read(4)
    if path.suffix.lower() in {".bat", ".cmd", ".ps1", ".sh"} or header.startswith(b"#!"):
        raise ValueError("JADX batch/shell scripts are unsupported; provide an executable JAR or native binary.")
    if os.name == "nt" and path.suffix.lower() not in {".exe", ".com"}:
        raise ValueError("Windows JADX tool must be a native .exe/.com or executable .jar.")
    if os.name != "nt" and not os.access(path, os.X_OK):
        raise ValueError("JADX binary is not executable.")
    return [str(path.resolve())]


def _restore_jadx(command: list[str], source: Path, manifest: dict, output: Path) -> None:
    restored = output / "restored"
    args = [*command, "--no-res", "-d", str(restored), str(source)]
    info = dict(tool=command, output_root=str(restored), status="unavailable", original_equivalence=False)
    manifest["restoration"] = info
    try:
        result = subprocess.run(args, shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                timeout=JADX_TIMEOUT_SECONDS)
        info.update(returncode=result.returncode,
                    log_tail=(result.stdout + result.stderr)[-4000:].decode("utf-8", "replace"))
        files = []
        temporary = dict(status="prepared", skipped=[])
        if restored.is_dir():
            candidates = _local_paths(restored, temporary)
            for path, key in candidates:
                if path.suffix.lower() != ".java":
                    continue
                data = path.read_bytes()
                files.append(_file_record(key, len(data), hashlib.sha256(data).hexdigest(), data[:4096]))
        info["files"] = files
        manifest["capabilities"]["restored_source"] = bool(files)
        info["status"] = "restored_candidates" if result.returncode == 0 and files else "partial" if files else "failed"
        if result.returncode or not files or temporary["status"] == "partial":
            manifest["status"] = "partial"
            manifest["warnings"].append("JADX restoration failed or was incomplete; inspect restoration log_tail/files.")
        manifest["warnings"].append("JADX Java candidates are derived from DEX; they are not guaranteed original source or AST-equivalent to Git source. Native/IL2CPP code is not restored by this step.")
    except (OSError, subprocess.TimeoutExpired) as exc:
        info.update(status="failed", error=str(exc))
        manifest["status"] = "partial"
        manifest["warnings"].append(f"Optional JADX restoration failed: {exc}")


def _markdown(manifest: dict) -> str:
    def value(item):
        return str(item).replace("`", "'").replace("\r", " ").replace("\n", " ")
    counts = Counter(item["category"] for item in manifest["files"])
    lines = ["# 입력 변환 스냅샷", "", f"- ID: {manifest['id']}",
        f"- 상태: {manifest['status']} — 선택된 표현의 준비 상태이며 실제 동작·Pass 판정이 아닙니다.",
        f"- 입력 종류: {manifest['source']['kind']}", f"- 입력: `{value(manifest['source']['path'])}`",
        f"- 표현: {manifest['representation']}", f"- 코드/패키지 루트: `{value(manifest['content_root'])}`",
        f"- 엔진: {value(manifest['engine'].get('name') or '미확인')} ({value(manifest['engine'].get('detection'))})",
        f"- 파일: {len(manifest['files'])}개 · 제외/누락: {len(manifest['skipped'])}개", ""]
    if manifest["source"].get("commit_sha"):
        lines += [f"- Git ref: {value(manifest['source']['ref'])}", f"- 고정 커밋: {manifest['source']['commit_sha']}", ""]
    lines += ["## 준비 가능한 분석", ""]
    for key, available in manifest["capabilities"].items():
        lines.append(f"- {key}: {'가능' if available else '미지원/미준비'}")
    lines += ["", "## 파일 구성", ""]
    lines += [f"- {category}: {count}개" for category, count in sorted(counts.items())]
    lines += ["", "## 해석 범위", "", "원본 프로젝트/앱 코드는 실행하지 않았습니다. 파일별 SHA-256과 크기는 manifest.json에 기록했습니다.",
        "APK/IPA content는 패키지 구성물입니다. 컴파일·난독화·스트리핑·빌드 설정을 거친 결과이며 Git 원본과의 동일성을 증명하지 않습니다.",
        "씬·프리팹·설정·에셋은 목록과 해시만 준비했습니다. 엔진 의미 분석, 바이너리 XML 해석, 네이티브 복원, 제품 기능·TC 확정은 별도 단계입니다.",
        "비교하려는 버전의 엔진/SDK/백엔드/ABI/빌드 설정과 매핑·심볼 자료를 함께 보존해야 합니다.",
        "실패 시 이 호출이 새로 만든 임시 출력 폴더만 소유 marker와 절대경로를 확인한 후 정리합니다.", "", "## 확인 사항", ""]
    lines += [f"- {value(warning)}" for warning in manifest["warnings"]]
    if manifest["skipped"]:
        lines += ["", "## 제외/누락", ""]
        lines += [f"- `{value(item['path'])}`: {value(item['reason'])} ({'설정된 제외' if item['intentional'] else '불완전 범위'})"
                  for item in manifest["skipped"]]
    if manifest.get("package", {}).get("applications"):
        lines += ["", "## IPA 앱 메타데이터", ""]
        for app in manifest["package"]["applications"]:
            lines += [f"- 번들: `{value(app['bundle_path'])}`", f"  - ID: {value(app.get('bundle_identifier'))}",
                      f"  - 버전: {value(app.get('version'))} · 빌드: {value(app.get('build'))}",
                      f"  - 실행 파일: {value(app.get('executable_path'))} · 서명/설치/실행 여부는 검증하지 않음"]
    return "\n".join(lines).rstrip() + "\n"


def _cleanup_new_output(output: Path, expected: Path, token: str) -> None:
    if output.resolve() != expected or _is_reparse(output):
        raise RuntimeError("Failed output cleanup refused: resolved path/link no longer matches created output.")
    marker = output / ".conversion-in-progress"
    if not marker.is_file() or _is_reparse(marker) or marker.read_text(encoding="ascii") != token:
        raise RuntimeError("Failed output cleanup refused: output ownership marker is missing/changed.")
    # The exact absolute target is verified above; only this newly created tree
    # is removed, never a source path or a computed ancestor.
    shutil.rmtree(output)


def convert_input(source: Path, kind="auto", output=None, ref=None,
                  source_root=".", jadx=None) -> dict:
    """Prepare an isolated new directory and return its provenance manifest.

    ``source_root`` is portable relative syntax ('.' or slash-separated path).
    For Git it is relative to the repository root; for local it is relative to
    the given directory. Package source_root selection is intentionally unsupported.
    Intentional cache exclusions retain prepared status; inaccessible source,
    links, submodules and missing LFS payloads produce partial snapshots.
    """
    if kind not in {"auto", "local", "engine", "git", "apk", "ipa"}:
        raise ValueError("kind must be auto/local/engine/git/apk/ipa.")
    raw_source = Path(source).expanduser().absolute()
    if not raw_source.exists() or _is_reparse(raw_source):
        raise ValueError("Source must exist and must not be a symlink/junction/reparse point.")
    source = raw_source.resolve()
    if not source.is_dir() and not source.is_file():
        raise ValueError("Source must be a regular file or directory.")
    source_root = _safe_relative(source_root, allow_dot=True)
    if ref is not None and kind != "git":
        raise ValueError("ref is only accepted for explicit kind=git; auto never chooses Git history.")
    if kind == "auto":
        kind = source.suffix.lower()[1:] if source.is_file() and source.suffix.lower() in {".apk", ".ipa"} else (
            "engine" if source.is_dir() and _local_engine(source)["name"] else "local")
    if kind == "engine" and not source.is_dir():
        raise ValueError("Engine input must be a project directory.")
    if kind in {"apk", "ipa"} and (not source.is_file() or source.suffix.lower() != f".{kind}"):
        raise ValueError(f"{kind.upper()} input must be a regular .{kind} file.")
    if kind in {"apk", "ipa"} and source_root != ".":
        raise ValueError("Package source-root selection is unsupported; preserve the full package inventory.")
    if jadx is not None and kind != "apk":
        raise ValueError("JADX is supported only for APK conversion.")
    command = _prepare_jadx(jadx)
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8]
    requested = Path(output).expanduser().absolute() if output is not None else (
        Path(__file__).resolve().parent / "reports" / "conversion" / run_id)
    if requested.exists() or requested.is_symlink():
        raise ValueError("Conversion output must be a new folder; existing output is never overwritten.")
    output = requested.resolve()
    if output == source or (source.is_dir() and _within(output, source)):
        raise ValueError("Output must be outside the source directory; choose an explicit separate output folder.")
    manifest = dict(schema_version=1, snapshot_type="qa_conversion", id=run_id,
        created_at=now.isoformat(), status="prepared", output_path=str(output),
        content_root=str(output / "content"), source=dict(kind=kind, path=str(source), is_file=source.is_file(), ref=None,
            commit_sha=None, source_root=source_root), representation="package_payload" if kind in {"apk", "ipa"} else "original_source",
        engine=dict(name=None, version=None, detection="not_identified"), files=[], skipped=[], warnings=[],
        capabilities=dict(python_ast=False, original_source=kind not in {"apk", "ipa"}, package_inventory=kind in {"apk", "ipa"}, restored_source=False),
        failure_cleanup="Remove only the newly created provisional output after verifying its ownership marker, exact absolute path and non-reparse status.")
    selected, git, entries, archive, apk_before, ipa_bundles = source, None, None, None, None, None
    try:
        if kind == "git":
            if not source.is_dir():
                raise ValueError("Git input must be a local repository directory.")
            git = _git_executable()
            bare = _git(git, source, ["rev-parse", "--is-bare-repository"]).strip() == b"true"
            root_args = ["rev-parse", "--absolute-git-dir"] if bare else ["rev-parse", "--show-toplevel"]
            repo = Path(_git(git, source, root_args).decode("utf-8", "strict").strip()).resolve()
            if _within(output, repo):
                raise ValueError("Git conversion output must be outside the repository.")
            requested_ref = "HEAD" if ref is None else ref
            if not isinstance(requested_ref, str) or not requested_ref or "\x00" in requested_ref:
                raise ValueError("A nonempty Git commit ref is required.")
            sha = _git(git, repo, ["rev-parse", "--verify", "--end-of-options", f"{requested_ref}^{{commit}}"])
            sha = sha.decode("ascii").strip()
            if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", sha):
                raise ValueError("Git ref did not resolve to exactly one commit SHA.")
            manifest["source"].update(repository_root=str(repo), ref=requested_ref, commit_sha=sha)
            entries = _git_entries(git, repo, sha, source_root)
            manifest["source"]["is_file"] = False
            manifest["source"]["selected_is_file"] = (
                source_root != "." and _git(git, repo, ["cat-file", "-t", f"{sha}:{source_root}"]).strip() == b"blob")
            manifest["engine"] = _git_engine(git, repo, sha)
            portable_paths = []
            for entry in entries:
                if entry["object_kind"] == "blob" and entry["mode"] != "120000" and not _excluded(entry["path"], engine_name=manifest["engine"]["name"], source_root=source_root):
                    try:
                        portable_paths.append(_safe_relative(entry["path"]))
                    except ValueError:
                        pass  # _copy_git reports the unsupported path as skipped.
            _validate_export_collisions(portable_paths)
            manifest["warnings"].append("Only committed raw Git blobs at the fixed SHA are exported. Index, uncommitted and untracked working-tree changes are excluded; no checkout/pull/fetch or filters were run.")
        elif kind in {"apk", "ipa"}:
            apk_before = source.stat()
            digest = hashlib.sha256()
            with source.open("rb") as reader:
                for chunk in iter(lambda: reader.read(CHUNK_BYTES), b""):
                    digest.update(chunk)
            manifest["source"]["sha256"] = digest.hexdigest()
            archive = zipfile.ZipFile(source, "r")
            if kind == "apk":
                entries = _validate_apk(archive)
            else:
                from ipa_support import validate_ipa_layout
                entries = _validate_zip(archive, "IPA")
                ipa_bundles = validate_ipa_layout(entries)
            manifest["warnings"].append(f"{kind.upper()} payload extraction/inventory only. Compiled binaries are not original source and no AST equivalence to Git is established.")
            if kind == "ipa":
                manifest["restoration"] = dict(status="unsupported", original_equivalence=False)
                manifest["warnings"].append("IPA Swift/Objective-C/native source restoration, decryption, signature verification, installation and execution are not implemented.")
            elif command is None:
                manifest["restoration"] = dict(status="unavailable", original_equivalence=False)
                manifest["warnings"].append("Code restoration is unavailable: no explicit JADX tool supplied. Native/IL2CPP and managed assembly restoration are not implemented.")
        else:
            if source.is_file() and source_root != ".":
                raise ValueError("source-root cannot be used with a standalone local source file.")
            if source.is_dir() and source_root != ".":
                selected = source
                for part in PurePosixPath(source_root).parts:
                    selected /= part
                    if not selected.exists() or _is_reparse(selected):
                        raise ValueError("Local source-root must exist and cannot traverse links/junctions.")
                selected = selected.resolve()
                if not _within(selected, source):
                    raise ValueError("source-root escaped the local input directory.")
            if not selected.is_dir() and not selected.is_file():
                raise ValueError("Local source-root must be a regular source file or directory.")
            manifest["engine"] = _local_engine(source)
            entries = _local_paths(selected, manifest, engine_name=manifest["engine"]["name"], source_root=source_root)
            _validate_export_collisions([key for path, key in entries])
            manifest["source"]["selected_is_file"] = selected.is_file()
            manifest["warnings"].append("Local original bytes are copied without execution; local edits/untracked files are included. Individual files are checked for changes during copying; this is not an atomic whole-project filesystem snapshot.")
            if kind == "engine" and not manifest["engine"]["name"]:
                manifest["warnings"].append("Engine type/version could not be identified from supported project markers.")

        # All metadata validation precedes creation. This new directory is a
        # provisional staging output until its final manifest is written.
        output.parent.mkdir(parents=True, exist_ok=True)
        output.mkdir(exist_ok=False)
        token = uuid.uuid4().hex
        marker = output / ".conversion-in-progress"
        try:
            marker.write_text(token, encoding="ascii")
        except Exception:
            output.rmdir()  # Fresh, verified empty folder; no recursive removal.
            raise
        try:
            content = output / "content"
            content.mkdir()
            if kind == "git":
                _copy_git(git, repo, entries, manifest, content)
            elif kind in {"apk", "ipa"}:
                _copy_package(archive, entries, manifest, content)
                names = {item["path"] for item in manifest["files"]}
                if any(path.endswith(("/libunity.so", "/libil2cpp.so")) for path in names):
                    manifest["engine"] = dict(name="Unity", version=None, detection="inferred_package_signatures",
                        scripting_backend="IL2CPP_candidate" if any(path.endswith("/libil2cpp.so") for path in names) else "unknown")
                    manifest["warnings"].append("Unity package signature is an inference; engine version and original project/commit are not verified.")
                if command is not None:
                    _restore_jadx(command, source, manifest, output)
                if kind == "ipa":
                    from ipa_support import inspect_ipa
                    inspect_ipa(content, manifest, ipa_bundles)
                if _fingerprint(apk_before) != _fingerprint(source.stat()):
                    raise ValueError("Package changed during conversion; prepared payload cannot be tied to its recorded hash.")
            else:
                _copy_local(entries, manifest, content)
                if source.is_file() and manifest["files"]:
                    manifest["source"]["sha256"] = manifest["files"][0]["sha256"]
            manifest["files"].sort(key=lambda item: item["path"])
            manifest["skipped"].sort(key=lambda item: (item["path"], item["reason_code"]))
            if kind not in {"apk", "ipa"}:
                languages = {item.get("language") for item in manifest["files"] if item["category"] == "source_code"}
                manifest["capabilities"]["python_ast"] = bool(languages & {"Python", "Python notebook"})
                unsupported = sorted(languages - {"Python", "Python notebook"})
                if unsupported:
                    manifest["warnings"].append("Current AST comparison supports Python only; other source languages were preserved but not parsed: " + ", ".join(unsupported))
            if not manifest["files"]:
                manifest["warnings"].append("No files were exported within the selected source scope.")
            manifest["warnings"] = list(dict.fromkeys(manifest["warnings"]))
            (output / "conversion.md").write_text(_markdown(manifest), encoding="utf-8")
            (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            marker.unlink()
            return manifest
        except Exception as exc:
            try:
                _cleanup_new_output(output, output, token)
            except Exception as cleanup_exc:
                raise RuntimeError(f"Conversion failed: {exc}; newly created output retained because cleanup failed: {cleanup_exc}") from exc
            raise
    finally:
        if archive is not None:
            archive.close()
