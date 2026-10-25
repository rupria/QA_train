from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from unittest.mock import Mock

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent
sys.path.insert(0, str(ROOT))

from qa_local_runtime import LocalEmbeddingRuntime, ModelStore, format_query, load_manifest


class ModelStoreTests(unittest.TestCase):
    def setUp(self):
        self.work = Path(tempfile.mkdtemp(prefix="qa_train_model_test_"))
        self.addCleanup(shutil.rmtree, self.work)
        self.manifest = load_manifest()

    def fake_download(self, **kwargs):
        target = Path(kwargs["local_dir"])
        spec = self.manifest.model("embedding")
        for relative in spec.required_files:
            path = target / Path(*relative.split("/"))
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((relative + "\n").encode("utf-8"))
        return str(target)

    def test_manifest_pins_policy_model_and_revision(self):
        spec = self.manifest.model("embedding")
        policy = json.loads((REPOSITORY / "learn" / "model_policy.json").read_text(encoding="utf-8"))
        primary = policy["models"]["primary"]
        self.assertEqual(spec.model_id, primary["model_id"])
        self.assertEqual(spec.revision, primary["revision"])
        self.assertEqual(primary["delivery"], "first_run_download")
        self.assertEqual(spec.revision, "97b0c614be4d77ee51c0cef4e5f07c00f9eb65b3")
        self.assertEqual(len(spec.revision), 40)

    def test_first_use_download_is_atomic_and_reused(self):
        downloader = Mock(side_effect=self.fake_download)
        store = ModelStore(root=self.work / "models", manifest=self.manifest, downloader=downloader)
        self.assertEqual(store.status().state, "missing")
        installed = store.ensure()
        self.assertEqual(installed.state, "ready")
        self.assertGreater(installed.file_count, 0)
        self.assertGreater(installed.size_bytes, 0)
        self.assertEqual(store.ensure().path, installed.path)
        downloader.assert_called_once()
        call = downloader.call_args.kwargs
        self.assertEqual(call["revision"], self.manifest.model("embedding").revision)
        self.assertIn("model.safetensors", call["allow_patterns"])

    def test_failed_download_is_not_registered_and_partial_is_removed(self):
        def broken(**kwargs):
            Path(kwargs["local_dir"], "config.json").write_text("{}", encoding="utf-8")
            raise OSError("network stopped")

        store = ModelStore(root=self.work / "models", manifest=self.manifest, downloader=broken)
        with self.assertRaisesRegex(OSError, "network stopped"):
            store.ensure()
        self.assertEqual(store.status().state, "missing")
        self.assertEqual(list((self.work / "models").glob(".partial-*")), [])

    def test_stale_partial_is_removed_and_completed_file_change_is_invalid(self):
        root = self.work / "models"
        stale = root / f".partial-{self.manifest.model('embedding').local_dir}-stale"
        stale.mkdir(parents=True)
        (stale / "old.part").write_bytes(b"partial")
        store = ModelStore(root=root, manifest=self.manifest, downloader=self.fake_download)
        installed = store.ensure()
        self.assertEqual(installed.state, "ready")
        self.assertFalse(stale.exists())
        (Path(installed.path) / "config.json").write_bytes(b"x")
        self.assertEqual(store.status().state, "invalid")

    def test_local_embedding_uses_installed_path_and_query_instruction(self):
        store = ModelStore(root=self.work / "models", manifest=self.manifest, downloader=self.fake_download)
        model = Mock()
        model.encode.return_value = [[1.0, 0.0]]
        factory = Mock(return_value=model)
        runtime = LocalEmbeddingRuntime(store=store, model_factory=factory)
        result = runtime.encode_queries(["Python 함수 이름 규칙"])
        self.assertEqual(result, [[1.0, 0.0]])
        factory.assert_called_once_with(str(store.model_path()), local_files_only=True)
        text = model.encode.call_args.args[0][0]
        self.assertTrue(text.startswith("Instruct: "))
        self.assertTrue(text.endswith("Query: Python 함수 이름 규칙"))
        model.encode.assert_called_once_with([text], normalize_embeddings=True, convert_to_numpy=True)

    def test_input_validation(self):
        with self.assertRaises(ValueError):
            format_query("", "query")
        with self.assertRaises(KeyError):
            self.manifest.model("unknown")


if __name__ == "__main__":
    unittest.main()
