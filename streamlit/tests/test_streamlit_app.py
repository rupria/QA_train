"""Headless pair-page flows; remote requests and project execution are absent."""
from __future__ import annotations

import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import unittest
from unittest.mock import patch
from uuid import uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from streamlit.testing.v1 import AppTest
import artifact_conversion as conversion
import qa_web_service as service


class Uploaded(io.BytesIO):
    def __init__(self, name, data):
        super().__init__(data)
        self.name, self.size = name, len(data)


class StreamlitAppTests(unittest.TestCase):
    def setUp(self):
        self.parent = ROOT / ".test_tmp"
        self.parent.mkdir(exist_ok=True)
        self.work = self.parent / f"ui_{uuid4().hex}"
        self.work.mkdir()
        self.environment = patch.dict(os.environ, {"QA_WEB_WORKSPACE": str(self.work), "QA_WEB_ALLOW_LOCAL": "1"})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.addCleanup(self.cleanup)
        self.app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20).run()

    def cleanup(self):
        expected = self.work.absolute()
        if self.work.resolve() != expected or expected.parent != self.parent.resolve() or conversion._is_reparse(self.work):
            raise RuntimeError("Unsafe UI fixture cleanup")
        def readonly_retry(function, path, error):
            item = Path(path)
            if not item.resolve().is_relative_to(expected) or conversion._is_reparse(item):
                raise RuntimeError("Unsafe UI fixture permission change") from error
            item.chmod(item.stat().st_mode | stat.S_IWRITE)
            function(path)
        shutil.rmtree(expected, onexc=readonly_retry)

    def assert_clean(self):
        self.assertEqual(list(self.app.exception), [])

    def result(self):
        self.assert_clean()
        return self.app.session_state.pair_analysis

    def source_files(self):
        before, after = self.work / "before.py", self.work / "after.py"
        before.write_text("def f(x):\n    return x < 30\n", encoding="utf-8")
        after.write_text("def f(x):\n    return x <= 30\n", encoding="utf-8")
        return before, after

    def local_side(self, side, path):
        self.app.segmented_control(key=f"{side}_method").set_value("로컬 경로").run()
        self.app.text_input(key=f"{side}_location").set_value(str(path)).run()
        self.assert_clean()

    def install_snapshots(self, manifests):
        self.app.session_state.snapshots = [{"label": f"입력 {i}", "manifest": value} for i, value in enumerate(manifests)]
        self.app.run()
        for side, manifest in zip(("base", "target"), manifests):
            self.app.segmented_control(key=f"{side}_method").set_value("준비된 입력").run()
            self.app.selectbox(key=f"{side}_snapshot").select(manifest["id"]).run()
        self.assert_clean()

    def source_snapshots(self):
        session = self.app.session_state.work_session
        return [service.prepare_upload(session, "app.py", b"def f(x):\n    return x < 30\n"),
                service.prepare_upload(session, "app.py", b"def f(x):\n    return x <= 30\n")]

    def apk(self, payload):
        data = io.BytesIO()
        with zipfile.ZipFile(data, "w") as archive:
            archive.writestr("AndroidManifest.xml", "synthetic fixture")
            archive.writestr("assets/settings.json", payload)
        return data.getvalue()

    def upload_patch(self, uploads):
        import streamlit
        original = streamlit.file_uploader
        def uploaded(label, *args, **kwargs):
            if kwargs.get("key") in uploads:
                return uploads[kwargs["key"]]
            return original(label, *args, **kwargs)
        return patch.object(streamlit, "file_uploader", uploaded)

    def mapping(self):
        return Uploaded("features.json", json.dumps({"features": [{"id": "POLICY", "name": "정책 확인",
            "entry_points": [{"file": "app.py", "symbol": "f"}], "tc_ids": ["TC-001"]}]}).encode())

    def assert_actual_boundary_diff(self, result):
        diffs = "\n".join(item["diff"] for item in result["file_evidence"]["details"].values())
        self.assertIn("-    return x < 30", diffs)
        self.assertIn("+    return x <= 30", diffs)

    def assert_blocked(self):
        button = self.app.button(key="run_pair")
        if not button.disabled:
            button.click().run()
        self.assert_clean()
        self.assertTrue(button.disabled or self.app.error or self.app.warning)
        self.assertFalse(self.app.session_state.pair_analysis)

    def test_initial_page_has_both_inputs_and_no_processing_on_rerun(self):
        self.assert_clean()
        self.assertEqual(self.app.session_state.view, "비교")
        for side in ("base", "target"):
            self.assertEqual(self.app.segmented_control(key=f"{side}_method").value, "파일 업로드")
        self.assertEqual(self.app.button(key="run_pair").label, "두 입력 비교")
        session = self.app.session_state.work_session
        self.app.run()
        self.assert_clean()
        self.assertEqual(self.app.session_state.snapshots, [])
        self.assertFalse((session / "input").exists())

    def test_local_pair_one_button_shows_diff_and_rerun_does_not_reprocess(self):
        before, after = self.source_files()
        self.local_side("base", before)
        self.local_side("target", after)
        with patch.object(service, "prepare_local", wraps=service.prepare_local) as prepare, \
                patch.object(service, "compare_prepared", wraps=service.compare_prepared) as compare:
            self.app.button(key="run_pair").click().run()
            result = self.result()
            self.assertEqual(result["mode"], "코드 영향")
            self.assertEqual([(c["symbol"], c["change_type"]) for c in result["report"]["changes"]], [("f", "modified")])
            self.assert_actual_boundary_diff(result)
            self.assertEqual((prepare.call_count, compare.call_count), (2, 1))
            self.assertEqual(len(self.app.session_state.snapshots), 2)
            self.app.run()
            self.assert_clean()
            self.assertEqual((prepare.call_count, compare.call_count), (2, 1))
        self.assertEqual(before.read_text(encoding="utf-8"), "def f(x):\n    return x < 30\n")
        self.assertEqual(after.read_text(encoding="utf-8"), "def f(x):\n    return x <= 30\n")

    def test_uploaded_apk_pair_compares_inventory_on_same_page(self):
        uploads = {"base_upload": Uploaded("before.apk", self.apk('{"level":1}')),
                   "target_upload": Uploaded("after.apk", self.apk('{"level":2}'))}
        with self.upload_patch(uploads):
            self.app.run()
            self.app.button(key="run_pair").click().run()
            result = self.result()
            self.assertEqual(result["mode"], "파일 구성")
            self.assertEqual([(c["path"], c["type"]) for c in result["report"]["changes"]], [("assets/settings.json", "modified")])
            self.assertEqual(self.app.session_state.view, "비교")
            self.assertEqual(len(self.app.session_state.snapshots), 2)

    def test_prepared_pair_keeps_candidates_and_tc_mapping_without_new_uploads(self):
        manifests = self.source_snapshots()
        self.install_snapshots(manifests)
        with self.upload_patch({"pair_features": self.mapping()}), patch.object(service, "prepare_upload") as prepare:
            self.app.run()
            self.app.button(key="run_pair").click().run()
            report = self.result()["report"]
            self.assertEqual(report["summary"]["affected_features"], 1)
            self.assertEqual(report["changes"][0]["features"][0]["tc_ids"], ["TC-001"])
            self.assertEqual([item["manifest"]["id"] for item in self.app.session_state.snapshots], [m["id"] for m in manifests])
            prepare.assert_not_called()

    def test_changed_input_hides_previous_result_and_downloads(self):
        before, after = self.source_files()
        self.local_side("base", before)
        self.local_side("target", after)
        self.app.button(key="run_pair").click().run()
        self.assert_actual_boundary_diff(self.result())
        self.app.text_input(key="target_location").set_value(str(self.work / "different.py")).run()
        self.assert_clean()
        self.assertEqual(len(self.app.metric), 0)
        self.assertFalse(any(item.key == "report_json" for item in self.app.get("download_button")))

    def test_changed_mapping_hides_result_and_next_compare_has_no_old_mapping(self):
        self.install_snapshots(self.source_snapshots())
        with self.upload_patch({"pair_features": self.mapping()}):
            self.app.run()
            self.app.button(key="run_pair").click().run()
            self.assertEqual(self.result()["report"]["summary"]["affected_features"], 1)
        self.app.run()
        self.assert_clean()
        self.assertEqual(len(self.app.metric), 0)
        self.assertFalse(any(item.key == "report_json" for item in self.app.get("download_button")))
        self.app.button(key="run_pair").click().run()
        self.assertEqual(self.result()["report"]["summary"]["affected_features"], 0)

    def test_source_package_pair_is_blocked(self):
        session = self.app.session_state.work_session
        source = service.prepare_upload(session, "app.py", b"def f(): return 1\n")
        package = service.prepare_upload(session, "app.apk", self.apk("{}"))
        self.install_snapshots([source, package])
        self.assert_blocked()

    def test_local_failure_does_not_register_half_a_pair(self):
        before, _ = self.source_files()
        self.local_side("base", before)
        self.local_side("target", self.work / "missing.py")
        self.app.button(key="run_pair").click().run()
        self.assert_clean()
        self.assertTrue(self.app.error)
        self.assertEqual(self.app.session_state.snapshots, [])
        self.assertFalse(self.app.session_state.pair_analysis)

    def create_git_pair(self, filename="app.py"):
        repo = self.work / "repository"
        repo.mkdir()
        hooks, config = self.work / "empty-hooks", self.work / "empty-config"
        hooks.mkdir()
        config.write_text("", encoding="ascii")
        env = conversion._git_env()
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(config), GIT_CONFIG_COUNT="0")
        env.pop("GIT_CONFIG_PARAMETERS", None)
        def run(*args):
            result = subprocess.run([conversion._git_executable(), "-c", f"safe.directory={repo}",
                "-c", f"core.hooksPath={hooks}", "-c", f"init.templateDir={hooks}", "-c", "commit.gpgsign=false",
                "-c", "core.autocrlf=false", "-c", "user.name=QA fixture", "-c", "user.email=qa@example.invalid",
                "-C", str(repo), *args], shell=False, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
            if result.returncode:
                raise RuntimeError(result.stderr.decode("utf-8", "replace"))
            return result.stdout.decode("utf-8", "replace").strip()
        run("init", "-q", "--initial-branch=main")
        first = "def f(x):\n    return x < 30\n" if filename.endswith(".py") else "previous behavior\n"
        second = "def f(x):\n    return x <= 30\n" if filename.endswith(".py") else "current behavior\n"
        (repo / filename).write_text(first, encoding="utf-8")
        run("add", filename)
        run("commit", "-q", "-m", "Previous policy")
        previous = run("rev-parse", "HEAD")
        (repo / filename).write_text(second, encoding="utf-8")
        run("commit", "-q", "-am", "Update policy")
        return repo, previous, run("rev-parse", "HEAD")

    def git_side(self, side, repo):
        self.app.segmented_control(key=f"{side}_method").set_value("Git").run()
        self.app.text_input(key=f"{side}_location").set_value(str(repo)).run()

    def query_git(self, side, repo):
        self.git_side(side, repo)
        self.app.button(key=f"{side}_load_history").click().run()
        self.assert_clean()

    def test_git_pair_defaults_previous_latest_and_one_button_shows_actual_diff(self):
        repo, previous, latest = self.create_git_pair()
        self.git_side("base", repo)
        self.git_side("target", repo)
        with patch.object(service, "list_git_history", wraps=service.list_git_history) as history:
            self.app.button(key="target_load_history").click().run()
            self.assert_clean()
            self.assertEqual(history.call_count, 1)
        self.assertEqual(self.app.selectbox(key="base_commit").value, previous)
        self.assertEqual(self.app.selectbox(key="target_commit").value, latest)
        self.app.button(key="run_pair").click().run()
        result = self.result()
        self.assertEqual(result["mode"], "코드 영향")
        self.assert_actual_boundary_diff(result)
        self.assertEqual([item["manifest"]["source"]["commit_sha"] for item in self.app.session_state.snapshots], [previous, latest])

    def test_git_text_pair_auto_mode_shows_content_difference(self):
        repo, _, _ = self.create_git_pair("README.md")
        self.query_git("base", repo)
        self.query_git("target", repo)
        self.app.button(key="run_pair").click().run()
        result = self.result()
        self.assertEqual(result["mode"], "파일 구성")
        diff = result["file_evidence"]["details"]["README.md"]["diff"]
        self.assertIn("-previous behavior", diff)
        self.assertIn("+current behavior", diff)

    def test_git_and_local_source_compare_on_same_page(self):
        repo, previous, _ = self.create_git_pair()
        self.query_git("base", repo)
        self.local_side("target", repo)
        self.assertEqual(self.app.selectbox(key="base_commit").value, previous)
        self.app.button(key="run_pair").click().run()
        result = self.result()
        self.assertEqual(result["mode"], "코드 영향")
        self.assert_actual_boundary_diff(result)
        self.assertEqual([item["manifest"]["source"]["kind"] for item in self.app.session_state.snapshots], ["git", "local"])

    def test_changed_repository_invalidates_old_history(self):
        repo, _, _ = self.create_git_pair()
        self.query_git("base", repo)
        self.app.text_input(key="base_location").set_value(str(self.work / "different-repository")).run()
        self.assert_clean()
        self.assertFalse(any(widget.key == "base_commit" for widget in self.app.selectbox))
        self.assertTrue(self.app.button(key="run_pair").disabled)

    def test_same_git_sha_is_blocked(self):
        repo, _, latest = self.create_git_pair()
        self.query_git("base", repo)
        self.query_git("target", repo)
        self.app.selectbox(key="base_commit").select(latest).run()
        self.assert_blocked()
        self.assertEqual(self.app.session_state.snapshots, [])

    def test_local_disabled_policy_hides_local_method_and_rejects_local_git(self):
        with patch.dict(os.environ, {"QA_WEB_ALLOW_LOCAL": "0"}):
            self.app = AppTest.from_file(str(ROOT / "streamlit_app.py"), default_timeout=20).run()
            self.assert_clean()
            for side in ("base", "target"):
                self.assertNotIn("로컬 경로", self.app.segmented_control(key=f"{side}_method").options)
            self.app.segmented_control(key="base_method").set_value("Git").run()
            self.app.text_input(key="base_location").set_value(str(self.work)).run()
            if any(item.key == "base_load_history" for item in self.app.button):
                button = self.app.button(key="base_load_history")
                if not button.disabled:
                    button.click().run()
            self.assert_clean()
            self.assertTrue(self.app.error or self.app.warning)
            self.assertEqual(self.app.session_state.snapshots, [])


if __name__ == "__main__":
    unittest.main()
