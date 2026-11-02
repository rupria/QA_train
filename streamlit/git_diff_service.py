"""Git-compatible source diff evidence without executing project code."""
from __future__ import annotations

import os
import re
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


GIT_DIFF_TIMEOUT_SECONDS = 60
MAX_NAME_STATUS_BYTES = 4 * 1024**2
MAX_PATCH_BYTES = 8 * 1024**2
MAX_FILE_PATCH_BYTES = 512 * 1024

_TYPE_BY_STATUS = {
    "A": "added",
    "D": "deleted",
    "M": "modified",
    "R": "renamed",
    "C": "copied",
    "T": "modified",
    "U": "modified",
    "X": "modified",
    "B": "modified",
}


def _git_environment(base_environment: dict) -> dict:
    """Ignore machine Git configuration while retaining the caller's safe env."""
    env = base_environment.copy()
    env.update(
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
        GIT_CONFIG_COUNT="0",
        GIT_ATTR_NOSYSTEM="1",
        GIT_TERMINAL_PROMPT="0",
        GIT_PAGER="cat",
    )
    for name in (
        "GIT_CONFIG_PARAMETERS",
        "GIT_EXTERNAL_DIFF",
        "GIT_DIFF_OPTS",
        "GIT_ASKPASS",
        "SSH_ASKPASS",
    ):
        env.pop(name, None)
    return env


