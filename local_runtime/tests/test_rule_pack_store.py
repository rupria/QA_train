from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import zipfile

from qa_local_runtime import RulePackStore


class RulePackStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="qa_rule_store_test_"))
        self.addCleanup(shutil.rmtree, self.work)

    @staticmethod
    def metadata(value: bytes) -> dict[str, object]:
        return {"sha256": hashlib.sha256(value).hexdigest(), "size_bytes": len(value)}

    def archive(self, *, bad_checksum: bool = False, unsafe: bool = False) -> Path:
        rules = b"sqlite-placeholder"
        sources = b"[]\n"
        manifest = {
            "schema_version": 1,
            "pack_version": "1.0.0",
            "created_at": "2026-10-24T00:00:00+00:00",
            "state": "metadata_only",
            "rule_count": 1,
            "review_statuses": ["accepted"],
            "release_eligible": False,
            "embedding": {"state": "pending"},
            "files": {
                "rules.sqlite": self.metadata(rules),
                "sources.json": self.metadata(sources),
            },
        }
        if bad_checksum:
            manifest["files"]["rules.sqlite"]["sha256"] = "0" * 64
        path = self.work / ("unsafe.zip" if unsafe else "pack.zip")
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("manifest.json", json.dumps(manifest))
            archive.writestr("rules.sqlite", rules)
            archive.writestr("sources.json", sources)
            if unsafe:
                archive.writestr("../outside.txt", b"blocked")
        return path

    def test_install_is_atomic_verified_and_reusable(self) -> None:
        store = RulePackStore(root=self.work / "installed")
        self.assertEqual(store.status().state, "missing")
        first = store.install(self.archive())
        self.assertEqual(first.state, "ready")
        self.assertEqual(first.pack_version, "1.0.0")
        self.assertFalse(first.semantic_ready)
        self.assertEqual(store.install(self.archive()).state, "ready")
        self.assertEqual(store.pack_path(), Path(first.path))
        self.assertEqual(list((self.work / "installed").glob(".partial-*")), [])

    def test_bad_checksum_is_rejected_without_install(self) -> None:
        store = RulePackStore(root=self.work / "installed")
        with self.assertRaisesRegex(ValueError, "checksum mismatch"):
            store.install(self.archive(bad_checksum=True))
        self.assertEqual(store.status().state, "missing")

    def test_unsafe_archive_path_is_rejected(self) -> None:
        store = RulePackStore(root=self.work / "installed")
        with self.assertRaisesRegex(ValueError, "unsafe rule pack entry"):
            store.install(self.archive(unsafe=True))
        self.assertFalse((self.work / "outside.txt").exists())

    def test_changed_installed_file_is_invalid(self) -> None:
        store = RulePackStore(root=self.work / "installed")
        installed = store.install(self.archive())
        Path(installed.path, "rules.sqlite").write_bytes(b"changed")
        self.assertEqual(store.status().state, "invalid")


if __name__ == "__main__":
    unittest.main()
