from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import sys
import unittest
import zipfile
from pathlib import Path
from uuid import uuid4
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import artifact_conversion
from artifact_conversion import convert_input
from code_comparison import build_comparison, write_comparison


class ConversionTests(unittest.TestCase):
    def setUp(self):
        self.temp_root = ROOT / ".test_tmp"
        self.temp_root.mkdir(exist_ok=True)
        self.work = self.temp_root / f"conversion_{uuid4().hex}"
        self.work.mkdir()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        if self.work.resolve().parent != self.temp_root.resolve() or self.work.is_symlink() or self.work.is_junction():
            raise RuntimeError("Refusing cleanup outside test workspace")
        def remove_readonly(function, path, exception):
            target = Path(path)
            if not target.resolve().is_relative_to(self.work.resolve()) or target.is_symlink() or target.is_junction():
                raise RuntimeError("Refusing permission change outside the test workspace") from exception
            target.chmod(target.stat().st_mode | stat.S_IWRITE)
            function(path)
        shutil.rmtree(self.work, onexc=remove_readonly)

    def write(self, root, relative, content):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode("utf-8"))
        return path

    def apk(self, entries, name="input.apk"):
        path = self.work / name
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
            for member, data in entries:
                archive.writestr(member, data)
        return path

    def test_local_snapshot_keeps_bytes_hashes_and_never_executes_source(self):
        source = self.work / "project"
        sentinel = self.work / "executed.txt"
        code = f"from pathlib import Path\nPath({str(sentinel)!r}).write_text('executed')\n"
        original = self.write(source, "pkg/app.py", code)
        self.write(source, ".venv/Scripts/ignored.py", "bad syntax!")
        self.write(source, ".git/ignored", "internal")
        self.write(source, "__pycache__/ignored.pyc", b"cache")
        out = self.work / "snapshot"
        result = convert_input(source, output=out)
        self.assertEqual(result["snapshot_type"], "qa_conversion")
        self.assertEqual(result["status"], "prepared")
        self.assertEqual(result["representation"], "original_source")
        self.assertTrue(result["capabilities"]["python_ast"])
        self.assertFalse(sentinel.exists())
        copied = out / "content/pkg/app.py"
        self.assertEqual(copied.read_bytes(), original.read_bytes())
        record = next(f for f in result["files"] if f["path"] == "pkg/app.py")
        self.assertEqual(record["sha256"], hashlib.sha256(original.read_bytes()).hexdigest())
        self.assertFalse((out / "content/.venv").exists())
        self.assertFalse((out / "content/.git").exists())
        self.assertTrue((out / "manifest.json").is_file())
        self.assertTrue((out / "conversion.md").is_file())

    def test_explicit_source_root_matches_import_root(self):
        source = self.work / "repo"
        self.write(source, "src/pkg/app.py", "def f():\n    return 1\n")
        self.write(source, "README.md", "outside source root")
        out = self.work / "snapshot"
        result = convert_input(source, source_root="src", output=out)
        self.assertEqual({f["path"] for f in result["files"]}, {"pkg/app.py"})
        self.assertTrue((out / "content/pkg/app.py").is_file())

    def test_unity_project_identifies_version_and_preserves_assets(self):
        source = self.work / "unity"
        self.write(source, "Assets/Scripts/Policy.cs", "class Policy {}\n")
        self.write(source, "Assets/Scenes/Login.unity", "%YAML 1.1\n")
        self.write(source, "Assets/Temp/preserved.prefab", "%YAML 1.1\n")
        self.write(source, "ProjectSettings/ProjectVersion.txt", "m_EditorVersion: 6000.0.0f1\n")
        self.write(source, "Library/cache.bin", b"cache")
        result = convert_input(source, kind="engine", output=self.work / "snapshot")
        self.assertEqual(result["engine"]["name"].lower(), "unity")
        self.assertEqual(result["engine"]["version"], "6000.0.0f1")
        self.assertFalse(result["capabilities"]["python_ast"])
        self.assertIn("Assets/Scenes/Login.unity", {f["path"] for f in result["files"]})
        self.assertIn("Assets/Temp/preserved.prefab", {f["path"] for f in result["files"]})
        self.assertNotIn("Library/cache.bin", {f["path"] for f in result["files"]})
        with self.assertRaises(ValueError):
            build_comparison(self.work / "snapshot", self.work / "snapshot")

    def test_apk_inventory_is_not_original_source_or_validated_build(self):
        source = self.apk([
            ("AndroidManifest.xml", "<manifest package='example.test'/>") ,
            ("classes.dex", b"dex\n035\x00" + bytes(104)),
            ("lib/arm64-v8a/libil2cpp.so", b"\x7fELFfixture"),
            ("assets/bin/Data/Managed/Assembly-CSharp.dll", b"MZfixture"),
            ("assets/accidental.py", "def f(): return 1"),
        ])
        original = source.read_bytes()
        out = self.work / "snapshot"
        result = convert_input(source, output=out)
        self.assertEqual(result["representation"], "package_payload")
        self.assertTrue(result["capabilities"]["package_inventory"])
        self.assertFalse(result["capabilities"]["original_source"])
        self.assertFalse(result["capabilities"]["python_ast"])
        self.assertFalse(result["capabilities"]["restored_source"])
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(result["source"]["sha256"], hashlib.sha256(original).hexdigest())
        self.assertTrue((out / "content/classes.dex").exists())
        self.assertTrue(result["warnings"])
        with self.assertRaisesRegex(ValueError, "APK|패키지|Python"):
            build_comparison(out, out)

    def test_zip_path_traversal_absolute_drive_and_backslash_are_rejected(self):
        for i, path in enumerate(("../outside.py", "/outside.py", "C:/outside.py", "a\\..\\outside.py", "a/../../outside.py")):
            with self.subTest(path=path):
                source = self.apk([(path, "bad")], name=f"input{i}.apk")
                out = self.work / f"snapshot{i}"
                with self.assertRaises((ValueError, RuntimeError)):
                    convert_input(source, output=out)
                self.assertFalse(out.exists())
                self.assertFalse((self.work / "outside.py").exists())

    def test_zip_case_collision_and_symlink_are_rejected_before_extraction(self):
        source = self.apk([("res/a.txt", "a"), ("res/A.txt", "b")])
        with self.assertRaises((ValueError, RuntimeError)):
            convert_input(source, output=self.work / "collision")
        link_apk = self.work / "link.apk"
        entry = zipfile.ZipInfo("assets/link")
        entry.create_system = 3
        entry.external_attr = (0o120777 << 16)
        with zipfile.ZipFile(link_apk, "w") as archive:
            archive.writestr(entry, "../../outside")
        with self.assertRaises((ValueError, RuntimeError)):
            convert_input(link_apk, output=self.work / "link_snapshot")

    def test_apk_member_count_individual_and_total_size_limits(self):
        source = self.apk([("AndroidManifest.xml", "<manifest/>"), ("assets/a", b"1234"), ("assets/b", b"5678")])
        limits = (("MAX_APK_MEMBERS", 2), ("MAX_APK_MEMBER_BYTES", 3), ("MAX_APK_TOTAL_BYTES", 15))
        for name, value in limits:
            with self.subTest(limit=name), mock.patch.object(artifact_conversion, name, value):
                out = self.work / name
                with self.assertRaisesRegex(ValueError, "limit"):
                    convert_input(source, output=out)
                self.assertFalse(out.exists())

    def test_apk_file_directory_prefix_collision_and_missing_manifest(self):
        for i, entries in enumerate(([("AndroidManifest.xml", "<manifest/>"), ("assets/a", "file"), ("assets/a/b", "nested")],
                                     [("assets/only.txt", "not an APK")])):
            with self.subTest(entries=entries):
                source = self.apk(entries, name=f"bad{i}.apk")
                out = self.work / f"bad_snapshot{i}"
                with self.assertRaises(ValueError):
                    convert_input(source, output=out)
                self.assertFalse(out.exists())

    def test_apk_midstream_failure_cleans_only_new_output(self):
        source = self.apk([("AndroidManifest.xml", "<manifest/>"), ("assets/a", b"data")])
        original = source.read_bytes()
        out = self.work / "failed"
        with mock.patch.object(artifact_conversion, "_stream_copy", side_effect=OSError("fixture I/O failure")):
            with self.assertRaises(OSError):
                convert_input(source, output=out)
        self.assertFalse(out.exists())
        self.assertEqual(source.read_bytes(), original)

    def test_generic_project_modules_named_like_engine_caches_are_preserved(self):
        source = self.work / "generic"
        self.write(source, "pkg/bin/policy.py", "def f(): return 1\n")
        self.write(source, "Library/app.py", "def g(): return 2\n")
        self.write(source, "pkg/reports/view.py", "def render(): return 3\n")
        self.write(source, "reports/report.py", "def report(): return 4\n")
        result = convert_input(source, output=self.work / "snapshot")
        self.assertEqual({f["path"] for f in result["files"]}, {"pkg/bin/policy.py", "Library/app.py", "pkg/reports/view.py", "reports/report.py"})

    def test_output_overlap_existing_results_and_invalid_options_preserve_inputs(self):
        source = self.work / "project"
        original = self.write(source, "app.py", "def f(): return 1\n")
        existing = self.work / "existing"
        kept = self.write(existing, "keep.txt", "existing result")
        for kwargs in ({"output": source / "generated"}, {"output": source}, {"output": self.work}, {"output": existing},
                       {"output": self.work / "escape", "source_root": "../project"},
                       {"output": self.work / "badref", "ref": "HEAD"},
                       {"output": self.work / "badjadx", "jadx": "missing"}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises((ValueError, RuntimeError, FileExistsError)):
                    convert_input(source, **kwargs)
        self.assertEqual(original.read_text(), "def f(): return 1\n")
        self.assertEqual(kept.read_text(), "existing result")

    def test_binary_blob_copy_not_text_decoding(self):
        source = self.work / "project"
        binary = bytes(range(256))
        self.write(source, "assets/data.bin", binary)
        result = convert_input(source, output=self.work / "snapshot")
        self.assertEqual((self.work / "snapshot/content/assets/data.bin").read_bytes(), binary)
        self.assertEqual(result["files"][0]["sha256"], hashlib.sha256(binary).hexdigest())

    def git(self, repo, *args):
        command = ["git", "-c", f"safe.directory={repo.as_posix()}", "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", "-C", str(repo), *args]
        return subprocess.run(command, check=True, capture_output=True, text=True, encoding="utf-8").stdout.strip()

    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_git_exact_ref_vs_dirty_local_and_snapshot_comparison(self):
        repo = self.work / "repo"
        repo.mkdir()
        self.git(repo, "init", "--quiet")
        self.write(repo, "src/pkg/__init__.py", "")
        file = self.write(repo, "src/pkg/app.py", "def f(x):\n    return x < 30\n")
        self.git(repo, "add", ".")
        self.git(repo, "-c", "user.name=QA Test", "-c", "user.email=qa@example.invalid", "commit", "--quiet", "-m", "fixture baseline")
        sha = self.git(repo, "rev-parse", "HEAD")
        file.write_text("def f(x):\n    return x <= 30\n", encoding="utf-8")
        self.write(repo, "src/untracked.txt", "received local file")
        before = self.git(repo, "status", "--porcelain")
        committed = convert_input(repo, kind="git", ref="HEAD", source_root="src", output=self.work / "committed")
        local = convert_input(repo, source_root="src", output=self.work / "local")
        self.assertEqual(committed["source"]["commit_sha"], sha)
        self.assertEqual((self.work / "committed/content/pkg/app.py").read_text(), "def f(x):\n    return x < 30\n")
        self.assertFalse((self.work / "committed/content/untracked.txt").exists())
        self.assertTrue((self.work / "local/content/untracked.txt").exists())
        self.assertEqual(self.git(repo, "status", "--porcelain"), before)
        comparison = build_comparison(self.work / "committed", self.work / "local")
        self.assertEqual([(c["file"], c["symbol"]) for c in comparison["changes"]], [("pkg/app.py", "f")])
        self.assertEqual(comparison["conversion_inputs"]["base"]["source"]["commit_sha"], sha)
        with self.assertRaises(ValueError):
            write_comparison(comparison, "json", self.work / "committed/manifest.json")

    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_git_replacement_refs_do_not_change_fixed_commit_content(self):
        repo = self.work / "repo"
        repo.mkdir()
        self.git(repo, "init", "--quiet")
        source = self.write(repo, "app.py", "def f(): return 1\n")
        self.git(repo, "add", ".")
        self.git(repo, "-c", "user.name=QA Test", "-c", "user.email=qa@example.invalid", "commit", "--quiet", "-m", "original")
        original_sha = self.git(repo, "rev-parse", "HEAD")
        source.write_text("def f(): return 2\n", encoding="utf-8")
        self.git(repo, "add", ".")
        self.git(repo, "-c", "user.name=QA Test", "-c", "user.email=qa@example.invalid", "commit", "--quiet", "-m", "replacement")
        replacement_sha = self.git(repo, "rev-parse", "HEAD")
        self.git(repo, "replace", original_sha, replacement_sha)
        result = convert_input(repo, kind="git", ref=original_sha, output=self.work / "snapshot")
        self.assertEqual(result["source"]["commit_sha"], original_sha)
        self.assertEqual((self.work / "snapshot/content/app.py").read_text(), "def f(): return 1\n")

    @unittest.skipUnless(shutil.which("git"), "Git is required")
    def test_selected_source_root_file_can_compare_with_raw_file(self):
        repo = self.work / "repo"
        repo.mkdir()
        self.git(repo, "init", "--quiet")
        source = self.write(repo, "src/app.py", "def f(): return 1\n")
        self.git(repo, "add", ".")
        self.git(repo, "-c", "user.name=QA Test", "-c", "user.email=qa@example.invalid", "commit", "--quiet", "-m", "fixture")
        source.write_text("def f(): return 2\n", encoding="utf-8")
        for kind in ("git", "local"):
            out = self.work / kind
            result = convert_input(repo, kind=kind, source_root="src/app.py", output=out)
            self.assertTrue(result["source"]["selected_is_file"])
            comparison = build_comparison(out, source)
            expected = 1 if kind == "git" else 0
            self.assertEqual(comparison["summary"]["total_changes"], expected)

    def test_optional_jadx_candidates_stay_derived_and_cannot_enter_python_comparison(self):
        source = self.apk([("AndroidManifest.xml", "<manifest/>"), ("classes.dex", b"dex\n035\x00" + bytes(104))])
        out = self.work / "snapshot"
        def fake_converter(args, **kwargs):
            self.assertFalse(kwargs["shell"])
            destination = Path(args[args.index("-d") + 1])
            self.write(destination, "sources/example/Policy.java", "class Policy {}\n")
            return subprocess.CompletedProcess(args, 0, stdout=b"fixture tool", stderr=b"")
        with mock.patch.object(artifact_conversion, "_prepare_jadx", return_value=["fixture-jadx"]), \
             mock.patch.object(artifact_conversion.subprocess, "run", side_effect=fake_converter):
            result = convert_input(source, output=out, jadx="fixture-jadx")
        self.assertTrue(result["capabilities"]["restored_source"])
        self.assertFalse(result["capabilities"]["original_source"])
        self.assertFalse(result["restoration"]["original_equivalence"])
        self.assertEqual(result["representation"], "package_payload")
        self.assertTrue(result["restoration"]["files"])
        with self.assertRaises(ValueError):
            build_comparison(out, out)

    def test_optional_jadx_failure_retains_package_inventory_as_partial(self):
        source = self.apk([("AndroidManifest.xml", "<manifest/>"), ("classes.dex", b"dex\n035\x00" + bytes(104))])
        out = self.work / "snapshot"
        with mock.patch.object(artifact_conversion, "_prepare_jadx", return_value=["fixture-jadx"]), \
             mock.patch.object(artifact_conversion.subprocess, "run", side_effect=subprocess.TimeoutExpired("fixture-jadx", 1)):
            result = convert_input(source, output=out, jadx="fixture-jadx")
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["restoration"]["status"], "failed")
        self.assertFalse(result["capabilities"]["restored_source"])
        self.assertTrue((out / "content/classes.dex").is_file())
        self.assertTrue((out / "manifest.json").is_file())

    def test_conversion_snapshot_can_be_moved_between_computers(self):
        source = self.work / "project"
        self.write(source, "app.py", "def f(): return 1\n")
        old = self.work / "old_snapshot"
        convert_input(source, output=old)
        moved = self.work / "moved_snapshot"
        old.rename(moved)
        report = build_comparison(moved, source)
        self.assertEqual(report["summary"]["total_changes"], 0)
        self.assertEqual(report["conversion_inputs"]["base"]["snapshot_path"], str(moved.resolve()))

    def test_single_file_snapshot_and_raw_file_with_different_names(self):
        before = self.work / "before.py"
        after = self.work / "after.py"
        before.write_text("def f(x): return x < 30\n", encoding="utf-8")
        after.write_text("def f(x): return x <= 30\n", encoding="utf-8")
        out = self.work / "snapshot"
        convert_input(before, output=out)
        report = build_comparison(out, after)
        self.assertEqual([(c["file"], c["symbol"]) for c in report["changes"]], [("after.py", "f")])

    def test_partial_manifest_is_not_silently_compared(self):
        source = self.work / "project"
        self.write(source, "app.py", "def f(): return 1\n")
        out = self.work / "snapshot"
        convert_input(source, output=out)
        path = out / "manifest.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        data["status"] = "partial"
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "partial"):
            build_comparison(out, source)

    def test_modified_added_or_deleted_snapshot_files_cannot_claim_original_git_source(self):
        source = self.work / "project"
        self.write(source, "app.py", "def f(): return 1\n")
        for action in ("modify", "add", "delete"):
            out = self.work / action
            convert_input(source, output=out)
            if action == "modify":
                (out / "content/app.py").write_text("def f(): return 2\n", encoding="utf-8")
            elif action == "add":
                (out / "content/new.py").write_text("def g(): return 2\n", encoding="utf-8")
            else:
                (out / "content/app.py").unlink()
            with self.subTest(action=action):
                with self.assertRaisesRegex(ValueError, "변환 후"):
                    build_comparison(out, source)

    def test_report_cannot_overwrite_any_preserved_snapshot_file(self):
        source = self.work / "project"
        self.write(source, "app.py", "def f(): return 1\n")
        self.write(source, "config.json", '{"policy": "keep"}\n')
        out = self.work / "snapshot"
        convert_input(source, output=out)
        report = build_comparison(out, source)
        before = (out / "content/config.json").read_bytes()
        for output in (out / "content/config.json", out / "new_report.md", out / "manifest.json"):
            with self.subTest(output=output):
                with self.assertRaises(ValueError):
                    write_comparison(report, "both", output)
        self.assertEqual((out / "content/config.json").read_bytes(), before)

    def test_cli_creates_snapshot_and_reports_bad_input_as_error(self):
        source = self.work / "app.py"
        source.write_text("def f(): return 1\n", encoding="utf-8")
        out = self.work / "snapshot"
        result = subprocess.run([sys.executable, "-B", str(ROOT / "ast_analyzer.py"), "convert", str(source), "--output", str(out)],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((out / "manifest.json").is_file())
        failed = subprocess.run([sys.executable, "-B", str(ROOT / "ast_analyzer.py"), "convert", str(self.work / "missing.apk"), "--output", str(self.work / "bad")],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(failed.returncode, 1)
        self.assertFalse((self.work / "bad").exists())
        corrupt = self.work / "corrupt.apk"
        corrupt.write_bytes(b"not a zip")
        failed = subprocess.run([sys.executable, "-B", str(ROOT / "ast_analyzer.py"), "convert", str(corrupt), "--output", str(self.work / "corrupt")],
                                capture_output=True, text=True, encoding="utf-8")
        self.assertEqual(failed.returncode, 1)
        self.assertNotIn("Traceback", failed.stderr)
        self.assertFalse((self.work / "corrupt").exists())


if __name__ == "__main__":
    unittest.main()
