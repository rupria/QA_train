"""Atomic local installation and verification of public QA Train rule packs."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import uuid
import zipfile

from .paths import app_data_root


PACK_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
MAX_FILES = 8
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MARKER_NAME = ".qa-rule-pack.json"
CURRENT_NAME = "current.json"


@dataclass(frozen=True)
class RulePackStatus:
    state: str
    path: str | None
    pack_version: str | None
    rule_count: int = 0
    semantic_ready: bool = False
    message: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class RulePackStore:
    def __init__(self, root: Path | None = None) -> None:
        self.root = Path(root or app_data_root() / "rules").resolve()

    def status(self) -> RulePackStatus:
        current_path = self.root / CURRENT_NAME
        if not current_path.is_file():
            return RulePackStatus("missing", None, None, message="no rule pack is installed")
        try:
            current = json.loads(current_path.read_text(encoding="utf-8"))
            version = _pack_version(current.get("pack_version"))
            target = self._target(version)
            marker = json.loads((target / MARKER_NAME).read_text(encoding="utf-8"))
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            _validate_manifest(manifest)
            if marker.get("manifest_sha256") != _sha256(target / "manifest.json"):
                raise ValueError("installed manifest changed")
            if marker.get("pack_version") != version or manifest["pack_version"] != version:
                raise ValueError("installed pack version mismatch")
            _validate_files(target, manifest)
            return RulePackStatus(
                "ready",
                str(target),
                version,
                int(manifest["rule_count"]),
                manifest["state"] == "semantic_ready",
            )
        except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            return RulePackStatus("invalid", None, None, message=f"invalid installed rule pack: {exc}")

    def install(self, archive_path: Path) -> RulePackStatus:
        archive = Path(archive_path).resolve()
        if not archive.is_file():
            raise FileNotFoundError(f"rule pack archive is missing: {archive}")
        self.root.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(archive) as bundle:
            entries = _validate_archive(bundle)
            manifest_bytes = bundle.read("manifest.json")
            try:
                manifest = json.loads(manifest_bytes.decode("utf-8"))
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("rule pack manifest is not valid UTF-8 JSON") from exc
            _validate_manifest(manifest)
            expected = {"manifest.json", *manifest["files"].keys()}
            if set(entries) != expected:
                raise ValueError("rule pack archive contents do not match its manifest")
            version = manifest["pack_version"]
            target = self._target(version)
            if target.exists():
                existing = self._status_for_target(target, version)
                if existing.state != "ready":
                    raise RuntimeError("rule pack version already exists but is invalid")
                marker = json.loads((target / MARKER_NAME).read_text(encoding="utf-8"))
                incoming_manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
                if marker.get("manifest_sha256") != incoming_manifest_sha256:
                    raise RuntimeError("a different rule pack already uses this version")
                self._write_current(version)
                return self.status()
            staging = self.root / f".partial-rule-pack-{uuid.uuid4().hex}"
            try:
                staging.mkdir()
                for name in entries:
                    data = bundle.read(name)
                    destination = staging / name
                    destination.write_bytes(data)
                _validate_files(staging, manifest)
                marker = {
                    "schema_version": 1,
                    "pack_version": version,
                    "archive_sha256": _sha256(archive),
                    "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
                }
                (staging / MARKER_NAME).write_text(
                    json.dumps(marker, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                staging.rename(target)
            except Exception:
                _remove_staging(self.root, staging)
                raise
        self._write_current(version)
        return self.status()

    def pack_path(self) -> Path:
        status = self.status()
        if status.state != "ready" or not status.path:
            raise RuntimeError(status.message or "rule pack is not ready")
        return Path(status.path)

    def _target(self, version: str) -> Path:
        target = (self.root / version).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("rule pack target escapes the rule root")
        return target

    def _status_for_target(self, target: Path, version: str) -> RulePackStatus:
        try:
            marker = json.loads((target / MARKER_NAME).read_text(encoding="utf-8"))
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            _validate_manifest(manifest)
            if marker.get("pack_version") != version or manifest["pack_version"] != version:
                raise ValueError("version mismatch")
            if marker.get("manifest_sha256") != _sha256(target / "manifest.json"):
                raise ValueError("manifest hash mismatch")
            _validate_files(target, manifest)
            return RulePackStatus("ready", str(target), version, int(manifest["rule_count"]))
        except Exception as exc:
            return RulePackStatus("invalid", str(target), version, message=str(exc))

    def _write_current(self, version: str) -> None:
        temporary = self.root / f".{CURRENT_NAME}.{uuid.uuid4().hex}.tmp"
        temporary.write_text(
            json.dumps({"schema_version": 1, "pack_version": version}, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.root / CURRENT_NAME)


def _validate_archive(bundle: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    entries: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in bundle.infolist():
        path = PurePosixPath(info.filename)
        if info.is_dir() or path.is_absolute() or len(path.parts) != 1 or ".." in path.parts:
            raise ValueError(f"unsafe rule pack entry: {info.filename!r}")
        if info.filename in entries:
            raise ValueError(f"duplicate rule pack entry: {info.filename}")
        entries[info.filename] = info
        total += info.file_size
    if not entries or len(entries) > MAX_FILES or total > MAX_TOTAL_BYTES:
        raise ValueError("rule pack archive exceeds the allowed file or size limit")
    if "manifest.json" not in entries or entries["manifest.json"].file_size > 128 * 1024:
        raise ValueError("rule pack manifest is missing or too large")
    return entries


def _validate_manifest(manifest: dict[str, object]) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("rule pack manifest schema_version must be 1")
    _pack_version(manifest.get("pack_version"))
    if manifest.get("state") not in {"metadata_only", "semantic_ready"}:
        raise ValueError("unsupported rule pack state")
    if not isinstance(manifest.get("rule_count"), int) or manifest["rule_count"] <= 0:
        raise ValueError("rule_count must be positive")
    files = manifest.get("files")
    if not isinstance(files, dict) or not {"rules.sqlite", "sources.json"}.issubset(files):
        raise ValueError("rule pack files are incomplete")
    if manifest["state"] == "semantic_ready" and "embeddings.npy" not in files:
        raise ValueError("semantic rule pack is missing embeddings.npy")
    for name, metadata in files.items():
        if name not in {"rules.sqlite", "sources.json", "embeddings.npy"}:
            raise ValueError(f"unsupported rule pack file: {name}")
        if not isinstance(metadata, dict) or not SHA256.fullmatch(str(metadata.get("sha256", ""))):
            raise ValueError(f"invalid checksum metadata for {name}")
        if not isinstance(metadata.get("size_bytes"), int) or metadata["size_bytes"] < 0:
            raise ValueError(f"invalid size metadata for {name}")


def _validate_files(root: Path, manifest: dict[str, object]) -> None:
    for name, metadata in manifest["files"].items():
        path = root / name
        if not path.is_file() or path.stat().st_size != metadata["size_bytes"]:
            raise ValueError(f"rule pack file size mismatch: {name}")
        if _sha256(path) != metadata["sha256"]:
            raise ValueError(f"rule pack checksum mismatch: {name}")


def _pack_version(value: object) -> str:
    if not isinstance(value, str) or not PACK_VERSION.fullmatch(value):
        raise ValueError(f"invalid rule pack version: {value!r}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _remove_staging(root: Path, staging: Path) -> None:
    if not staging.exists():
        return
    resolved = staging.resolve()
    if not resolved.is_relative_to(root) or not staging.name.startswith(".partial-rule-pack-"):
        raise RuntimeError(f"refusing to remove unsafe rule pack staging directory: {resolved}")
    shutil.rmtree(staging)
