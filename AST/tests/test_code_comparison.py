from __future__ import annotations

import json
import shutil
import subprocess
import sys
import unittest
from uuid import uuid4
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from code_comparison import build_comparison, markdown_comparison, write_comparison
from code_relations import build_relations
from code_snapshot import load_snapshot


class ComparisonTests(unittest.TestCase):
    def setUp(self):
        temp_root = ROOT / ".test_tmp"
        temp_root.mkdir(exist_ok=True)
        # Normal inherited ACLs also work with Windows sandbox identities.
        self.work = temp_root / f"case_{uuid4().hex}"
        self.work.mkdir()
        self.addCleanup(self.cleanup_work, temp_root)
        self.base, self.target = self.work / "base", self.work / "target"
        self.base.mkdir()
        self.target.mkdir()

    def cleanup_work(self, temp_root):
        if self.work.resolve().parent != temp_root.resolve() or self.work.is_symlink():
            raise RuntimeError("Refusing to clean outside the test workspace")
        shutil.rmtree(self.work)

    def write(self, side, file, source):
        path = getattr(self, side) / file
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source, encoding="utf-8")
        return path

    def pair(self, before, after, file="app.py"):
        self.write("base", file, before)
        self.write("target", file, after)
        return build_comparison(self.base, self.target)

    def calls(self, source, files=None):
        self.write("target", "app.py", source)
        for file, value in (files or {}).items():
            self.write("target", file, value)
        graph = build_relations(load_snapshot(self.target))
        return {(e["caller"], e["callee"]) for e in graph["edges"] if e["kind"] == "call"}, graph

    def test_demo_finds_two_features_without_inventory_false_positive(self):
        folder = ROOT / "examples" / "code_compare"
        report = build_comparison(folder / "base", folder / "target", folder / "features.json")
        self.assertEqual([(c["file"], c["symbol"]) for c in report["changes"]], [("services/auth.py", "valid_token")])
        change = report["changes"][0]
        self.assertEqual({f["id"] for f in change["features"]}, {"LOGIN", "AUTO_LOGIN"})
        login = next(f for f in change["features"] if f["id"] == "LOGIN")
        self.assertIn("LOGIN-BOUNDARY-001", login["tc_ids"])
        self.assertEqual({e["depth"] for e in login["evidence"]}, {2})
        self.assertEqual(report["ignored_text_changes"], ["screens.py"])
        self.assertNotIn("INVENTORY", {f["id"] for f in change["features"]})

    def test_method_change_does_not_duplicate_class_or_module(self):
        report = self.pair("class C:\n    def f(self):\n        return 1\n", "class C:\n    def f(self):\n        return 2\n")
        self.assertEqual([c["symbol"] for c in report["changes"]], ["C.f"])

    def test_comments_format_and_line_shifts_are_ignored(self):
        report = self.pair("def f(x):\n    return x+1\n", "# new comment\n\ndef f( x ):\n    return (x + 1)  # same AST\n")
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["ignored_text_changes"], ["app.py"])

    def test_deleted_symbol_preserves_base_caller_evidence(self):
        before = "def helper():\n    return 1\ndef caller():\n    return helper()\n"
        after = "def caller():\n    return 0\n"
        report = self.pair(before, after)
        deleted = next(c for c in report["changes"] if c["symbol"] == "helper")
        self.assertEqual(deleted["change_type"], "deleted")
        self.assertIsNone(deleted["target"])
        self.assertIn(("base", "caller"), {(i["side"], i["symbol"]) for i in deleted["impacts"]})

    def test_signature_and_decorator_changes_are_own_symbol_changes(self):
        report = self.pair("def f(x=1):\n    return x\n", "@staticmethod\ndef f(x=2):\n    return x\n")
        self.assertEqual([c["symbol"] for c in report["changes"]], ["f"])

    def test_import_alias_resolves_without_same_name_guessing(self):
        calls, graph = self.calls("from a import helper as selected\ndef caller():\n    return selected()\n",
                                 {"a.py": "def helper():\n    return 1\n", "b.py": "def helper():\n    return 2\n"})
        self.assertIn(("app.py::caller", "a.py::helper"), calls)
        self.assertNotIn(("app.py::caller", "b.py::helper"), calls)

    def test_parameter_shadowing_and_local_rebinding_are_unresolved(self):
        calls, graph = self.calls("def helper():\n    return 1\ndef f(helper):\n    return helper()\ndef g():\n    helper = unknown\n    return helper()\n")
        self.assertNotIn(("app.py::f", "app.py::helper"), calls)
        self.assertNotIn(("app.py::g", "app.py::helper"), calls)
        self.assertTrue(any(e["caller"] == "app.py::f" for e in graph["unresolved"]))

    def test_imported_redefined_binding_is_not_original_function(self):
        calls, _ = self.calls("from auth import helper\ndef caller():\n    return helper()\n",
                             {"auth.py": "def helper():\n    return 1\nhelper = other\n"})
        self.assertNotIn(("app.py::caller", "auth.py::helper"), calls)

    def test_nested_global_resolves_module_not_enclosing_scope(self):
        calls, _ = self.calls("def helper():\n    return 1\ndef outer():\n    def helper():\n        return 2\n    def inner():\n        global helper\n        return helper()\n    return inner()\n")
        self.assertIn(("app.py::outer.inner", "app.py::helper"), calls)
        self.assertNotIn(("app.py::outer.inner", "app.py::outer.helper"), calls)

    def test_nested_function_is_not_an_attribute(self):
        calls, _ = self.calls("def outer():\n    def inner():\n        return 1\n    return inner()\ndef caller():\n    return outer.inner()\n")
        self.assertNotIn(("app.py::caller", "app.py::outer.inner"), calls)
        self.assertIn(("app.py::outer", "app.py::outer.inner"), calls)

    def test_deleted_local_name_does_not_resolve_global(self):
        calls, _ = self.calls("def helper():\n    return 1\ndef caller():\n    del helper\n    return helper()\n")
        self.assertNotIn(("app.py::caller", "app.py::helper"), calls)

    def test_receiver_method_and_constructor_connections(self):
        calls, _ = self.calls("class C:\n    def __init__(self):\n        self.f()\n    def f(self):\n        return 1\ndef make():\n    return C()\n")
        self.assertIn(("app.py::C.__init__", "app.py::C.f"), calls)
        self.assertIn(("app.py::make", "app.py::C.__init__"), calls)

    def test_relative_import_and_package_reexport(self):
        calls, _ = self.calls("from package import helper\ndef caller():\n    return helper()\n",
                             {"package/__init__.py": "from .auth import helper\n", "package/auth.py": "def helper():\n    return 1\n"})
        self.assertIn(("app.py::caller", "package/auth.py::helper"), calls)

    def test_constant_change_reaches_body_and_default_users(self):
        before = "LIMIT = 1\ndef f():\n    return LIMIT\ndef g(value=LIMIT):\n    return value\n"
        report = self.pair(before, before.replace("LIMIT = 1", "LIMIT = 2"))
        self.assertEqual([c["symbol"] for c in report["changes"]], ["<module>"])
        self.assertTrue({"f", "g"}.issubset({i["symbol"] for i in report["changes"][0]["impacts"]}))

    def test_cycle_terminates_and_depth_cutoff_is_visible(self):
        before = "def a():\n    return b()\ndef b():\n    return a()+1\ndef c():\n    return a()\n"
        self.pair(before, before.replace("+1", "+2"))
        report = build_comparison(self.base, self.target, max_depth=1)
        change = next(c for c in report["changes"] if c["symbol"] == "b")
        self.assertEqual(len(change["impacts"]), 4)
        self.assertEqual(change["traversal_truncated"], ["base", "target"])

    def test_syntax_error_skips_unit_and_cli_exits_incomplete(self):
        self.pair("def f():\n    return 1\n", "def f(:\n    pass\n")
        output = self.work / "error_report.json"
        result = subprocess.run([sys.executable, "-B", str(ROOT / "ast_analyzer.py"), "compare", str(self.base), str(self.target), "--format", "json", "--output", str(output)], capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 2, result.stderr)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["status"], "incomplete")
        self.assertEqual(report["changes"], [])
        self.assertEqual(len(report["skipped_files"]), 1)

    def test_sources_are_never_executed(self):
        sentinel = self.work / "must_not_exist.txt"
        source = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\nraise RuntimeError('must not execute')\ndef f():\n    return 1\n"
        self.pair(source, source.replace("return 1", "return 2"))
        self.assertFalse(sentinel.exists())

    def test_standalone_files_with_different_names_compare_same_symbol(self):
        before = self.write("base", "old.py", "def f():\n    return 1\n")
        after = self.write("target", "new.py", "def f():\n    return 2\n")
        report = build_comparison(before, after)
        self.assertEqual([(c["file"], c["symbol"], c["change_type"]) for c in report["changes"]], [("new.py", "f", "modified")])

    def test_notebook_preprocessing_and_invalid_container_are_visible(self):
        notebook = {"cells": [{"cell_type": "code", "source": ["%%writefile example.py\n", "def f():\n", "    return 1\n"]}]}
        self.write("base", "test.ipynb", json.dumps(notebook))
        self.write("target", "test.ipynb", "{ invalid json")
        report = build_comparison(self.base, self.target)
        self.assertEqual(report["changes"], [])
        self.assertEqual(report["status"], "incomplete")
        self.assertTrue(any("preprocessed" in w for w in report["warnings"]))

    def test_invalid_mapping_and_missing_entry_are_visible(self):
        self.pair("def f():\n    return 1\n", "def f():\n    return 2\n")
        mapping = self.work / "features.json"
        mapping.write_text(json.dumps({"features": [{"id": "F", "name": "Feature", "entry_points": [{"file": "app.py", "symbol": "missing"}]}]}), encoding="utf-8")
        report = build_comparison(self.base, self.target, mapping)
        self.assertTrue(any("미확인" in w for w in report["warnings"]))
        mapping.write_text("[]", encoding="utf-8")
        with self.assertRaises(ValueError):
            build_comparison(self.base, self.target, mapping)

    def test_report_does_not_overwrite_mapping_or_source(self):
        self.pair("def f():\n    return 1\n", "def f():\n    return 2\n")
        mapping = self.work / "features.json"
        mapping.write_text('{"features": []}', encoding="utf-8")
        report = build_comparison(self.base, self.target, mapping)
        with self.assertRaises(ValueError):
            write_comparison(report, "both", mapping)
        with self.assertRaises(ValueError):
            write_comparison(report, "markdown", self.target / "app.py")
        self.assertEqual(mapping.read_text(), '{"features": []}')

    def test_duplicate_definitions_and_ignored_environment(self):
        self.write("base", "app.py", "def f():\n    return 1\ndef f():\n    return 2\n")
        self.write("target", "app.py", "def f():\n    return 3\n")
        self.write("target", ".venv/broken.py", "syntax error !!!")
        report = build_comparison(self.base, self.target)
        self.assertEqual(report["changes"], [])
        self.assertEqual(len(report["errors"]), 1)

    def test_empty_or_missing_input_is_not_a_success(self):
        with self.assertRaises(ValueError):
            build_comparison(self.base, self.target)
        with self.assertRaises(OSError):
            load_snapshot(self.work / "missing.py")

    def test_legacy_tree_and_structure_cli_still_work(self):
        source = self.write("target", "app.py", "def f():\n    return 1\n")
        for mode in ("tree", "structure"):
            output = self.work / f"{mode}.md"
            result = subprocess.run([sys.executable, "-B", str(ROOT / "ast_analyzer.py"), mode, str(source), "--output", str(output)], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(output.exists())


if __name__ == "__main__":
    unittest.main()
