from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "AST"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from language_cases import CASES, CASES_BY_ID, VALUE_MARKER  # noqa: E402
from qa_ast import default_registry  # noqa: E402


class LanguageCaseCatalogTests(unittest.TestCase):
    def test_every_registered_language_has_one_fixture(self):
        registered = {item["id"] for item in default_registry().descriptors()}
        self.assertEqual(set(CASES_BY_ID), registered)
        self.assertEqual(len(CASES_BY_ID), len(CASES))

    def test_every_fixture_has_one_change_marker_and_two_distinct_versions(self):
        for case in CASES:
            with self.subTest(language=case.language_id):
                self.assertEqual(case.source_template.count(VALUE_MARKER), 1)
                self.assertNotEqual(case.source(1), case.source(2))
                self.assertTrue(case.filename)
                self.assertTrue(case.group)


if __name__ == "__main__":
    unittest.main()
