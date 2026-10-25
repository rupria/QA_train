from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import shutil
import sqlite3
import tempfile
import unittest
import zipfile

from qa_learn.rule_pack import build_rule_pack


ROOT = Path(__file__).resolve().parents[1]


def rule(rule_id: str, status: str) -> dict[str, object]:
    return {
        "schema_version": 1,
        "rule_id": rule_id,
        "source_id": "sample",
        "source_name": "Sample",
        "source_url": "https://example.com/rules",
        "source_content_sha256": "a" * 64,
        "languages": ["python"],
        "rule_families": ["naming"],
        "category": "naming",
        "targets": ["function"],
        "heading_path": ["Naming"],
        "title": "Function names",
        "statement": "Function names should describe an action.",
        "examples": [],
        "extraction_method": "test",
        "confidence": 0.9,
        "review_status": status,
    }


class RulePackTests(unittest.TestCase):
    def setUp(self) -> None:
        self.work = Path(tempfile.mkdtemp(prefix="qa_rule_pack_test_"))
        self.addCleanup(shutil.rmtree, self.work)
        self.rules = self.work / "rules.jsonl"
        self.rules.write_text(
            "\n".join(json.dumps(item) for item in (rule("accepted-rule", "accepted"), rule("pending-rule", "pending"))) + "\n",
            encoding="utf-8",
        )

    def test_default_pack_contains_only_reviewed_rules(self) -> None:
        output = self.work / "base-rules-1.0.0.zip"
        result = build_rule_pack(self.rules, output, "1.0.0", ROOT / "model_policy.json")
        self.assertEqual(result["rule_count"], 1)
        self.assertEqual(result["state"], "metadata_only")
        self.assertFalse(result["release_eligible"])
        self.assertTrue(output.is_file())
        self.assertTrue(output.with_suffix(".zip.sha256").is_file())
        with zipfile.ZipFile(output) as archive:
            self.assertEqual(
                sorted(archive.namelist()),
                ["manifest.json", "rules.sqlite", "sources.json"],
            )
            manifest = json.loads(archive.read("manifest.json"))
            self.assertEqual(manifest["embedding"]["state"], "pending")
            archive.extract("rules.sqlite", self.work)
        with closing(sqlite3.connect(self.work / "rules.sqlite")) as connection:
            rows = connection.execute("SELECT rule_id, position FROM rules").fetchall()
            languages = connection.execute("SELECT language FROM rule_languages").fetchall()
        self.assertEqual(rows, [("accepted-rule", 0)])
        self.assertEqual(languages, [("python",)])

    def test_pending_rules_require_explicit_draft_selection(self) -> None:
        output = self.work / "draft.zip"
        result = build_rule_pack(
            self.rules,
            output,
            "0.1.0-draft",
            ROOT / "model_policy.json",
            review_statuses=("pending",),
        )
        self.assertEqual(result["rule_count"], 1)
        self.assertEqual(result["review_statuses"], ["pending"])
        self.assertFalse(result["release_eligible"])

    def test_duplicate_rule_ids_are_rejected(self) -> None:
        duplicate = rule("same", "accepted")
        self.rules.write_text(
            json.dumps(duplicate) + "\n" + json.dumps(duplicate) + "\n",
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "duplicate rule_id"):
            build_rule_pack(self.rules, self.work / "bad.zip", "1.0.0", ROOT / "model_policy.json")


if __name__ == "__main__":
    unittest.main()
