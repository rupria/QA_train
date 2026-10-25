"""Strict model manifest parsing for deterministic first-run downloads."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path, PurePosixPath
import re


MODEL_ID = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
REVISION = re.compile(r"^[0-9a-f]{40}$")
LOCAL_DIR = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True)
class ModelSpec:
    key: str
    model_id: str
    revision: str
    license: str
    source_url: str
    local_dir: str
    approximate_download_bytes: int
    query_instruction: str
    allow_patterns: tuple[str, ...]
    required_files: tuple[str, ...]


@dataclass(frozen=True)
class ModelManifest:
    schema_version: int
    delivery: str
    models: dict[str, ModelSpec]

    def model(self, key: str) -> ModelSpec:
        try:
            return self.models[key]
        except KeyError as exc:
            raise KeyError(f"unknown model key: {key}") from exc


def default_manifest_path() -> Path:
    return Path(__file__).resolve().parents[1] / "model_manifest.json"


def load_manifest(path: Path | None = None) -> ModelManifest:
    manifest_path = Path(path or default_manifest_path()).resolve()
    try:
        raw = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read model manifest: {manifest_path}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ValueError("model manifest schema_version must be 1")
    if raw.get("delivery") != "first_run_download":
        raise ValueError("model manifest delivery must be first_run_download")
    if not isinstance(raw.get("models"), dict) or not raw["models"]:
        raise ValueError("model manifest must define at least one model")
    models: dict[str, ModelSpec] = {}
    for key, value in raw["models"].items():
        if not isinstance(key, str) or not key or not isinstance(value, dict):
            raise ValueError("model entries must use non-empty string keys and objects")
        spec = ModelSpec(
            key=key,
            model_id=_required_string(value, "model_id"),
            revision=_required_string(value, "revision"),
            license=_required_string(value, "license"),
            source_url=_required_string(value, "source_url"),
            local_dir=_required_string(value, "local_dir"),
            approximate_download_bytes=value.get("approximate_download_bytes"),
            query_instruction=_required_string(value, "query_instruction"),
            allow_patterns=_paths(value, "allow_patterns"),
            required_files=_paths(value, "required_files"),
        )
        _validate_spec(spec)
        models[key] = spec
    return ModelManifest(schema_version=1, delivery="first_run_download", models=models)


def _required_string(value: dict, key: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise ValueError(f"model {key} must be a non-empty string")
    return result.strip()


def _paths(value: dict, key: str) -> tuple[str, ...]:
    entries = value.get(key)
    if not isinstance(entries, list) or not entries or not all(isinstance(item, str) for item in entries):
        raise ValueError(f"model {key} must be a non-empty string list")
    normalized = tuple(dict.fromkeys(item.replace("\\", "/") for item in entries))
    for item in normalized:
        path = PurePosixPath(item)
        if path.is_absolute() or ".." in path.parts or not item.strip():
            raise ValueError(f"unsafe model path in {key}: {item!r}")
    return normalized


def _validate_spec(spec: ModelSpec) -> None:
    if not MODEL_ID.fullmatch(spec.model_id):
        raise ValueError(f"invalid model_id: {spec.model_id!r}")
    if not REVISION.fullmatch(spec.revision):
        raise ValueError("model revision must be a pinned 40-character lowercase commit hash")
    if not LOCAL_DIR.fullmatch(spec.local_dir) or spec.local_dir in {".", ".."}:
        raise ValueError(f"unsafe model local_dir: {spec.local_dir!r}")
    if not isinstance(spec.approximate_download_bytes, int) or spec.approximate_download_bytes <= 0:
        raise ValueError("approximate_download_bytes must be a positive integer")
    if not spec.source_url.startswith("https://huggingface.co/"):
        raise ValueError("model source_url must use https://huggingface.co/")
    if not set(spec.required_files).issubset(spec.allow_patterns):
        raise ValueError("every required file must be included in allow_patterns")
