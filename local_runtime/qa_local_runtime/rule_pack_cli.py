"""Installer-facing command line for local rule packs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import zipfile

from .rule_pack import RulePackStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QA Train local rule pack setup")
    parser.add_argument("--data-dir", type=Path, help="override the local QA Train data directory")
    subparsers = parser.add_subparsers(dest="command", required=True)
    status = subparsers.add_parser("status")
    status.add_argument("--json", action="store_true")
    install = subparsers.add_parser("install")
    install.add_argument("archive", type=Path)
    install.add_argument("--json", action="store_true")
    path = subparsers.add_parser("path")
    path.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.data_dir.resolve() / "rules" if args.data_dir else None
    store = RulePackStore(root=root)
    try:
        status = store.install(args.archive) if args.command == "install" else store.status()
        if args.command == "path":
            store.pack_path()
        if args.json:
            print(json.dumps(status.to_dict(), ensure_ascii=False, indent=2))
        elif args.command == "path" and status.path:
            print(status.path)
        else:
            print(f"rule-pack: {status.state}")
            print(f"version: {status.pack_version or 'none'}")
            print(f"path: {status.path or 'none'}")
            if status.message:
                print(status.message)
        return 0 if status.state == "ready" or args.command == "status" else 1
    except (FileNotFoundError, OSError, RuntimeError, ValueError, zipfile.BadZipFile) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
