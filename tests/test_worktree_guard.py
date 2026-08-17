from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
GUARD = REPO / "oplan/scripts/worktree_guard.py"


class WorktreeGuardTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tempdir = tempfile.TemporaryDirectory()
        self.repo = Path(self.tempdir.name)
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "oplan test"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "oplan@example.invalid"], check=True)
        subprocess.run(
            ["git", "-C", str(self.repo), "commit", "--allow-empty", "-q", "-m", "baseline"], check=True
        )
        self.workspace = self.repo / ".oplan/test"
        (self.workspace / "attempts").mkdir(parents=True)
        (self.workspace / "control").mkdir()
        self.control = self.workspace / "control/1.1.json"
        self.control.write_text(
            json.dumps({"write_set": ["allowed.txt"]}) + "\n", encoding="utf-8"
        )
        self.snapshot = self.workspace / "attempts/executor-1.1-a1-before.json"

    def tearDown(self) -> None:
        self.tempdir.cleanup()

    def run_guard(self, *args: str | Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(GUARD), *(str(arg) for arg in args)],
            text=True,
            capture_output=True,
            check=False,
        )

    def capture(self) -> None:
        result = self.run_guard("capture", self.repo, self.snapshot, self.control)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_only_declared_write_passes(self) -> None:
        self.capture()
        (self.repo / "allowed.txt").write_text("ok\n", encoding="utf-8")
        result = self.run_guard(
            "check", self.repo, self.snapshot, self.control, self.workspace
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("worktree guard: PASS", result.stdout)

    def test_undeclared_write_fails(self) -> None:
        self.capture()
        (self.repo / "allowed.txt").write_text("ok\n", encoding="utf-8")
        (self.repo / "outside.txt").write_text("not allowed\n", encoding="utf-8")
        result = self.run_guard(
            "check", self.repo, self.snapshot, self.control, self.workspace
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("undeclared write: outside.txt", result.stdout)

    def test_expected_versioned_report_may_be_persisted_before_check(self) -> None:
        report_rel = ".oplan/test/attempts/executor-1.1-a1.report"
        captured = self.run_guard("capture", self.repo, self.snapshot, self.control, report_rel)
        self.assertEqual(captured.returncode, 0, captured.stdout + captured.stderr)
        (self.repo / report_rel).write_text("STATUS: done\n", encoding="utf-8")
        (self.repo / "allowed.txt").write_text("ok\n", encoding="utf-8")
        result = self.run_guard(
            "check", self.repo, self.snapshot, self.control, self.workspace
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_restore_reverts_pre_existing_dirty_file_to_exact_bytes(self) -> None:
        target = self.repo / "allowed.txt"
        target.write_text("before\n", encoding="utf-8")
        original_bytes = target.read_bytes()
        self.capture()
        target.write_text("attempt\n", encoding="utf-8")
        result = self.run_guard("restore", self.repo, self.snapshot, self.control)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("worktree guard: RESTORED", result.stdout)
        self.assertEqual(target.read_bytes(), original_bytes)

    def test_restore_deletes_newly_created_write_set_file(self) -> None:
        self.capture()
        (self.repo / "allowed.txt").write_text("new\n", encoding="utf-8")
        result = self.run_guard("restore", self.repo, self.snapshot, self.control)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertFalse((self.repo / "allowed.txt").exists())

    def test_restore_does_not_touch_paths_outside_write_set(self) -> None:
        outside = self.repo / "outside.txt"
        outside.write_text("original\n", encoding="utf-8")
        self.capture()
        outside.write_text("modified after capture\n", encoding="utf-8")
        result = self.run_guard("restore", self.repo, self.snapshot, self.control)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(outside.read_text(encoding="utf-8"), "modified after capture\n")

    def test_restore_fails_on_write_set_mismatch(self) -> None:
        self.capture()
        mismatched_control = self.workspace / "control/mismatch.json"
        mismatched_control.write_text(
            json.dumps({"write_set": ["allowed.txt", "extra.txt"]}) + "\n", encoding="utf-8"
        )
        result = self.run_guard("restore", self.repo, self.snapshot, mismatched_control)
        self.assertNotEqual(result.returncode, 0)


if __name__ == "__main__":
    unittest.main()
