"""Command-line setup entrypoint used by installers and local development."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from .manifest import load_manifest
from .store import ModelStatus, ModelStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QA Train local model setup")
    parser.add_argument("--data-dir", type=Path, help="override the local QA Train data directory")
    parser.add_argument("--manifest", type=Path, help="model manifest path")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("status", "download", "path"):
        command = subparsers.add_parser(name)
        command.add_argument("--model", default="embedding")
        command.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.data_dir.resolve() / "models" if args.data_dir else None
    try:
        store = ModelStore(root=root, manifest=load_manifest(args.manifest))
        if args.command == "download":
            status = store.ensure(args.model)
        elif args.command == "path":
            status = store.status(args.model)
            if status.state != "ready":
                raise RuntimeError(status.message or "model is not ready")
        else:
            status = store.status(args.model)
        _print_status(status, args.json, path_only=args.command == "path")
        return 0 if status.state == "ready" or args.command == "status" else 1
    except (KeyError, OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


def _print_status(status: ModelStatus, as_json: bool, path_only: bool = False) -> None:
    if as_json:
        print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))
    elif path_only:
        print(status.path)
    else:
        print(f"{status.key}: {status.state}")
        print(f"model: {status.model_id} @ {status.revision}")
        print(f"path: {status.path}")
        if status.message:
            print(status.message)


if __name__ == "__main__":
    raise SystemExit(main())
