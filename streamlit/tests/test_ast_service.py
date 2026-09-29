from __future__ import annotations

import ast
import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import qa_ast_service as ast_service
import qa_web_service as service


class SingleASTServiceTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / ".test_tmp"
        parent.mkdir(exist_ok=True)
        self.work = Path(tempfile.mkdtemp(prefix="ast_", dir=parent)).resolve()
        self.addCleanup(self.cleanup)
        self.session = service.new_session(self.work)

    def cleanup(self):
        if self.work.parent != (ROOT / ".test_tmp").resolve() or self.work.is_symlink():
            raise RuntimeError("Unsafe AST fixture cleanup")
        shutil.rmtree(self.work)

    def analyze(self, name, data):
        return ast_service.analyze_prepared(self.session, service.prepare_upload(self.session, name, data))

    def project(self, files):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            for path, content in files.items():
                archive.writestr(path, content)
        return data.getvalue()

    def test_native_tree_order_and_saved_documents_without_execution(self):
        marker = self.work / "must-not-be-created"
        source = f"from pathlib import Path\nPath({str(marker)!r}).write_text('executed')\nz = 1\na = z + 2\n"
        result = self.analyze("app.py", source.encode())
        self.assertEqual(result["trees"][0]["tree"], ast.dump(ast.parse(source), indent=2))
        self.assertFalse(marker.exists())
        self.assertEqual([item["value"] for item in result["report"]["modules"][0]["execution_items"] if item["kind"] == "변수 대입"], ["z = 1", "a = z + 2"])
        tree = result["documents"]["ast_tree.md"]
        self.assertIn("## 원본 파일\n\n```text\nModule(", tree)
        self.assertNotIn("```python", tree)
        with zipfile.ZipFile(io.BytesIO(result["zip"])) as archive:
            self.assertEqual(set(archive.namelist()), set(result["documents"]))
            for name, document in result["documents"].items():
                self.assertEqual((Path(result["output_path"]) / name).read_text(encoding="utf-8"), document)
                self.assertEqual(archive.read(name).decode(), document)

    def test_notebook_cell_order_preprocessing_and_errors_share_one_report(self):
        cells = [{"cell_type": "code", "source": f"v{i} = {i}\n"} for i in range(1, 12)]
        cells[1] = {"cell_type": "markdown", "source": "A note"}
        cells[2] = {"cell_type": "code", "source": ["%%writefile app.py\n", "def f():\n", "    return 3\n"]}
        cells[3] = {"cell_type": "code", "source": "def broken(:\n"}
        result = self.analyze("notebook.ipynb", json.dumps({"cells": cells}).encode())
        self.assertEqual([row["path"] for row in result["trees"]], [f"notebook.ipynb#cell-{i}" for i in [1, 3, 4, 5, 6, 7, 8, 9, 10, 11]])
        self.assertTrue(result["trees"][1]["preprocessed"])
        self.assertIn("FunctionDef(", result["trees"][1]["tree"])
        self.assertEqual(result["report"]["status"], "incomplete")
        tree = result["documents"]["ast_tree.md"]
        self.assertIn("SyntaxError", tree)
        self.assertLess(tree.index("## 원본 코드 셀 4"), tree.index("## 원본 코드 셀 10"))
        self.assertFalse((Path(result["output_path"]) / "app.py").exists())

    def test_bad_notebook_schema_does_not_discard_valid_project_file(self):
        result = self.analyze("project.zip", self.project({"good.py": "x = 1", "bad.ipynb": '{"cells": null}'}))
        self.assertEqual(result["report"]["module_count"], 2)
        self.assertEqual(len(result["report"]["errors"]), 1)
        self.assertIn("## good.py", result["documents"]["ast_tree.md"])
        self.assertIn("ValueError", result["documents"]["ast_tree.md"])

    def test_empty_notebook_is_reported_as_incomplete(self):
        result = self.analyze("empty.ipynb", b'{"cells": []}')
        self.assertEqual(result["report"]["status"], "incomplete")
        self.assertEqual(result["report"]["module_count"], 0)
        self.assertTrue(result["report"]["warnings"])

    def test_non_python_input_is_rejected(self):
        manifest = service.prepare_upload(self.session, "project.zip", self.project({"app.js": "let x = 1;"}))
        with self.assertRaisesRegex(ValueError, "원본 .py"):
            ast_service.analyze_prepared(self.session, manifest)

    def test_foreign_session_and_modified_snapshot_are_rejected(self):
        manifest = service.prepare_upload(self.session, "app.py", b"x = 1\n")
        with self.assertRaisesRegex(ValueError, "현재 웹 세션"):
            ast_service.analyze_prepared(service.new_session(self.work), manifest)
        (Path(manifest["output_path"]) / "content" / "app.py").write_text("x = 2\n")
        with self.assertRaisesRegex(ValueError, "수정"):
            ast_service.analyze_prepared(self.session, manifest)

    def test_report_size_limit_is_enforced_before_saving(self):
        with patch.object(ast_service, "MAX_DOWNLOAD_BYTES", 10):
            with self.assertRaisesRegex(ValueError, "100MiB"):
                self.analyze("app.py", b"x = 1\n")
        self.assertFalse((self.session / "ast_reports").exists())

    def test_python_encoding_declaration_is_honored(self):
        result = self.analyze("app.py", '# coding: cp949\nname = "한글"\n'.encode("cp949"))
        self.assertEqual(result["report"]["status"], "complete")
        self.assertIn("한글", result["trees"][0]["tree"])

    def test_project_file_tree_keeps_data_configuration_and_ast_links(self):
        source = "def run():\n    return 42\n"
        data = "id,name\n1,example\n"
        notebook = json.dumps({"cells": [
            {"cell_type": "code", "source": "x = 1"},
            {"cell_type": "markdown", "source": "note"},
            {"cell_type": "code", "source": "def broken(:"},
        ]})
        result = self.analyze("project.zip", self.project({
            "src/main.py": source, "data/items.csv": data,
            "data/settings.json": "{}", "README.md": "example",
            "src/demo#cell-name.ipynb": notebook,
        }))
        self.assertEqual(result["file_tree"],
            "./\n├── data/\n│   ├── items.csv\n│   └── settings.json\n"
            "├── src/\n│   ├── demo#cell-name.ipynb\n│   └── main.py\n└── README.md")
        files = {entry["path"]: entry for entry in result["report"]["files"]}
        self.assertEqual(result["report"]["file_count"], 5)
        self.assertEqual(files["data/items.csv"]["category"], "asset_or_data")
        self.assertEqual(files["data/settings.json"]["category"], "configuration")
        self.assertEqual(files["data/items.csv"]["sha256"], hashlib.sha256(data.encode()).hexdigest())
        self.assertEqual(files["data/items.csv"]["size"], len(data.encode()))
        self.assertEqual(files["data/items.csv"]["ast_paths"], [])
        self.assertEqual(files["src/main.py"]["ast_paths"], ["src/main.py"])
        self.assertEqual(files["src/demo#cell-name.ipynb"]["ast_paths"],
                         ["src/demo#cell-name.ipynb#cell-1", "src/demo#cell-name.ipynb#cell-3"])
        self.assertIn("```text\n" + result["file_tree"], result["documents"]["file_tree.md"])
        self.assertNotIn("items.csv", result["documents"]["ast_tree.md"])
        self.assertEqual(json.loads(result["documents"]["ast_structure.json"])["files"], list(files.values()))
        with zipfile.ZipFile(io.BytesIO(result["zip"])) as archive:
            self.assertEqual(archive.read("file_tree.md").decode(), result["documents"]["file_tree.md"])
        self.assertEqual(next(entry["tree"] for entry in result["trees"] if entry["path"] == "src/main.py"),
                         ast.dump(ast.parse(source), indent=2))

    def test_modified_data_file_is_rejected_before_tree_generation(self):
        manifest = service.prepare_upload(self.session, "project.zip", self.project({"app.py": "x = 1", "data/items.csv": "id\n1"}))
        (Path(manifest["output_path"]) / "content/data/items.csv").write_text("id\n2")
        with self.assertRaisesRegex(ValueError, "수정"):
            ast_service.analyze_prepared(self.session, manifest)

    def test_empty_notebook_remains_a_file_without_ast_cells(self):
        result = self.analyze("empty.ipynb", b'{"cells": []}')
        self.assertEqual(result["file_tree"], "./\n└── empty.ipynb")
        self.assertEqual(result["report"]["files"][0]["ast_paths"], [])


if __name__ == "__main__":
    unittest.main()