def _run_diff(
    git: str,
    base_root: Path,
    target_root: Path,
    env: dict,
    *options: str,
) -> bytes:
    args = [
        git,
        "--no-pager",
        "-c",
        "core.autocrlf=false",
        "-c",
        "core.safecrlf=false",
        "-c",
        "core.quotepath=false",
        "diff",
        "--no-index",
        "--no-ext-diff",
        "--no-textconv",
        "--ignore-cr-at-eol",
        "--find-renames",
        *options,
        "--",
        str(base_root),
        str(target_root),
    ]
    try:
        result = subprocess.run(
            args,
            shell=False,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=GIT_DIFF_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired as exc:
        raise ValueError("Git 파일 비교 제한 시간이 지났습니다.") from exc
    if result.returncode not in {0, 1}:
        message = result.stderr[-3000:].decode("utf-8", "replace").strip()
        raise ValueError("Git 파일 비교에 실패했습니다: " + (message or "알 수 없는 오류"))
    return result.stdout


def _portable_root(path: Path) -> str:
    return str(path.resolve()).replace("\\", "/").rstrip("/")


def _relative_path(raw: bytes, root: Path) -> str:
    try:
        value = raw.decode("utf-8", "strict").replace("\\", "/")
    except UnicodeError as exc:
        raise ValueError("Git 변경 파일 경로를 UTF-8로 표시할 수 없습니다.") from exc
    prefix = _portable_root(root)
    if not value.startswith(prefix + "/"):
        raise ValueError("Git 변경 파일이 준비된 스냅샷 범위를 벗어났습니다.")
    relative = value[len(prefix) + 1 :]
    if not relative or relative.startswith("../"):
        raise ValueError("Git 변경 파일의 상대 경로가 올바르지 않습니다.")
    return relative


def _parse_name_status(payload: bytes, base_root: Path, target_root: Path) -> list[dict]:
    fields = payload.split(b"\x00")
    if fields and fields[-1] == b"":
        fields.pop()
    changes, index = [], 0
    while index < len(fields):
        try:
            status = fields[index].decode("ascii", "strict")
        except UnicodeError as exc:
            raise ValueError("Git 변경 상태 형식이 올바르지 않습니다.") from exc
        index += 1
        if not re.fullmatch(r"[A-Z][0-9]*", status) or status[0] not in _TYPE_BY_STATUS:
            raise ValueError(f"지원하지 않는 Git 변경 상태입니다: {status!r}")
        code = status[0]
        needed = 2 if code in {"R", "C"} else 1
        if index + needed > len(fields):
            raise ValueError("Git 변경 파일 목록이 중간에 끝났습니다.")
        raw_paths = fields[index : index + needed]
        index += needed
        if code in {"R", "C"}:
            base_path = _relative_path(raw_paths[0], base_root)
            target_path = _relative_path(raw_paths[1], target_root)
        elif code == "A":
            base_path, target_path = None, _relative_path(raw_paths[0], target_root)
        elif code == "D":
            base_path, target_path = _relative_path(raw_paths[0], base_root), None
        else:
            base_path = _relative_path(raw_paths[0], base_root)
            target_path = base_path
        changes.append(
            {
                "status": status,
                "type": _TYPE_BY_STATUS[code],
                "base_path": base_path,
                "target_path": target_path,
                "path": target_path or base_path,
            }
        )
    return changes


def _patch_sections(payload: bytes) -> list[str]:
    try:
        text = payload.decode("utf-8", "strict")
    except UnicodeError as exc:
        raise ValueError("Git diff 결과를 UTF-8로 표시할 수 없습니다.") from exc
    return [item for item in re.split(r"(?=^diff --git )", text, flags=re.MULTILINE) if item]


def _scrub_patch(section: str, base_root: Path, target_root: Path) -> str:
    base = _portable_root(base_root)
    target = _portable_root(target_root)
    header_prefixes = (
        "diff --git ",
        "--- ",
        "+++ ",
        "rename from ",
        "rename to ",
        "copy from ",
        "copy to ",
        "Binary files ",
    )
    cleaned = []
    for line in section.splitlines(keepends=True):
        if line.startswith(header_prefixes):
            line = line.replace(base, "a").replace(target, "b")
            line = line.replace(base.replace("/", "\\"), "a").replace(
                target.replace("/", "\\"), "b"
            )
        cleaned.append(line)
    return "".join(cleaned)


def _line_counts(patch: str) -> tuple[int, int]:
    additions = deletions = 0
    in_hunk = False
    for line in patch.splitlines():
        if line.startswith("@@"):
            in_hunk = True
        elif in_hunk and line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif in_hunk and line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return additions, deletions


def build_git_diff(
    base_root: Path,
    target_root: Path,
    before_files: list[dict],
    after_files: list[dict],
    *,
    git: str,
    environment_factory: Callable[[], dict],
) -> dict:
    """Return Git status plus bounded per-file unified patches.

    The input roots must already be immutable, verified snapshots. Machine Git
    configuration, external diff programs and text conversion are disabled.
    """
    base_root, target_root = base_root.resolve(), target_root.resolve()
    env = _git_environment(environment_factory())
    statuses = _run_diff(git, base_root, target_root, env, "--name-status", "-z")
    if len(statuses) > MAX_NAME_STATUS_BYTES:
        raise ValueError("변경 파일 목록이 표시 제한을 초과했습니다.")
    changes = _parse_name_status(statuses, base_root, target_root)

    before = {item["path"]: item for item in before_files}
    after = {item["path"]: item for item in after_files}
    touched_base, touched_target = set(), set()
    summary = {"added": 0, "deleted": 0, "modified": 0, "renamed": 0, "copied": 0}
    for change in changes:
        base_path, target_path = change["base_path"], change["target_path"]
        if base_path:
            touched_base.add(base_path)
        if target_path:
            touched_target.add(target_path)
        change["base"] = before.get(base_path) if base_path else None
        change["target"] = after.get(target_path) if target_path else None
        if ((base_path and change["base"] is None)
                or (target_path and change["target"] is None)):
            raise ValueError("Git 변경 목록과 스냅샷 manifest가 일치하지 않습니다.")
        summary[change["type"]] += 1

    patch_payload = _run_diff(git, base_root, target_root, env, "--no-prefix", "--unified=3")
    details = {}
    if len(patch_payload) <= MAX_PATCH_BYTES:
        sections = _patch_sections(patch_payload)
        if len(sections) != len(changes):
            raise ValueError("Git 변경 파일 목록과 diff 구간 수가 일치하지 않습니다.")
        for change, section in zip(changes, sections):
            patch = _scrub_patch(section, base_root, target_root)
            additions, deletions = _line_counts(patch)
            change.update(additions=additions, deletions=deletions)
            detail = {"additions": additions, "deletions": deletions}
            if len(patch.encode("utf-8")) > MAX_FILE_PATCH_BYTES:
                detail["note"] = "이 파일의 diff가 512KiB를 넘어 상세 표시에서 제외했습니다."
            elif "GIT binary patch" in patch or "Binary files " in patch:
                detail.update(note="바이너리 파일은 변경 사실만 표시합니다.", binary=True)
            else:
                detail["diff"] = patch
            details[change["path"]] = detail
    else:
        for change in changes:
            change.update(additions=0, deletions=0)
            details[change["path"]] = {
                "note": "전체 diff가 8MiB를 넘어 파일 목록만 표시합니다."
            }

    unchanged = (set(before) & set(after)) - touched_base - touched_target
    summary.update(
        unchanged=len(unchanged),
        total_changes=len(changes),
        affected_features=0,
        additions=sum(item.get("additions", 0) for item in changes),
        deletions=sum(item.get("deletions", 0) for item in changes),
        skipped_files=0,
    )
    return {
        "mode": "git_diff",
        "schema_version": 1,
        "run_id": uuid.uuid4().hex,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "analyzed",
        "summary": summary,
        "changes": changes,
        "details": details,
        "warnings": [],
        "limitations": [
            "Git의 --no-index diff 결과입니다. CRLF/LF 줄바꿈만 다른 파일은 변경에서 제외합니다.",
            "바이너리 파일은 변경 여부만 표시하며 코드 내용이나 기능 영향을 해석하지 않습니다.",
            "파일 변경은 근거이며 실제 실행 결과·제품 기능·테스트 통과를 확정하지 않습니다.",
        ],
    }
