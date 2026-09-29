"""Offline service integration checks; no real network cloning is performed."""
from __future__ import annotations

import hashlib
import io
import json
import plistlib
import shutil
import stat
import subprocess
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ast_runtime import AST_ROOT
import qa_web_service as service
from code_comparison import build_comparison


def zipped(items):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, data in items:
            archive.writestr(path, data)
    return buffer.getvalue()


class WebServiceTests(unittest.TestCase):
    def setUp(self):
        self.work = ROOT / ".test_tmp" / ("web_" + uuid4().hex)
        self.work.mkdir(parents=True)
        self.session = service.new_session(self.work / "sessions")
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.work.resolve().parent != (ROOT / ".test_tmp").resolve() or self.work.is_symlink() or self.work.is_junction():
            raise RuntimeError("Unsafe web test cleanup path")
        def readonly_retry(function, path, error):
            target = Path(path)
            if not target.resolve().is_relative_to(self.work.resolve()) or target.is_symlink() or target.is_junction():
                raise RuntimeError("Unsafe web test readonly cleanup") from error
            target.chmod(target.stat().st_mode | stat.S_IWRITE)
            function(path)
        shutil.rmtree(self.work, onexc=readonly_retry)

    def apk(self, data):
        return zipped([("AndroidManifest.xml", b"<manifest/>"),
                       ("classes.dex", b"dex\n035\x00" + data)])

    def test_clear_session_deletes_owned_copies_reports_and_readonly_files_only(self):
        original = self.work / "original.py"
        original.write_text("x = 1\n")
        service.prepare_local(self.session, str(original))
        report = self.session / "ast_reports" / "test.md"
        report.parent.mkdir()
        report.write_text("test report")
        report.chmod(stat.S_IREAD)
        other = service.new_session(self.session.parent)
        marker = other / "keep.txt"
        marker.write_text("other session")
        service.clear_session(self.session)
        self.assertFalse(self.session.exists())
        self.assertEqual(original.read_text(), "x = 1\n")
        self.assertEqual(marker.read_text(), "other session")

    def test_clear_session_rejects_missing_or_modified_ownership(self):
        for value in (None, "wrong-session"):
            with self.subTest(marker=value):
                marker = self.session / ".qa-web-session"
                if value is None:
                    marker.unlink()
                else:
                    marker.write_text(value)
                with self.assertRaisesRegex(ValueError, "소유"):
                    service.clear_session(self.session)
                self.assertTrue(self.session.exists())

    def test_clear_session_refuses_reparse_child_before_deleting_any_files(self):
        child = self.session / "linked-folder"
        child.mkdir()
        original = service.conversion._is_reparse
        with mock.patch.object(service.conversion, "_is_reparse", side_effect=lambda path: Path(path) == child or original(path)):
            with self.assertRaisesRegex(ValueError, "링크"):
                service.clear_session(self.session)
        self.assertTrue((self.session / ".qa-web-session").is_file())
        self.assertTrue(child.is_dir())

    def test_python_uploads_compare_semantics_and_tc_without_execution(self):
        sentinel = self.work / "executed"
        prefix = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n"
        before = service.prepare_upload(self.session, "before.py", (prefix + "def gate(x): return x < 30\n").encode())
        after = service.prepare_upload(self.session, "after.py", (prefix + "def gate(x): return x <= 30\n").encode())
        features = {"features": [{"id": "LOGIN", "name": "로그인", "entry_points": [{"file": "after.py", "symbol": "gate"}], "tc_ids": ["TC-001"]}]}
        report = service.compare_prepared(self.session, before, after, features_json=features)
        self.assertFalse(sentinel.exists())
        self.assertEqual([(c["file"], c["symbol"]) for c in report["changes"]], [("after.py", "gate")])
        self.assertEqual(report["changes"][0]["features"][0]["tc_ids"], ["TC-001"])

    def test_engine_project_zip_preserves_assets_and_detects_version(self):
        data = zipped([("Assets/Scripts/Policy.cs", b"class Policy {}"),
                       ("Assets/Temp/Screen.prefab", b"%YAML 1.1"),
                       ("ProjectSettings/ProjectVersion.txt", b"m_EditorVersion: 6000.0.0f1\n")])
        manifest = service.prepare_upload(self.session, "project.zip", data)
        self.assertEqual(manifest["engine"]["name"], "Unity")
        self.assertEqual(manifest["engine"]["version"], "6000.0.0f1")
        self.assertFalse(manifest["capabilities"]["python_ast"])
        self.assertIn("Assets/Temp/Screen.prefab", [f["path"] for f in manifest["files"]])
        self.assertEqual(manifest["source"]["upload_sha256"], hashlib.sha256(data).hexdigest())

    def test_project_zip_rejects_traversal_and_case_collisions_before_any_job(self):
        for entries in ([("../outside.py", "bad")], [("A.py", "a"), ("a.py", "b")]):
            with self.subTest(entries=entries):
                with self.assertRaises(ValueError):
                    service.prepare_upload(self.session, "project.zip", zipped(entries))
        self.assertFalse((self.work / "outside.py").exists())
        self.assertFalse((self.session / "input").exists())

    def test_upload_filename_and_size_are_bounded(self):
        for name in ("../app.py", "C:/app.py", "a\\app.py", "app.exe", "NUL.py"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                service.prepare_upload(self.session, name, b"x=1")
        with mock.patch.object(service, "MAX_UPLOAD_BYTES", 2), self.assertRaises(ValueError):
            service.prepare_upload(self.session, "app.py", b"x=1")

    def test_zip_source_root_matches_package_paths(self):
        left = service.prepare_upload(self.session, "left.zip", zipped([("src/pkg/app.py", "def f(): return 1"), ("README.md", "outside")]), source_root="src")
        right = service.prepare_upload(self.session, "right.zip", zipped([("src/pkg/app.py", "def f(): return 2")]), source_root="src")
        report = service.compare_prepared(self.session, left, right)
        self.assertEqual([(c["file"], c["symbol"]) for c in report["changes"]], [("pkg/app.py", "f")])

    def test_inventory_apk_change_and_original_package_rejection(self):
        before = service.prepare_upload(self.session, "before.apk", self.apk(b"before"))
        after = service.prepare_upload(self.session, "after.apk", self.apk(b"after"))
        report = service.compare_inventory(before, after)
        self.assertEqual([(c["path"], c["type"]) for c in report["changes"]], [("classes.dex", "modified")])
        self.assertEqual(report["summary"]["unchanged"], 1)
        original = service.prepare_upload(self.session, "app.py", b"x=1")
        with self.assertRaisesRegex(ValueError, "원본|APK"):
            service.compare_inventory(original, after)

    def test_apk_and_ipa_inventory_are_not_cross_platform_diffs(self):
        apk = service.prepare_upload(self.session, "app.apk", self.apk(b"data"))
        plist = plistlib.dumps({"CFBundleIdentifier": "test.app", "CFBundleExecutable": "Game"}, fmt=plistlib.FMT_BINARY)
        ipa = service.prepare_upload(self.session, "app.ipa", zipped([("Payload/Game.app/Info.plist", plist), ("Payload/Game.app/Game", b"\xcf\xfa\xed\xfe")]))
        with self.assertRaisesRegex(ValueError, "APK|IPA"):
            service.compare_inventory(apk, ipa)

    def test_package_tampering_is_detected_before_hash_report(self):
        first = service.prepare_upload(self.session, "one.apk", self.apk(b"same"))
        second = service.prepare_upload(self.session, "two.apk", self.apk(b"same"))
        (Path(second["content_root"]) / "classes.dex").write_bytes(b"tampered")
        with self.assertRaisesRegex(ValueError, "수정"):
            service.compare_inventory(first, second)

    def test_snapshot_download_is_portable_and_keeps_original_bytes(self):
        original = b"def f(): return 1\n"
        manifest = service.prepare_upload(self.session, "app.py", original)
        data = service.make_snapshot_download(manifest)
        unpacked = self.work / "downloaded"
        unpacked.mkdir()
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            portable = json.loads(archive.read("manifest.json"))
            self.assertEqual(portable["output_path"], ".")
            self.assertEqual(portable["content_root"], "content")
            self.assertEqual(portable["source"]["path"], "app.py")
            self.assertNotIn(str(self.session), archive.read("manifest.json").decode())
            self.assertEqual(archive.read("content/app.py"), original)
            archive.extractall(unpacked)  # Archive produced by the service above.
        report = build_comparison(unpacked, Path(manifest["output_path"]))
        self.assertEqual(report["summary"]["total_changes"], 0)
        with mock.patch.object(service, "MAX_DOWNLOAD_BYTES", 1), self.assertRaises(ValueError):
            service.make_snapshot_download(manifest)

    def test_remote_git_url_validation_prevents_clone_on_invalid_input(self):
        invalid = ["http://github.com/a/b", "https://evil.example/a/b", "https://user:pass@github.com/a/b", "https://github.com/a/b?x=1", "https://github.com/a/b#main", "https://github.com/a/b/tree/main", "https://github.com/a/%2e%2e", "https://github.com:443/a/b"]
        with mock.patch.object(service.subprocess, "run") as process:
            for url in invalid:
                with self.subTest(url=url), self.assertRaises(ValueError):
                    service.prepare_git(self.session, url)
            process.assert_not_called()

    def test_remote_clone_uses_isolated_bare_command_and_anonymous_env(self):
        actual_convert = service.conversion.convert_input
        def clone(args, **kwargs):
            repo = Path(args[-1])
            repo.mkdir()
            (repo / "app.py").write_text("def f(): return 1", encoding="utf-8")
            return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
        def convert(repo, **kwargs):
            # Offline fixture converter; actual Git object/ref export is covered
            # by CLI conversion tests rather than invented by this mock.
            self.assertEqual(kwargs["kind"], "git")
            result = actual_convert(repo, output=kwargs["output"])
            result["source"]["kind"] = "git"
            return result
        with mock.patch.dict(service.os.environ, {"GIT_ASKPASS": "must-not-execute", "SSH_ASKPASS": "must-not-execute"}), mock.patch.object(service.conversion, "_git_executable", return_value="git"), mock.patch.object(service.subprocess, "run", side_effect=clone) as process, mock.patch.object(service.conversion, "convert_input", side_effect=convert):
            result = service.prepare_git(self.session, "https://github.com/owner/repo", ref="main")
        args, kwargs = process.call_args
        self.assertIn("--bare", args[0])
        self.assertIn("--no-local", args[0])
        self.assertFalse(kwargs["shell"])
        self.assertEqual(kwargs["env"]["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(kwargs["env"]["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertNotIn("GIT_ASKPASS", kwargs["env"])
        self.assertNotIn("SSH_ASKPASS", kwargs["env"])
        self.assertIn("core.askPass=", args[0])
        self.assertEqual(result["source"]["remote_url"], "https://github.com/owner/repo.git")

    def test_failed_remote_clone_cleans_only_new_session_input(self):
        sentinel = self.work / "preserved.txt"
        sentinel.write_text("keep", encoding="utf-8")
        with mock.patch.object(service.conversion, "_git_executable", return_value="git"), mock.patch.object(service.subprocess, "run", return_value=SimpleNamespace(returncode=1, stdout=b"", stderr=b"fixture failure")):
            with self.assertRaises(ValueError):
                service.prepare_git(self.session, "https://github.com/owner/repo")
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertEqual(list((self.session / "input").iterdir()), [])

    def test_invalid_zip_and_clone_timeout_are_user_errors(self):
        with self.assertRaises(ValueError):
            service.prepare_upload(self.session, "invalid.zip", b"not a ZIP")
        with self.assertRaises(ValueError):
            service.prepare_upload(self.session, "invalid.apk", b"not a ZIP")
        with mock.patch.object(service.conversion, "_git_executable", return_value="git"), mock.patch.object(service.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 180)):
            with self.assertRaisesRegex(ValueError, "시간"):
                service.prepare_git(self.session, "https://github.com/owner/repo")

    def test_empty_python_baseline_is_valid_and_session_scope_is_enforced(self):
        before = service.prepare_upload(self.session, "empty.py", b"")
        after = service.prepare_upload(self.session, "after.py", b"def f(): return 1")
        report = service.compare_prepared(self.session, before, after)
        self.assertIn("f", [c["symbol"] for c in report["changes"]])
        other = service.new_session(self.work / "other_sessions")
        foreign = service.prepare_upload(other, "foreign.py", b"def f(): return 2")
        with self.assertRaisesRegex(ValueError, "세션"):
            service.compare_prepared(self.session, before, foreign)

    def test_server_local_path_policy_cannot_be_bypassed_by_local_git(self):
        with mock.patch.dict(service.os.environ, {"QA_WEB_ALLOW_LOCAL": "0"}):
            with self.assertRaisesRegex(ValueError, "로컬"):
                service.prepare_local(self.session, self.work)
            with self.assertRaisesRegex(ValueError, "로컬"):
                service.prepare_git(self.session, self.work)
        self.assertFalse((self.session / "input").exists())

    def test_actual_bare_git_export_compares_against_dirty_original_source(self):
        try:
            git = service.conversion._git_executable()
        except ValueError:
            self.skipTest("Git executable unavailable")
        repo, bare, hooks = self.work / "repo", self.work / "bare", self.work / "hooks"
        repo.mkdir()
        hooks.mkdir()
        def run(path, *args):
            command = [git, "-c", f"safe.directory={path}", "-c", f"safe.directory={repo}", "-c", f"core.hooksPath={hooks}",
                       "-c", f"init.templateDir={hooks}", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false", "-C", str(path), *args]
            result = subprocess.run(command, shell=False, capture_output=True, env=service.conversion._git_env())
            if result.returncode:
                raise RuntimeError(result.stderr.decode("utf-8", "replace"))
            return result.stdout.decode().strip()
        run(repo, "init", "--quiet")
        source = repo / "app.py"
        source.write_text("def f(): return 1\n", encoding="utf-8")
        run(repo, "add", ".")
        run(repo, "-c", "user.name=QA Test", "-c", "user.email=qa@example.invalid", "commit", "--quiet", "-m", "baseline")
        sha = run(repo, "rev-parse", "HEAD")
        run(self.work, "clone", "--bare", "--no-hardlinks", str(repo), str(bare))
        committed = service.prepare_git(self.session, bare)
        self.assertEqual(committed["source"]["commit_sha"], sha)
        source.write_text("def f(): return 2\n", encoding="utf-8")
        local = service.prepare_local(self.session, repo)
        report = service.compare_prepared(self.session, committed, local)
        self.assertEqual([(c["file"], c["symbol"]) for c in report["changes"]], [("app.py", "f")])

    def test_blank_server_paths_do_not_read_current_directory(self):
        for path in ("", "   ", None):
            with self.subTest(path=path), self.assertRaises(ValueError):
                service.prepare_local(self.session, path)
            with self.subTest(path=path), self.assertRaises(ValueError):
                service.prepare_git(self.session, path)
        self.assertFalse((self.session / "input").exists())


if __name__ == "__main__":
    unittest.main()
