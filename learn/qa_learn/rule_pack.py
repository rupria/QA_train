"""Build versioned, self-verifying rule packs for local QA Train clients."""

from __future__ import annotations

import ast
from contextlib import closing
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import sqlite3
import struct
import tempfile
import zipfile


PACK_VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DEFAULT_REVIEW_STATUSES = ("accepted", "approved")


def build_rule_pack(
    rules_path: Path,
    output_path: Path,
    pack_version: str,
    model_policy_path: Path,
    *,
    review_statuses: tuple[str, ...] = DEFAULT_REVIEW_STATUSES,
    embeddings_path: Path | None = None,
) -> dict[str, object]:
    """Create a ZIP pack. Without embeddings the result is a valid metadata-only draft."""
    _validate_pack_version(pack_version)
    statuses = tuple(dict.fromkeys(item.strip() for item in review_statuses if item.strip()))
    if not statuses:
        raise ValueError("at least one review status is required")
    rules = _load_rules(Path(rules_path), statuses)
    policy = _load_model_policy(Path(model_policy_path))
    output = Path(output_path).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="qa_rule_pack_", dir=output.parent) as temporary:
        root = Path(temporary)
        database_path = root / "rules.sqlite"
        sources_path = root / "sources.json"
        _write_database(database_path, rules)
        _write_sources(sources_path, rules)

        files = {
            "rules.sqlite": _file_metadata(database_path),
            "sources.json": _file_metadata(sources_path),
        }
        primary = policy["models"]["primary"]
        dimension = int(policy["encoding"]["runtime_embedding_dimensions"])
        embedding = {
            "state": "pending",
            "file": None,
            "model_id": primary["model_id"],
            "revision": primary["revision"],
            "dimension": dimension,
            "dtype": "float32",
            "normalization": policy["encoding"]["normalization"],
            "similarity": policy["encoding"]["similarity"],
            "query_instruction": policy["encoding"]["query_instruction"],
        }
        if embeddings_path is not None:
            embedding_source = Path(embeddings_path).resolve()
            count, actual_dimension, dtype = _npy_shape(embedding_source)
            if count != len(rules):
                raise ValueError(f"embedding row count {count} does not match rule count {len(rules)}")
            if actual_dimension != dimension:
                raise ValueError(
                    f"embedding dimension {actual_dimension} does not match policy dimension {dimension}"
                )
            if dtype not in {"<f4", "|f4", ">f4"}:
                raise ValueError(f"embeddings must use float32, got {dtype}")
            target = root / "embeddings.npy"
            shutil.copyfile(embedding_source, target)
            files[target.name] = _file_metadata(target)
            embedding.update({"state": "ready", "file": target.name, "dtype": "float32"})

        manifest = {
            "schema_version": 1,
            "pack_version": pack_version,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "state": "semantic_ready" if embedding["state"] == "ready" else "metadata_only",
            "rule_count": len(rules),
            "review_statuses": list(statuses),
            "release_eligible": (
                embedding["state"] == "ready"
                and set(statuses).issubset(set(DEFAULT_REVIEW_STATUSES))
            ),
            "embedding": embedding,
            "files": files,
        }
        manifest_path = root / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        temporary_archive = output.with_suffix(output.suffix + ".partial")
        temporary_archive.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(temporary_archive, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for name in ("manifest.json", "rules.sqlite", "sources.json", "embeddings.npy"):
                    candidate = root / name
                    if candidate.exists():
                        archive.write(candidate, arcname=name)
            temporary_archive.replace(output)
        finally:
            temporary_archive.unlink(missing_ok=True)

    archive_sha256 = _sha256(output)
    checksum_path = output.with_suffix(output.suffix + ".sha256")
    checksum_path.write_text(f"{archive_sha256}  {output.name}\n", encoding="utf-8")
    return {
        **manifest,
        "archive": str(output),
        "archive_sha256": archive_sha256,
        "checksum_file": str(checksum_path),
    }


def _load_rules(path: Path, statuses: tuple[str, ...]) -> list[dict[str, object]]:
    if not path.is_file():
        raise FileNotFoundError(f"rules dataset is missing: {path}")
    selected: list[dict[str, object]] = []
    seen: set[str] = set()
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            rule = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON at {path}:{line_number}") from exc
        if not isinstance(rule, dict) or rule.get("schema_version") != 1:
            raise ValueError(f"unsupported rule schema at {path}:{line_number}")
        rule_id = rule.get("rule_id")
        if not isinstance(rule_id, str) or not rule_id:
            raise ValueError(f"missing rule_id at {path}:{line_number}")
        if rule_id in seen:
            raise ValueError(f"duplicate rule_id: {rule_id}")
        seen.add(rule_id)
        if rule.get("review_status") in statuses:
            selected.append(rule)
    if not selected:
        raise ValueError(f"no rules matched review statuses: {', '.join(statuses)}")
    return sorted(selected, key=lambda item: str(item["rule_id"]))


def _load_model_policy(path: Path) -> dict[str, object]:
    try:
        policy = json.loads(path.read_text(encoding="utf-8"))
        primary = policy["models"]["primary"]
        encoding = policy["encoding"]
        required = (
            primary["model_id"], primary["revision"],
            encoding["runtime_embedding_dimensions"], encoding["query_instruction"],
        )
    except (OSError, UnicodeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"invalid model policy: {path}") from exc
    if policy.get("schema_version") != 1 or not all(required):
        raise ValueError("model policy is incomplete")
    return policy


def _write_database(path: Path, rules: list[dict[str, object]]) -> None:
    with closing(sqlite3.connect(path)) as connection, connection:
        connection.executescript(
            """
            PRAGMA journal_mode=DELETE;
            CREATE TABLE rules (
                position INTEGER PRIMARY KEY,
                rule_id TEXT NOT NULL UNIQUE,
                source_id TEXT NOT NULL,
                source_name TEXT NOT NULL,
                source_url TEXT NOT NULL,
                source_content_sha256 TEXT NOT NULL,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                statement TEXT NOT NULL,
                confidence REAL NOT NULL,
                review_status TEXT NOT NULL,
                languages_json TEXT NOT NULL,
                targets_json TEXT NOT NULL,
                heading_path_json TEXT NOT NULL,
                examples_json TEXT NOT NULL,
                record_json TEXT NOT NULL
            );
            CREATE TABLE rule_languages (rule_id TEXT NOT NULL, language TEXT NOT NULL);
            CREATE TABLE rule_targets (rule_id TEXT NOT NULL, target TEXT NOT NULL);
            CREATE INDEX idx_rules_category ON rules(category);
            CREATE INDEX idx_rules_source ON rules(source_id);
            CREATE INDEX idx_languages_language ON rule_languages(language);
            CREATE INDEX idx_targets_target ON rule_targets(target);
            """
        )
        for position, rule in enumerate(rules):
            value = lambda key: json.dumps(rule.get(key, []), ensure_ascii=False, separators=(",", ":"))
            connection.execute(
                "INSERT INTO rules VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    position, rule["rule_id"], rule.get("source_id", ""), rule.get("source_name", ""),
                    rule.get("source_url", ""), rule.get("source_content_sha256", ""),
                    rule.get("category", "general"), rule.get("title", ""), rule.get("statement", ""),
                    float(rule.get("confidence", 0.0)), rule.get("review_status", ""),
                    value("languages"), value("targets"), value("heading_path"), value("examples"),
                    json.dumps(rule, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
                ),
            )
            connection.executemany(
                "INSERT INTO rule_languages VALUES (?, ?)",
                ((rule["rule_id"], str(item)) for item in rule.get("languages", [])),
            )
            connection.executemany(
                "INSERT INTO rule_targets VALUES (?, ?)",
                ((rule["rule_id"], str(item)) for item in rule.get("targets", [])),
            )


def _write_sources(path: Path, rules: list[dict[str, object]]) -> None:
    sources: dict[str, dict[str, object]] = {}
    hashes: dict[str, set[str]] = defaultdict(set)
    urls: dict[str, set[str]] = defaultdict(set)
    for rule in rules:
        source_id = str(rule.get("source_id", ""))
        sources[source_id] = {"source_id": source_id, "source_name": rule.get("source_name", "")}
        hashes[source_id].add(str(rule.get("source_content_sha256", "")))
        urls[source_id].add(str(rule.get("source_url", "")))
    payload = []
    for source_id in sorted(sources):
        payload.append({
            **sources[source_id],
            "source_urls": sorted(item for item in urls[source_id] if item),
            "content_sha256": sorted(item for item in hashes[source_id] if item),
        })
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _npy_shape(path: Path) -> tuple[int, int, str]:
    with path.open("rb") as handle:
        if handle.read(6) != b"\x93NUMPY":
            raise ValueError("embedding file is not a NumPy .npy file")
        major, minor = handle.read(2)
        size = struct.unpack("<H" if major == 1 else "<I", handle.read(2 if major == 1 else 4))[0]
        header = ast.literal_eval(handle.read(size).decode("latin1").strip())
    shape = header.get("shape")
    if not isinstance(shape, tuple) or len(shape) != 2 or header.get("fortran_order"):
        raise ValueError("embeddings must be a two-dimensional C-order NumPy array")
    return int(shape[0]), int(shape[1]), str(header.get("descr"))


def _validate_pack_version(value: str) -> None:
    if not PACK_VERSION.fullmatch(value):
        raise ValueError(f"invalid pack version: {value!r}")


def _file_metadata(path: Path) -> dict[str, object]:
    return {"sha256": _sha256(path), "size_bytes": path.stat().st_size}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
