from __future__ import annotations

import hashlib
import json
import shutil
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from qa_learn.catalog import load_catalog
from qa_learn.rules import build_rules_from_cache, build_rules_from_document, write_dataset


SAMPLE_HTML = """
<!doctype html>
<html>
  <body>
    <h1>Python Style</h1>
    <h2>Naming conventions</h2>
    <p>Function names should use snake_case and variable names should be descriptive.</p>
    <pre>def calculate_total(item_count):\n    return item_count</pre>
    <h2>Formatting</h2>
    <p>Avoid excessive whitespace and use consistent indentation.</p>
  </body>
</html>
"""


def sample_metadata(html: str = SAMPLE_HTML) -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": {
            "id": "sample",
            "name": "Sample Style Guide",
            "source_type": "style_guide",
            "languages": ["python"],
            "rule_families": ["naming", "formatting"],
        },
        "url": "https://example.com/style",
        "content_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
        "html_file": "sample.html",
    }


class CatalogTests(unittest.TestCase):
    def test_repository_catalog_is_valid_and_contains_expected_sources(self) -> None:
        catalog_path = Path(__file__).resolve().parents[1] / "sources.json"
        sources = load_catalog(catalog_path)
        self.assertEqual(7, len(sources))
        self.assertIn("pep8", {source.source_id for source in sources})
        self.assertTrue(all(page.url.startswith("https://") for source in sources for page in source.pages))
        google = next(source for source in sources if source.source_id == "google-style-guides")
        go_page = next(page for page in google.pages if page.url.endswith("/go/guide"))
        self.assertEqual(("go",), go_page.languages)


class RuleExtractionTests(unittest.TestCase):
    @staticmethod
    @contextmanager
    def temporary_directory() -> Iterator[str]:
        test_root = Path(__file__).resolve().parents[1] / ".test-work"
        test_root.mkdir(exist_ok=True)
        case_root = test_root / f"case-{uuid.uuid4().hex}"
        case_root.mkdir()
        try:
            yield str(case_root)
        finally:
            shutil.rmtree(case_root, ignore_errors=True)

    def test_extracts_naming_targets_and_code_examples(self) -> None:
        rules = build_rules_from_document(SAMPLE_HTML, sample_metadata())
        naming_rules = [rule for rule in rules if rule.category == "naming"]
        self.assertEqual(1, len(naming_rules))
        rule = naming_rules[0]
        self.assertIn("function", rule.targets)
        self.assertIn("variable", rule.targets)
        self.assertEqual(("Python Style", "Naming conventions"), rule.heading_path)
        self.assertIn("calculate_total", rule.examples[0])
        self.assertEqual("pending", rule.review_status)

    def test_cache_hash_is_verified_and_dataset_is_written(self) -> None:
        with self.temporary_directory() as temporary_directory:
            root = Path(temporary_directory)
            raw_root = root / "raw" / "sample"
            raw_root.mkdir(parents=True)
            html_path = raw_root / "sample.html"
            html_path.write_text(SAMPLE_HTML, encoding="utf-8")
            metadata = sample_metadata()
            (raw_root / "sample.meta.json").write_text(
                json.dumps(metadata, ensure_ascii=False), encoding="utf-8"
            )

            rules = build_rules_from_cache(root / "raw")
            manifest = write_dataset(rules, root / "processed")

            self.assertGreaterEqual(manifest["rule_count"], 2)
            self.assertEqual(manifest["rule_count"] * 2, manifest["training_example_count"])
            self.assertEqual(manifest["training_example_count"], manifest["swift_candidate_count"])
            rule_lines = (root / "processed" / "rules.jsonl").read_text(encoding="utf-8").splitlines()
            training_lines = (root / "processed" / "training_examples.jsonl").read_text(encoding="utf-8").splitlines()
            swift_lines = (root / "processed" / "swift_embedding_candidates.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(manifest["rule_count"], len(rule_lines))
            self.assertEqual(manifest["training_example_count"], len(training_lines))
            self.assertEqual(manifest["swift_candidate_count"], len(swift_lines))
            first_example = json.loads(training_lines[0])
            self.assertEqual("rule_retrieval", first_example["task"])
            self.assertIn(first_example["query_language"], {"ko", "en"})
            self.assertFalse(first_example["training_eligible"])
            first_swift_example = json.loads(swift_lines[0])
            self.assertTrue(first_swift_example["messages"][0]["content"].startswith("Instruct: "))
            self.assertNotIn("Instruct:", first_swift_example["positive_messages"][0][0]["content"])

    def test_modified_cache_is_rejected(self) -> None:
        with self.temporary_directory() as temporary_directory:
            root = Path(temporary_directory)
            raw_root = root / "raw" / "sample"
            raw_root.mkdir(parents=True)
            (raw_root / "sample.html").write_text(SAMPLE_HTML + "changed", encoding="utf-8")
            (raw_root / "sample.meta.json").write_text(
                json.dumps(sample_metadata(), ensure_ascii=False), encoding="utf-8"
            )
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                build_rules_from_cache(root / "raw")


if __name__ == "__main__":
    unittest.main()
