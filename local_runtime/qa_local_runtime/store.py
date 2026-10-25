"""Atomic first-run model installation into a user-local cache."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shutil
import time
from typing import Callable
import uuid

from .manifest import ModelManifest, ModelSpec, load_manifest
from .paths import app_data_root


Downloader = Callable[..., str]
MARKER_NAME = ".qa-model.json"
LOCK_STALE_SECONDS = 6 * 60 * 60


@dataclass(frozen=True)
class ModelStatus:
    key: str
    state: str
    path: str
    model_id: str
    revision: str
    installed_at: str | None = None
    file_count: int = 0
    size_bytes: int = 0
    message: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class ModelStore:
    def __init__(
        self,
        root: Path | None = None,
        manifest: ModelManifest | None = None,
        downloader: Downloader | None = None,
    ) -> None:
        self.root = Path(root or app_data_root() / "models").resolve()
        self.manifest = manifest or load_manifest()
        self.downloader = downloader or _snapshot_download

    def status(self, key: str = "embedding") -> ModelStatus:
        spec = self.manifest.model(key)
        target = self._target(spec)
        marker = target / MARKER_NAME
        if marker.is_file():
            try:
                data = json.loads(marker.read_text(encoding="utf-8"))
                self._validate_marker(spec, target, data)
                return ModelStatus(
                    key=key,
                    state="ready",
                    path=str(target),
                    model_id=spec.model_id,
                    revision=spec.revision,
                    installed_at=data["installed_at"],
                    file_count=data["file_count"],
                    size_bytes=data["size_bytes"],
                )
            except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                return self._status(spec, "invalid", f"invalid completed model: {exc}")
        if self._lock_path(spec).exists():
            return self._status(spec, "downloading", "another process is downloading this model")
        if target.exists():
            return self._status(spec, "invalid", "model directory exists without a valid completion marker")
        return self._status(spec, "missing", "model will be downloaded on first use")

    def ensure(self, key: str = "embedding") -> ModelStatus:
        spec = self.manifest.model(key)
        current = self.status(key)
        if current.state == "ready":
            return current
        if current.state == "invalid":
            raise RuntimeError(current.message)
        self.root.mkdir(parents=True, exist_ok=True)
        lock = self._acquire_lock(spec)
        staging = self.root / f".partial-{spec.local_dir}-{uuid.uuid4().hex}"
        try:
            current = self.status(key)
            if current.state == "ready":
                return current
            if self._target(spec).exists():
                raise RuntimeError("model target appeared without a valid completion marker")
            self._cleanup_stale_staging(spec)
            staging.mkdir()
            self.downloader(
                repo_id=spec.model_id,
                revision=spec.revision,
                local_dir=str(staging),
                allow_patterns=list(spec.allow_patterns),
            )
            file_count, size_bytes, required_file_sizes = self._validate_download(spec, staging)
            installed_at = datetime.now(timezone.utc).isoformat()
            marker = {
                "schema_version": 1,
                "key": key,
                "model_id": spec.model_id,
                "revision": spec.revision,
                "installed_at": installed_at,
                "file_count": file_count,
                "size_bytes": size_bytes,
                "required_file_sizes": required_file_sizes,
            }
            (staging / MARKER_NAME).write_text(
                json.dumps(marker, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            staging.rename(self._target(spec))
            return self.status(key)
        except Exception:
            self._remove_staging(staging)
            raise
        finally:
            try:
                lock.unlink(missing_ok=True)
            except OSError:
                pass

    def model_path(self, key: str = "embedding") -> Path:
        status = self.status(key)
        if status.state != "ready":
            raise RuntimeError(status.message or f"model is not ready: {status.state}")
        return Path(status.path)

    def _status(self, spec: ModelSpec, state: str, message: str) -> ModelStatus:
        return ModelStatus(
            key=spec.key,
            state=state,
            path=str(self._target(spec)),
            model_id=spec.model_id,
            revision=spec.revision,
            message=message,
        )

    def _target(self, spec: ModelSpec) -> Path:
        target = (self.root / spec.local_dir).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("model target escapes the model root")
        return target

    def _lock_path(self, spec: ModelSpec) -> Path:
        return self.root / f".{spec.local_dir}.download.lock"

    def _acquire_lock(self, spec: ModelSpec) -> Path:
        lock = self._lock_path(spec)
        if lock.exists() and time.time() - lock.stat().st_mtime > LOCK_STALE_SECONDS:
            lock.unlink()
        try:
            descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError("model download is already running") from exc
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump({"pid": os.getpid(), "started_at": datetime.now(timezone.utc).isoformat()}, stream)
        return lock

    def _validate_download(self, spec: ModelSpec, root: Path) -> tuple[int, int, dict[str, int]]:
        resolved_root = root.resolve()
        required_file_sizes: dict[str, int] = {}
        for relative in spec.required_files:
            candidate = (root / Path(*relative.split("/"))).resolve()
            if not candidate.is_relative_to(resolved_root) or not candidate.is_file():
                raise RuntimeError(f"downloaded model is missing required file: {relative}")
            required_file_sizes[relative] = candidate.stat().st_size
        files = [path for path in root.rglob("*") if path.is_file()]
        return len(files), sum(path.stat().st_size for path in files), required_file_sizes

    def _validate_marker(self, spec: ModelSpec, target: Path, data: dict) -> None:
        if data.get("schema_version") != 1:
            raise ValueError("unsupported completion marker schema")
        if data.get("key") != spec.key or data.get("model_id") != spec.model_id:
            raise ValueError("completion marker model identity mismatch")
        if data.get("revision") != spec.revision:
            raise ValueError("completion marker revision mismatch")
        if not isinstance(data.get("installed_at"), str):
            raise ValueError("completion marker installed_at is missing")
        if not isinstance(data.get("file_count"), int) or not isinstance(data.get("size_bytes"), int):
            raise ValueError("completion marker size metadata is invalid")
        recorded_sizes = data.get("required_file_sizes")
        if not isinstance(recorded_sizes, dict):
            raise ValueError("completion marker required-file metadata is invalid")
        _, _, current_sizes = self._validate_download(spec, target)
        if recorded_sizes != current_sizes:
            raise ValueError("a required model file size changed after installation")

    def _cleanup_stale_staging(self, spec: ModelSpec) -> None:
        for candidate in self.root.glob(f".partial-{spec.local_dir}-*"):
            self._remove_staging(candidate)

    def _remove_staging(self, staging: Path) -> None:
        if not staging.exists():
            return
        resolved = staging.resolve()
        if not resolved.is_relative_to(self.root) or not staging.name.startswith(".partial-"):
            raise RuntimeError(f"refusing to remove unsafe staging directory: {resolved}")
        shutil.rmtree(staging)


def _snapshot_download(**kwargs) -> str:
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise RuntimeError("huggingface-hub is required for first-run model download") from exc
    return snapshot_download(repo_type="model", **kwargs)
