from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .catalog import SourceDefinition, load_catalog
from .fetcher import fetch_source, result_as_dict
from .rules import build_rules_from_cache, write_dataset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CATALOG = PROJECT_ROOT / "sources.json"
DEFAULT_MODEL_POLICY = PROJECT_ROOT / "model_policy.json"
DEFAULT_DATA_ROOT = PROJECT_ROOT / "data"


def _sources_for_args(catalog_path: Path, source_ids: list[str] | None) -> list[SourceDefinition]:
    sources = load_catalog(catalog_path)
    if not source_ids:
        return sources
    selected = set(source_ids)
    known = {source.source_id for source in sources}
    unknown = selected - known
    if unknown:
        raise ValueError(f"unknown source ids: {', '.join(sorted(unknown))}")
    return [source for source in sources if source.source_id in selected]


def _print_json(payload: object) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def command_catalog(args: argparse.Namespace) -> int:
    sources = _sources_for_args(args.catalog, args.source)
    _print_json(
        [
            {
                "id": source.source_id,
                "name": source.name,
                "source_type": source.source_type,
                "languages": list(source.languages),
                "rule_families": list(source.rule_families),
                "urls": list(source.urls),
                "pages": [
                    {"url": page.url, "languages": list(page.languages)} for page in source.pages
                ],
            }
            for source in sources
        ]
    )
    return 0


def command_policy(args: argparse.Namespace) -> int:
    policy = json.loads(args.model_policy.read_text(encoding="utf-8"))
    if policy.get("schema_version") != 1:
        raise ValueError("unsupported model policy schema_version")
    _print_json(policy)
    return 0


def command_fetch(args: argparse.Namespace) -> int:
    sources = _sources_for_args(args.catalog, args.source)
    results = []
    for source in sources:
        results.extend(
            fetch_source(
                source,
                args.data_root / "raw",
                force=args.force,
                timeout_seconds=args.timeout,
                max_bytes=args.max_bytes,
            )
        )
    payload = [result_as_dict(result) for result in results]
    _print_json(payload)
    return 1 if any(result.status == "error" for result in results) else 0


def command_build(args: argparse.Namespace) -> int:
    raw_root = args.data_root / "raw"
    if not raw_root.exists() or not any(raw_root.glob("**/*.meta.json")):
        raise FileNotFoundError(f"no cached sources found under {raw_root}; run fetch first")
    rules = build_rules_from_cache(raw_root)
    manifest = write_dataset(rules, args.data_root / "processed")
    _print_json(manifest)
    return 0


def command_all(args: argparse.Namespace) -> int:
    fetch_status = command_fetch(args)
    if fetch_status:
        print("one or more sources failed; cached successful sources can still be built", file=sys.stderr)
    build_status = command_build(args)
    return fetch_status or build_status


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="qa-learn",
        description="Build versioned convention and identifier-rule datasets without an external AI API.",
    )
    parser.add_argument("--catalog", type=Path, default=DEFAULT_CATALOG)
    parser.add_argument("--model-policy", type=Path, default=DEFAULT_MODEL_POLICY)
    parser.add_argument("--data-root", type=Path, default=DEFAULT_DATA_ROOT)
    parser.add_argument("--source", action="append", help="source id to process; repeat to select more than one")
    parser.add_argument("--force", action="store_true", help="download sources even when a cache exists")
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--max-bytes", type=int, default=8 * 1024 * 1024)
    parser.add_argument("command", choices=("catalog", "policy", "fetch", "build", "all"))
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "catalog":
            return command_catalog(args)
        if args.command == "policy":
            return command_policy(args)
        if args.command == "fetch":
            return command_fetch(args)
        if args.command == "build":
            return command_build(args)
        return command_all(args)
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
