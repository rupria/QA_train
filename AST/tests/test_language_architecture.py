from __future__ import annotations

import shutil
import sys
import unittest
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from code_snapshot import load_snapshot as compatibility_load_snapshot
from qa_ast import EdgeKind, NodeKind, default_registry
from qa_ast.languages.python.snapshot import load_snapshot


class LanguageArchitectureTests(unittest.TestCase):
    def setUp(self):
        temp_root = ROOT / ".test_tmp"
        temp_root.mkdir(exist_ok=True)
        self.work = temp_root / f"architecture_{uuid4().hex}"
        self.work.mkdir()
        self.addCleanup(self._cleanup, temp_root)

    def _cleanup(self, temp_root: Path) -> None:
        if self.work.resolve().parent != temp_root.resolve() or self.work.is_symlink():
            raise RuntimeError("Refusing to clean outside the test workspace")
        shutil.rmtree(self.work)

    def test_registry_supports_explicit_language_selection(self):
        registry = default_registry()
        selected = registry.selected(["python", "python"])
        self.assertEqual([adapter.language_id for adapter in selected], ["python"])
        self.assertEqual(registry.detect(self._source()), {"python": 1})
        hidden = self.work / ".venv" / "installed.py"
        hidden.parent.mkdir()
        hidden.write_text("x = 1\n", encoding="utf-8")
        self.assertEqual(registry.detect(self.work), {"python": 1})
        descriptor = next(item for item in registry.descriptors() if item["id"] == "python")
        self.assertTrue(descriptor["capabilities"]["calls"])
        self.assertFalse(descriptor["capabilities"]["db_mapping"])
        self.assertIn("typescript", {item["id"] for item in registry.descriptors()})

    def test_registry_contains_requested_language_families(self):
        available = {item["id"] for item in default_registry().descriptors()}
        expected = {
            "javascript", "typescript", "vue", "svelte", "astro", "html", "css",
            "java", "kotlin", "scala", "groovy",
            "csharp", "razor", "fsharp", "vbnet",
            "c", "cpp", "objective_c", "swift", "rust", "go", "dart",
            "sql", "r", "julia", "ruby", "php", "perl", "lua",
            "terraform", "bicep", "rego", "dockerfile", "make", "cmake",
            "elixir", "erlang", "clojure", "haskell", "ocaml", "solidity",
            "graphql", "protobuf", "vhdl", "matlab",
        }
        self.assertEqual(expected - available, set())

    def test_python_adapter_emits_language_neutral_graph(self):
        graph = default_registry().get("python").analyze(self._source())
        graph.validate()
        self.assertEqual(graph.languages, ["python"])
        self.assertIn(NodeKind.PROJECT, {node.kind for node in graph.nodes})
        self.assertIn(NodeKind.FUNCTION, {node.kind for node in graph.nodes})
        self.assertIn(EdgeKind.CALLS, {edge.kind for edge in graph.edges})
        serialized = graph.to_dict()
        self.assertEqual(serialized["languages"], ["python"])
        self.assertTrue(all(isinstance(node["kind"], str) for node in serialized["nodes"]))

    def test_legacy_snapshot_import_remains_compatible(self):
        self.assertIs(compatibility_load_snapshot, load_snapshot)
        self.assertIn("app.py::entry", compatibility_load_snapshot(self._source()).symbols)

    def _source(self) -> Path:
        path = self.work / "app.py"
        if not path.exists():
            path.write_text(
                "def helper():\n    return 1\n\ndef entry():\n    return helper()\n",
                encoding="utf-8",
            )
        return path


if __name__ == "__main__":
    unittest.main()
