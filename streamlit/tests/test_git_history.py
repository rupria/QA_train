"""Git history integration checks; remote requests are mocked, never sent."""
from __future__ import annotations

import os
import shutil
import stat
import subprocess
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import qa_web_service as service


class GitHistoryTests(unittest.TestCase):
    def setUp(self):
        self.work = ROOT / ".test_tmp" / ("history_" + uuid4().hex)
        self.work.mkdir(parents=True)
        self.session = service.new_session(self.work / "sessions")
        self.hooks = self.work / "empty-hooks"
        self.hooks.mkdir()
        self.config = self.work / "empty-config"
        self.config.write_text("", encoding="ascii")
        self.git = service.conversion._git_executable()
        self.addCleanup(self.cleanup)

    def cleanup(self):
        expected = self.work.absolute()
        if (self.work.resolve() != expected or expected.parent != (ROOT / ".test_tmp").resolve()
                or service.conversion._is_reparse(self.work)):
            raise RuntimeError("Unsafe history fixture cleanup")
        def readonly_retry(function, path, error):
            target = Path(path)
            if not target.resolve().is_relative_to(expected) or service.conversion._is_reparse(target):
                raise RuntimeError("Unsafe history fixture permission change") from error
            target.chmod(target.stat().st_mode | stat.S_IWRITE)
            function(path)
        shutil.rmtree(expected, onexc=readonly_retry)

    def run_git(self, repo, *args, date=None):
        env = service.conversion._git_env()
        env.update(GIT_CONFIG_NOSYSTEM="1", GIT_CONFIG_GLOBAL=str(self.config), GIT_CONFIG_COUNT="0")
        env.pop("GIT_CONFIG_PARAMETERS", None)
        if date:
            env.update(GIT_AUTHOR_DATE=date, GIT_COMMITTER_DATE=date)
        command = [self.git, "-c", f"safe.directory={repo}", "-c", f"core.hooksPath={self.hooks}",
            "-c", f"init.templateDir={self.hooks}", "-c", "commit.gpgsign=false", "-c", "core.autocrlf=false",
            "-c", "user.name=QA Test", "-c", "user.email=qa@example.invalid", "-C", str(repo), *args]
        result = subprocess.run(command, shell=False, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, timeout=30)
        if result.returncode:
            raise AssertionError(result.stderr.decode("utf-8", "replace"))
        return result.stdout.decode("utf-8", "replace").strip()

    def make_repo(self, two=True):
        repo = self.work / "repo"
        repo.mkdir()
        self.run_git(repo, "init", "--initial-branch=main")
        (repo / "app.py").write_text("def limit(x): return x < 30\n", encoding="utf-8")
        self.run_git(repo, "add", "app.py")
        self.run_git(repo, "commit", "-m", "첫 버전\t정책", date="2026-01-01T01:02:03+09:00")
        first = self.run_git(repo, "rev-parse", "HEAD")
        if not two:
            return repo, first, None
        (repo / "app.py").write_text("def limit(x): return x <= 30\n", encoding="utf-8")
        self.run_git(repo, "add", "app.py")
        self.run_git(repo, "commit", "-m", "두 번째: 경계 수정", date="2026-01-02T04:05:06+09:00")
        return repo, first, self.run_git(repo, "rev-parse", "HEAD")

    def test_local_two_commits_preserve_dates_subjects_and_working_tree(self):
        repo, first, second = self.make_repo()
        self.run_git(repo, "config", "i18n.logOutputEncoding", "CP949")
        (repo / "app.py").write_text("# dirty worktree must stay dirty\n", encoding="utf-8")
        sentinel = repo / "never-executed"
        untracked = repo / "untracked.py"
        untracked.write_text(f"from pathlib import Path\nPath({str(sentinel)!r}).touch()\n", encoding="utf-8")
        before = (self.run_git(repo, "status", "--porcelain"), (repo / ".git" / "index").read_bytes(),
                  (repo / ".git" / "HEAD").read_bytes(), (repo / "app.py").read_bytes(), untracked.read_bytes())
        rows = service.list_git_history(self.session, repo)
        self.assertEqual([r["sha"] for r in rows], [second, first])
        self.assertEqual([r["date"] for r in rows], ["2026-01-02T04:05:06+09:00", "2026-01-01T01:02:03+09:00"])
        self.assertEqual([r["subject"] for r in rows], ["두 번째: 경계 수정", "첫 버전\t정책"])
        for row in rows:
            self.assertEqual(set(row), {"sha", "short_sha", "date", "subject"})
            self.assertTrue(row["sha"].startswith(row["short_sha"]))
        after = (self.run_git(repo, "status", "--porcelain"), (repo / ".git" / "index").read_bytes(),
                 (repo / ".git" / "HEAD").read_bytes(), (repo / "app.py").read_bytes(), untracked.read_bytes())
        self.assertEqual(after, before)
        self.assertFalse(sentinel.exists())

    def test_limit_and_pinned_older_commit(self):
        repo, first, second = self.make_repo()
        self.assertEqual([r["sha"] for r in service.list_git_history(self.session, repo, limit=1)], [second])
        self.assertEqual([r["sha"] for r in service.list_git_history(self.session, repo, ref=first)], [first])

    def test_merge_history_follows_first_parent(self):
        repo, first, _ = self.make_repo(two=False)
        self.run_git(repo, "checkout", "-b", "side")
        (repo / "side.txt").write_text("side", encoding="utf-8")
        self.run_git(repo, "add", "side.txt")
        self.run_git(repo, "commit", "-m", "side change", date="2026-01-02T01:00:00+09:00")
        side = self.run_git(repo, "rev-parse", "HEAD")
        self.run_git(repo, "checkout", "main")
        (repo / "app.py").write_text("def limit(x): return x <= 30\n", encoding="utf-8")
        self.run_git(repo, "add", "app.py")
        self.run_git(repo, "commit", "-m", "main change", date="2026-01-03T01:00:00+09:00")
        main = self.run_git(repo, "rev-parse", "HEAD")
        self.run_git(repo, "merge", "--no-ff", "side", "-m", "merge side", date="2026-01-04T01:00:00+09:00")
        merge = self.run_git(repo, "rev-parse", "HEAD")
        rows = service.list_git_history(self.session, repo)
        self.assertEqual([r["sha"] for r in rows], [merge, main, first])
        self.assertEqual(rows[1]["sha"], self.run_git(repo, "rev-parse", "HEAD^1"))
        self.assertNotIn(side, [r["sha"] for r in rows])

    def test_empty_repo_and_unknown_ref_have_actionable_errors(self):
        repo = self.work / "empty-repo"
        repo.mkdir()
        self.run_git(repo, "init", "--initial-branch=main")
        with self.assertRaises(ValueError):
            service.list_git_history(self.session, repo)
        repo, _, _ = self.make_repo(two=False)
        with self.assertRaises(ValueError):
            service.list_git_history(self.session, repo, ref="missing-branch")

    def test_invalid_ref_limit_and_location_reject_before_git(self):
        with mock.patch.object(service.conversion, "_git") as read_git, mock.patch.object(service, "_clone_remote") as clone:
            for ref in ("--help", "-n1", "", " ", "HEAD\n", "HEAD\x00", None):
                with self.subTest(ref=ref), self.assertRaises(ValueError):
                    service.list_git_history(self.session, "https://github.com/example/repo", ref=ref)
            for limit in (0, 201, True, 1.5, "50", None):
                with self.subTest(limit=limit), self.assertRaises(ValueError):
                    service.list_git_history(self.session, "https://github.com/example/repo", limit=limit)
            for location in (None, "", "   "):
                with self.subTest(location=location), self.assertRaises(ValueError):
                    service.list_git_history(self.session, location)
            read_git.assert_not_called()
            clone.assert_not_called()

    def test_local_policy_and_remote_url_guards(self):
        with mock.patch.dict(os.environ, {"QA_WEB_ALLOW_LOCAL": "0"}), mock.patch.object(service.conversion, "_git") as read_git:
            with self.assertRaisesRegex(ValueError, "로컬"):
                service.list_git_history(self.session, self.work)
            read_git.assert_not_called()
        with mock.patch.object(service.subprocess, "run") as run:
            for url in ("http://github.com/example/repo", "https://user@github.com/example/repo",
                        "https://github.com/example/repo?x=1", "https://github.com/example/repo/tree/main",
                        "https://evil.example/example/repo", "https://github.com/example/repo#main"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    service.list_git_history(self.session, url)
            run.assert_not_called()

    def test_remote_anonymous_clone_history_is_pinned_and_cleaned(self):
        sha = "a" * 40
        payload = f"{sha}\x00aaaaaaa\x002026-01-01T00:00:00Z\x00Remote\tmessage\x00".encode()
        captured = {}
        def cloned(args, **kwargs):
            captured.update(args=args, kwargs=kwargs)
            Path(args[-1]).mkdir()
            return SimpleNamespace(returncode=0, stderr=b"", stdout=b"")
        with mock.patch.dict(os.environ, {"GIT_ASKPASS": "must-not-run", "SSH_ASKPASS": "must-not-run"}), \
                mock.patch.object(service.subprocess, "run", side_effect=cloned), \
                mock.patch.object(service.conversion, "_git", side_effect=[(sha + "\n").encode(), payload]) as read_git:
            rows = service.list_git_history(self.session, "https://github.com/example/repo", ref="release")
        self.assertEqual(rows, [dict(sha=sha, short_sha="aaaaaaa", date="2026-01-01T00:00:00Z", subject="Remote\tmessage")])
        self.assertEqual(read_git.call_args_list[0].args[2], ["rev-parse", "--verify", "--end-of-options", "release^{commit}"])
        log = read_git.call_args_list[1].args[2]
        self.assertIn("--first-parent", log)
        self.assertIn("--encoding=UTF-8", log)
        self.assertEqual(log[-2:], [sha, "--"])
        self.assertNotIn("release", log)
        self.assertIn("--bare", captured["args"])
        self.assertIn("https://github.com/example/repo.git", captured["args"])
        self.assertFalse(captured["kwargs"]["shell"])
        env = captured["kwargs"]["env"]
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")
        self.assertNotIn("GIT_ASKPASS", env)
        self.assertNotIn("SSH_ASKPASS", env)
        self.assertEqual(env["GIT_NO_REPLACE_OBJECTS"], "1")
        self.assertEqual(env["GIT_NO_LAZY_FETCH"], "1")
        self.assertEqual(list((self.session / "input").iterdir()), [])

    def test_remote_timeout_and_log_error_clean_owned_clone(self):
        with mock.patch.object(service.subprocess, "run", side_effect=subprocess.TimeoutExpired("git", 180)):
            with self.assertRaisesRegex(ValueError, "시간"):
                service.list_git_history(self.session, "https://github.com/example/repo")
        self.assertEqual(list((self.session / "input").iterdir()), [])
        def cloned(args, **kwargs):
            Path(args[-1]).mkdir()
            return SimpleNamespace(returncode=0, stderr=b"", stdout=b"")
        with mock.patch.object(service.subprocess, "run", side_effect=cloned), \
                mock.patch.object(service.conversion, "_git", side_effect=ValueError("unknown ref")):
            with self.assertRaisesRegex(ValueError, "unknown ref"):
                service.list_git_history(self.session, "https://github.com/example/repo")
        self.assertEqual(list((self.session / "input").iterdir()), [])

    def test_malformed_delimiters_and_hashes_are_rejected(self):
        sha = "b" * 40
        for payload in (b"incomplete\x00row\x00", f"bad\x00bad\x00date\x00subject\x00".encode(),
                        f"{sha}\x00ccccccc\x00date\x00subject\x00".encode()):
            with self.subTest(payload=payload), \
                    mock.patch.object(service.conversion, "_git", side_effect=[sha.encode(), payload]), \
                    self.assertRaises(ValueError):
                service.list_git_history(self.session, self.work)


if __name__ == "__main__":
    unittest.main()
