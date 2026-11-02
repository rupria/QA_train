from __future__ import annotations

import json
from pathlib import Path
import tomllib
import unittest


ROOT = Path(__file__).resolve().parents[1]


class AppVersionTests(unittest.TestCase):
    def test_cloud_local_and_learning_packages_share_product_version(self):
        manifest = json.loads((ROOT / "app_manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schema_version"], 1)
        expected = manifest["app_version"]
        for project in ("streamlit", "local_runtime", "learn"):
            with self.subTest(project=project):
                data = tomllib.loads((ROOT / project / "pyproject.toml").read_text(encoding="utf-8"))
                self.assertEqual(data["project"]["version"], expected)

    def test_local_launcher_uses_the_same_streamlit_entrypoint(self):
        launcher = (ROOT / "streamlit" / "run_qa_local.ps1").read_text(encoding="utf-8")
        shared = (ROOT / "streamlit" / "run_qa_web.ps1").read_text(encoding="utf-8")
        self.assertIn("run_qa_web.ps1", launcher)
        self.assertIn("streamlit_app.py", shared)


if __name__ == "__main__":
    unittest.main()
