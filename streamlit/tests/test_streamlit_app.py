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
from ast_runtime import AST_ROOT
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

    def create_git_pair(self, filename="app.py", name="repository"):
        repo = self.work / name
        repo.mkdir()
        hooks, config = self.work / f"{name}-empty-hooks", self.work / f"{name}-empty-config"
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
        self.app.button(key=f"{side}_load_branches").click().run()
        self.app.button(key=f"{side}_load_history").click().run()
        self.assert_clean()

    def test_git_pair_defaults_previous_latest_and_one_button_shows_actual_diff(self):
        repo, previous, latest = self.create_git_pair()
        self.git_side("base", repo)
        self.git_side("target", repo)
        with patch.object(service, "list_git_branches", wraps=service.list_git_branches) as branches, \
                patch.object(service, "list_git_history", wraps=service.list_git_history) as history:
            self.app.button(key="target_load_branches").click().run()
            self.app.button(key="target_load_history").click().run()
            self.assert_clean()
            self.assertEqual(branches.call_count, 1)
            self.assertEqual(history.call_count, 1)
        self.assertEqual(self.app.selectbox(key="base_branch").value, "main")
        self.assertEqual(self.app.selectbox(key="target_branch").value, "main")
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

    def test_different_git_repositories_keep_independent_branch_lists(self):
        first, _, _ = self.create_git_pair(name="first-repository")
        second, _, _ = self.create_git_pair(name="second-repository")
        conversion._git(conversion._git_executable(), first, ["branch", "release-a"])
        conversion._git(conversion._git_executable(), second, ["branch", "release-b"])
        self.git_side("base", first)
        self.git_side("target", second)
        with patch.object(service, "list_git_branches", wraps=service.list_git_branches) as branches:
            self.app.button(key="base_load_branches").click().run()
            self.app.button(key="target_load_branches").click().run()
            self.assertEqual(branches.call_count, 2)
        self.assertEqual(self.app.selectbox(key="base_branch").options, ["main", "release-a"])
        self.assertEqual(self.app.selectbox(key="target_branch").options, ["main", "release-b"])
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
            for side in ("base", "target", "ast"):
                self.assertNotIn("로컬 경로", self.app.segmented_control(key=f"{side}_method").options)
            self.app.segmented_control(key="base_method").set_value("Git").run()
            self.app.text_input(key="base_location").set_value(str(self.work)).run()
            if any(item.key == "base_load_branches" for item in self.app.button):
                button = self.app.button(key="base_load_branches")
                if not button.disabled:
                    button.click().run()
            self.assert_clean()
            self.assertTrue(self.app.error or self.app.warning)
            self.assertEqual(self.app.session_state.snapshots, [])

    def test_single_ast_upload_is_independent_and_not_repeated_by_view_changes(self):
        import ast_ui
        import qa_ast_service
        self.assertEqual([tab.label for tab in self.app.tabs], ["비교", "AST 연결·해석", "스냅샷", "_AST"])
        self.assertTrue(self.app.button(key="run_ast").disabled)
        with self.upload_patch({"ast_upload": Uploaded("app.py", b"def f(x):\n    return x + 1\n")}), \
                patch.object(ast_ui, "analyze_prepared", wraps=qa_ast_service.analyze_prepared) as analyze, \
                patch.object(service, "prepare_upload", wraps=service.prepare_upload) as prepare, \
                patch.object(service, "compare_prepared") as compare:
            self.app.run()
            self.app.button(key="run_ast").click().run()
            self.assert_clean()
            result = self.app.session_state.ast_analysis
            self.assertEqual(result["report"]["status"], "complete")
            self.assertTrue(any("FunctionDef(" in item.value for item in self.app.code))
            self.assertIsNone(self.app.session_state.pair_analysis)
            self.assertEqual((analyze.call_count, prepare.call_count), (1, 1))
            self.app.segmented_control(key="ast_output_view").set_value("정리형").run()
            self.assert_clean()
            self.assertEqual((analyze.call_count, prepare.call_count), (1, 1))
            self.assertEqual(len(self.app.session_state.snapshots), 1)
            compare.assert_not_called()
        self.app.run()
        self.assert_clean()
        self.assertFalse(any(widget.key.startswith("ast_download_") for widget in self.app.get("download_button")))
        self.assertTrue(any("입력이 바뀌었습니다" in item.value for item in self.app.info))

    def test_single_ast_errors_are_downloadable_without_comparison(self):
        with self.upload_patch({"ast_upload": Uploaded("broken.py", b"def broken(:\n")}):
            self.app.run()
            self.app.button(key="run_ast").click().run()
            self.assert_clean()
            result = self.app.session_state.ast_analysis
            self.assertEqual(result["report"]["status"], "incomplete")
            self.assertIn("SyntaxError", result["documents"]["ast_tree.md"])
            self.assertTrue(self.app.warning)
            self.assertTrue(any(widget.key == "ast_download_ast_tree.md" for widget in self.app.get("download_button")))
            self.assertIsNone(self.app.session_state.pair_analysis)

    def test_file_tree_selection_shows_corresponding_ast_and_data_without_reanalysis(self):
        import ast_ui
        import qa_ast_service
        payload = io.BytesIO()
        with zipfile.ZipFile(payload, "w") as archive:
            archive.writestr("src/alpha.py", "def alpha():\n    return 1\n")
            archive.writestr("src/beta.py", "def beta():\n    return 2\n")
            archive.writestr("data/items.csv", "id\n1\n")
            archive.writestr("settings.json", "{}")
            archive.writestr("notes.ipynb", json.dumps({"cells": [
                {"cell_type": "code", "source": "first = 1"},
                {"cell_type": "markdown", "source": "note"},
                {"cell_type": "code", "source": "second = 2"},
            ]}))
        with self.upload_patch({"ast_upload": Uploaded("project.zip", payload.getvalue())}), \
                patch.object(ast_ui, "analyze_prepared", wraps=qa_ast_service.analyze_prepared) as analyze:
            self.app.run()
            self.app.button(key="run_ast").click().run()
            self.assert_clean()
            self.assertTrue(any("├── data/\n│   └── items.csv" in item.value for item in self.app.code))
            self.assertIn("settings.json", self.app.selectbox(key="ast_file_path").options)
            self.app.selectbox(key="ast_file_path").select("src/beta.py").run()
            self.assert_clean()
            self.assertTrue(any("name='beta'" in item.value for item in self.app.code))
            self.assertFalse(any("name='alpha'" in item.value for item in self.app.code))
            self.app.selectbox(key="ast_file_path").select("notes.ipynb").run()
            self.assertEqual(self.app.selectbox(key="ast_tree_path").options, ["notes.ipynb#cell-1", "notes.ipynb#cell-3"])
            self.app.selectbox(key="ast_tree_path").select("notes.ipynb#cell-3").run()
            self.assertTrue(any("id='second'" in item.value for item in self.app.code))
            self.app.selectbox(key="ast_file_path").select("data/items.csv").run()
            self.assert_clean()
            self.assertTrue(any("Python AST 대상이 아닙니다" in item.value for item in self.app.info))
            self.assertFalse(any(item.value.startswith("Module(") for item in self.app.code))
            details = next(item.value for item in self.app.dataframe if "상대 경로" in item.value.columns).iloc[0]
            self.assertEqual(details["상대 경로"], "data/items.csv")
            self.assertEqual(details["종류"], "데이터·리소스")
            self.assertEqual(details["크기 (bytes)"], 5)
            self.assertTrue(any(widget.key == "ast_download_file_tree.md" for widget in self.app.get("download_button")))
            self.app.selectbox(key="ast_file_path").select("src/alpha.py").run()
            self.assert_clean()
            self.assertTrue(any("name='alpha'" in item.value for item in self.app.code))
            self.assertEqual(analyze.call_count, 1)

    def test_single_ast_reuses_prepared_source_without_copying_it_again(self):
        manifest = self.source_snapshots()[0]
        self.app.session_state.snapshots = [{"label": "기존 소스", "manifest": manifest}]
        self.app.run()
        self.app.segmented_control(key="ast_method").set_value("준비된 입력").run()
        with patch.object(service, "prepare_upload") as prepare:
            self.app.button(key="run_ast").click().run()
            self.assert_clean()
            self.assertEqual(self.app.session_state.ast_analysis["report"]["snapshot_id"], manifest["id"])
            self.assertEqual(len(self.app.session_state.snapshots), 1)
            prepare.assert_not_called()

    def test_session_cleanup_removes_server_files_results_and_downloads(self):
        manifest = self.source_snapshots()[0]
        previous = self.app.session_state.work_session
        other = service.new_session(self.work)
        self.app.session_state.snapshots = [{"label": "테스트 소스", "manifest": manifest}]
        self.app.run()
        self.app.segmented_control(key="ast_method").set_value("준비된 입력").run()
        self.app.button(key="run_ast").click().run()
        self.assert_clean()
        self.assertTrue((previous / "ast_reports").is_dir())
        self.app.button(key="clear_work_session").click().run()
        self.assert_clean()
        self.assertFalse(previous.exists())
        self.assertTrue(other.is_dir())
        self.assertNotEqual(self.app.session_state.work_session, previous)
        self.assertEqual(self.app.session_state.snapshots, [])
        self.assertIsNone(self.app.session_state.ast_analysis)
        self.assertIsNone(self.app.session_state.pair_analysis)
        self.assertFalse(self.app.get("download_button"))
        self.assertTrue(any("삭제했습니다" in item.value for item in self.app.success))

    def test_single_git_ast_uses_one_selected_commit_and_keeps_checkout(self):
        repo, _, latest = self.create_git_pair()
        self.app.segmented_control(key="ast_method").set_value("Git").run()
        self.app.text_input(key="ast_location").set_value(str(repo)).run()
        self.app.text_input(key="ast_root").set_value("").run()
        self.assertEqual(self.app.text_input(key="ast_root").value, ".")
        self.app.button(key="ast_load_branches").click().run()
        self.app.button(key="ast_load_history").click().run()
        self.assertEqual(self.app.selectbox(key="ast_branch").value, "main")
        self.assertEqual(self.app.selectbox(key="ast_commit").value, latest)
        self.assertEqual(self.app.selectbox(key="ast_commit").label, "분석할 커밋")
        self.app.button(key="run_ast").click().run()
        self.assert_clean()
        result = self.app.session_state.ast_analysis
        self.assertEqual(result["report"]["input"]["commit_sha"], latest)
        self.assertIn("LtE(", result["trees"][0]["tree"])
        self.assertEqual(len(self.app.session_state.snapshots), 1)
        self.assertIsNone(self.app.session_state.pair_analysis)
        self.assertEqual(subprocess.run([shutil.which("git"), "status", "--porcelain"], cwd=repo, capture_output=True, check=True).stdout, b"")


if __name__ == "__main__":
    unittest.main()
