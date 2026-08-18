from __future__ import annotations

import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
GUARD = REPO / "oplan/scripts/worktree_guard.py"


def downgrade_snapshot(path: Path, extra_states: dict[str, dict[str, str]] | None = None) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    data.pop("schema", None)

    def downgrade(value: str) -> str:
        parts = value.split(":")
        if parts[0] in ("file", "symlink") and len(parts) == 3:
            return f"{parts[0]}:{parts[2]}"
        if parts[0] == "directory":
            return "directory"
        return value

    data["states"] = {
        relative: {"worktree": downgrade(state["worktree"]), "index": state["index"]}
        for relative, state in data.get("states", {}).items()
    }
    data["write_set_states"] = {
        relative: downgrade(state) for relative, state in data.get("write_set_states", {}).items()
    }
    if extra_states is not None:
        data["states"].update(extra_states)
    path.write_text(json.dumps(data), encoding="utf-8")


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
        self.accepted = self.workspace / "attempts/accepted-state.json"

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

    def init_accepted(self) -> None:
        result = self.run_guard("init-accepted", self.repo, self.accepted)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def record(self, control: Path | None = None) -> subprocess.CompletedProcess[str]:
        return self.run_guard(
            "record-accepted", self.repo, control if control is not None else self.control, self.accepted
        )

    def verify(self) -> subprocess.CompletedProcess[str]:
        return self.run_guard("verify-accepted", self.repo, self.accepted)

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

    def test_capture_rejects_symlink_write_set(self) -> None:
        link = self.repo / "allowed.txt"
        target = self.repo / "target.txt"
        target.write_text("data\n", encoding="utf-8")
        try:
            link.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        result = self.run_guard("capture", self.repo, self.snapshot, self.control)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("traverses a symlink or junction", result.stdout)

    def test_capture_rejects_symlink_ancestor(self) -> None:
        real = self.repo / "realdir"
        real.mkdir()
        link = self.repo / "linkdir"
        try:
            link.symlink_to(real, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        self.control.write_text(
            json.dumps({"write_set": ["linkdir/allowed.txt"]}) + "\n", encoding="utf-8"
        )
        result = self.run_guard("capture", self.repo, self.snapshot, self.control)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("traverses a symlink or junction", result.stdout)

    def test_capture_rejects_symlink_descendant_in_directory_write_set(self) -> None:
        bundle = self.repo / "bundle"
        bundle.mkdir()
        (bundle / "real.txt").write_text("data\n", encoding="utf-8")
        outside_target = self.repo / "outside_target.txt"
        outside_target.write_text("x\n", encoding="utf-8")
        link = bundle / "link.txt"
        try:
            link.symlink_to(outside_target)
        except OSError as exc:
            self.skipTest(f"symlinks unavailable: {exc}")
        self.control.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        result = self.run_guard("capture", self.repo, self.snapshot, self.control)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("directory contains a symlink or junction", result.stdout)

    def test_restore_reverts_directory_tree(self) -> None:
        self.control.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        bundle = self.repo / "bundle"
        bundle.mkdir()
        before_file = bundle / "before.bin"
        before_file.write_bytes(b"\x00\xff")
        self.capture()
        before_file.unlink()
        (bundle / "after.txt").write_text("new\n", encoding="utf-8")
        result = self.run_guard("restore", self.repo, self.snapshot, self.control)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual((bundle / "before.bin").read_bytes(), b"\x00\xff")
        self.assertFalse((bundle / "after.txt").exists())

    def test_restore_reports_unsupported_symlink_state(self) -> None:
        (self.repo / "allowed.txt").write_text("before\n", encoding="utf-8")
        self.capture()
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        data["write_set_states"]["allowed.txt"] = "symlink:777:" + "0" * 64
        self.snapshot.write_text(json.dumps(data), encoding="utf-8")
        result = self.run_guard("restore", self.repo, self.snapshot, self.control)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "cannot restore symlink write_set path (unsupported): allowed.txt", result.stdout
        )

    def test_check_ignores_pytest_cache_writes(self) -> None:
        cache_file = self.repo / ".pytest_cache/v/cache/nodeids"
        cache_file.parent.mkdir(parents=True)
        cache_file.write_bytes(b"before")
        self.capture()
        cache_file.write_bytes(b"after-changed")
        (self.repo / "allowed.txt").write_text("ok\n", encoding="utf-8")
        result = self.run_guard("check", self.repo, self.snapshot, self.control, self.workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_check_accepts_write_set_path_with_different_casing(self) -> None:
        probe = self.repo / "case-probe"
        probe.write_text("x\n", encoding="utf-8")
        if not os.path.exists(self.repo / "CASE-PROBE"):
            probe.unlink()
            self.skipTest("case-sensitive filesystem")
        probe.unlink()
        self.control.write_text(json.dumps({"write_set": ["Allowed.TXT"]}) + "\n", encoding="utf-8")
        self.capture()
        (self.repo / "allowed.txt").write_text("ok\n", encoding="utf-8")
        result = self.run_guard("check", self.repo, self.snapshot, self.control, self.workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_capture_stamps_the_snapshot_state_grammar(self) -> None:
        self.capture()
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        self.assertEqual(data["schema"], "oplan-worktree-snapshot/v2")

    def test_check_accepts_pre_mode_snapshot_without_false_violations(self) -> None:
        (self.repo / "allowed.txt").write_text("before\n", encoding="utf-8")
        (self.repo / "outside.txt").write_text("original\n", encoding="utf-8")
        self.capture()
        downgrade_snapshot(self.snapshot)
        (self.repo / "allowed.txt").write_text("after\n", encoding="utf-8")
        result = self.run_guard("check", self.repo, self.snapshot, self.control, self.workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("predates the mode-tagged state grammar", result.stdout)
        self.assertNotIn("undeclared write", result.stdout)

    def test_check_ignores_snapshot_paths_outside_current_collection_membership(self) -> None:
        (self.repo / "allowed.txt").write_text("before\n", encoding="utf-8")
        self.capture()
        downgrade_snapshot(
            self.snapshot,
            {
                ".pytest_cache/CACHEDIR.TAG": {"worktree": "file:" + "a" * 64, "index": "b" * 64},
                ".pytest_cache/v/cache/nodeids": {"worktree": "file:" + "c" * 64, "index": "b" * 64},
            },
        )
        (self.repo / "allowed.txt").write_text("after\n", encoding="utf-8")
        result = self.run_guard("check", self.repo, self.snapshot, self.control, self.workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("undeclared write", result.stdout)
        self.assertNotIn(".pytest_cache", result.stdout)

    def test_check_rejects_unknown_snapshot_state_grammar(self) -> None:
        self.capture()
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        data["schema"] = "oplan-worktree-snapshot/v9"
        self.snapshot.write_text(json.dumps(data), encoding="utf-8")
        result = self.run_guard("check", self.repo, self.snapshot, self.control, self.workspace)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported snapshot state grammar", result.stdout)

    def test_restore_accepts_pre_mode_snapshot(self) -> None:
        (self.repo / "allowed.txt").write_bytes(b"before\n")
        self.capture()
        downgrade_snapshot(self.snapshot)
        (self.repo / "allowed.txt").write_text("attempt\n", encoding="utf-8")
        result = self.run_guard("restore", self.repo, self.snapshot, self.control)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("worktree guard: RESTORED", result.stdout)
        self.assertNotIn("restore mismatch", result.stdout)
        self.assertEqual((self.repo / "allowed.txt").read_bytes(), b"before\n")

    def test_restore_rejects_unknown_snapshot_state_grammar(self) -> None:
        self.capture()
        data = json.loads(self.snapshot.read_text(encoding="utf-8"))
        data["schema"] = "oplan-worktree-snapshot/v9"
        self.snapshot.write_text(json.dumps(data), encoding="utf-8")
        result = self.run_guard("restore", self.repo, self.snapshot, self.control)
        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported snapshot state grammar", result.stdout)

    def test_restore_reports_linklike_write_set_path(self) -> None:
        self.control.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        bundle = self.repo / "bundle"
        bundle.mkdir()
        (bundle / "before.bin").write_bytes(b"\x00\xff")
        self.capture()
        shutil.rmtree(bundle)
        if os.name != "nt":
            self.skipTest("junctions require Windows")
        outside_dir = Path(tempfile.mkdtemp(prefix="oplan-outside-"))
        try:
            result = subprocess.run(
                ["cmd", "/c", "mklink", "/J", str(bundle), str(outside_dir)],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                self.skipTest(f"mklink unavailable: {(result.stdout or result.stderr).strip()}")
            restore_result = self.run_guard("restore", self.repo, self.snapshot, self.control)
            self.assertEqual(restore_result.returncode, 2)
            self.assertIn(
                "is a symlink or junction; remove it and rerun restore: bundle",
                restore_result.stdout,
            )
            self.assertTrue(outside_dir.exists())
        finally:
            shutil.rmtree(outside_dir, ignore_errors=True)

    def test_check_rejects_bare_attempts_exclusion(self) -> None:
        result = self.run_guard(
            "capture", self.repo, self.snapshot, self.control, ".oplan/test/attempts"
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        check_result = self.run_guard(
            "check", self.repo, self.snapshot, self.control, self.workspace
        )
        self.assertEqual(check_result.returncode, 2)
        self.assertIn("snapshot excludes paths outside workspace attempts", check_result.stdout)

    def test_record_and_verify_accepted_file(self) -> None:
        self.init_accepted()
        (self.repo / "allowed.txt").write_text("data\n", encoding="utf-8")
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "oplan worktree guard: ACCEPTED (1 controls, 1 current paths)", result.stdout
        )
        verify_result = self.verify()
        self.assertEqual(verify_result.returncode, 0, verify_result.stdout + verify_result.stderr)
        self.assertIn(
            "oplan worktree guard: ACCEPTED STATE VERIFIED (1 controls, 1 paths)",
            verify_result.stdout,
        )

    def test_verify_accepted_detects_later_change(self) -> None:
        self.init_accepted()
        (self.repo / "allowed.txt").write_text("data\n", encoding="utf-8")
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (self.repo / "allowed.txt").write_text("changed\n", encoding="utf-8")
        verify_result = self.verify()
        self.assertNotEqual(verify_result.returncode, 0)
        self.assertIn("accepted state mismatch: allowed.txt", verify_result.stdout)

    def test_verify_accepted_hashes_directory_contents(self) -> None:
        self.control.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        bundle = self.repo / "bundle"
        bundle.mkdir()
        (bundle / "a.txt").write_text("one\n", encoding="utf-8")
        self.init_accepted()
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        (bundle / "a.txt").write_text("two\n", encoding="utf-8")
        verify_result = self.verify()
        self.assertNotEqual(verify_result.returncode, 0)
        self.assertIn("accepted state mismatch: bundle", verify_result.stdout)

    def test_verify_accepted_detects_index_change(self) -> None:
        self.init_accepted()
        (self.repo / "allowed.txt").write_text("data\n", encoding="utf-8")
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        subprocess.run(
            ["git", "-C", str(self.repo), "add", "--", "allowed.txt"], check=True
        )
        verify_result = self.verify()
        self.assertNotEqual(verify_result.returncode, 0)
        self.assertIn("accepted state mismatch: allowed.txt", verify_result.stdout)

    @unittest.skipIf(os.name == "nt", "Windows does not preserve Unix executable bits")
    def test_verify_accepted_detects_mode_change(self) -> None:
        target = self.repo / "allowed.txt"
        target.write_text("data\n", encoding="utf-8")
        self.init_accepted()
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        original_mode = target.stat().st_mode & 0o7777
        os.chmod(target, original_mode ^ 0o100)
        verify_result = self.verify()
        self.assertNotEqual(verify_result.returncode, 0)
        self.assertIn("accepted state mismatch: allowed.txt", verify_result.stdout)

    @unittest.skipIf(os.name == "nt", "Windows does not preserve Unix executable bits")
    def test_verify_accepted_detects_directory_root_mode_change(self) -> None:
        self.control.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        bundle = self.repo / "bundle"
        bundle.mkdir()
        (bundle / "a.txt").write_text("one\n", encoding="utf-8")
        self.init_accepted()
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        original_mode = bundle.stat().st_mode & 0o7777
        os.chmod(bundle, original_mode ^ 0o100)
        verify_result = self.verify()
        self.assertNotEqual(verify_result.returncode, 0)
        self.assertIn("accepted state mismatch: bundle", verify_result.stdout)

    @unittest.skipIf(os.name != "nt", "read-only attribute mode drift is Windows-observable")
    def test_verify_accepted_detects_read_only_mode_change_on_windows(self) -> None:
        target = self.repo / "allowed.txt"
        target.write_text("data\n", encoding="utf-8")
        self.init_accepted()
        record_result = self.record()
        self.assertEqual(record_result.returncode, 0, record_result.stdout + record_result.stderr)
        os.chmod(target, stat.S_IREAD)
        result = self.verify()
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepted state mismatch: allowed.txt", result.stdout)

    def test_accepted_directory_state_uses_the_tree_prefix(self) -> None:
        self.control.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        bundle = self.repo / "bundle"
        bundle.mkdir()
        (bundle / "a.txt").write_text("one\n", encoding="utf-8")
        self.init_accepted()
        result = self.record()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(self.accepted.read_text(encoding="utf-8"))
        worktree_state = data["write_set_states"]["bundle"]["worktree"]
        self.assertTrue(worktree_state.startswith("tree:"))
        self.assertFalse(worktree_state.startswith("directory:"))

    def test_record_accepted_rejects_a_foreign_manifest_schema(self) -> None:
        self.init_accepted()
        data = json.loads(self.accepted.read_text(encoding="utf-8"))
        data["schema"] = "oplan-accepted-state/v0"
        self.accepted.write_text(json.dumps(data), encoding="utf-8")
        (self.repo / "allowed.txt").write_text("data\n", encoding="utf-8")
        result = self.record()
        self.assertEqual(result.returncode, 2)
        self.assertIn("re-initialize the manifest", result.stdout)

    def test_later_accepted_control_may_overlap_and_replaces_current_state(self) -> None:
        self.init_accepted()
        (self.repo / "allowed.txt").write_text("first\n", encoding="utf-8")
        result_1 = self.record()
        self.assertEqual(result_1.returncode, 0, result_1.stdout + result_1.stderr)
        (self.repo / "allowed.txt").write_text("second\n", encoding="utf-8")
        control_2 = self.workspace / "control/1.2.json"
        control_2.write_text(json.dumps({"write_set": ["allowed.txt"]}) + "\n", encoding="utf-8")
        result_2 = self.record(control_2)
        self.assertEqual(result_2.returncode, 0, result_2.stdout + result_2.stderr)
        verify_result = self.verify()
        self.assertEqual(verify_result.returncode, 0, verify_result.stdout + verify_result.stderr)

    def test_record_accepted_rejects_drift_outside_new_write_set(self) -> None:
        self.init_accepted()
        (self.repo / "allowed.txt").write_text("first\n", encoding="utf-8")
        result_1 = self.record()
        self.assertEqual(result_1.returncode, 0, result_1.stdout + result_1.stderr)
        control_2 = self.workspace / "control/1.2.json"
        control_2.write_text(json.dumps({"write_set": ["other.txt"]}) + "\n", encoding="utf-8")
        (self.repo / "other.txt").write_text("new\n", encoding="utf-8")
        (self.repo / "allowed.txt").write_text("mutated\n", encoding="utf-8")
        result_2 = self.record(control_2)
        self.assertNotEqual(result_2.returncode, 0)
        self.assertIn(
            "accepted state drifted outside the accepted write set: allowed.txt", result_2.stdout
        )

    def test_record_accepted_leaves_manifest_unchanged_on_drift(self) -> None:
        self.init_accepted()
        (self.repo / "allowed.txt").write_text("first\n", encoding="utf-8")
        result_1 = self.record()
        self.assertEqual(result_1.returncode, 0, result_1.stdout + result_1.stderr)
        control_2 = self.workspace / "control/1.2.json"
        control_2.write_text(json.dumps({"write_set": ["other.txt"]}) + "\n", encoding="utf-8")
        (self.repo / "other.txt").write_text("new\n", encoding="utf-8")
        (self.repo / "allowed.txt").write_text("mutated\n", encoding="utf-8")
        before_bytes = self.accepted.read_bytes()
        result_2 = self.record(control_2)
        self.assertNotEqual(result_2.returncode, 0)
        self.assertEqual(self.accepted.read_bytes(), before_bytes)

    def test_record_accepted_rejects_sibling_drift_in_a_recorded_directory(self) -> None:
        self.control.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        bundle = self.repo / "bundle"
        bundle.mkdir()
        (bundle / "x.txt").write_text("x1\n", encoding="utf-8")
        (bundle / "z.txt").write_text("z1\n", encoding="utf-8")
        self.init_accepted()
        result_1 = self.record()
        self.assertEqual(result_1.returncode, 0, result_1.stdout + result_1.stderr)
        (bundle / "z.txt").write_text("z2-behind-the-back\n", encoding="utf-8")
        (bundle / "x.txt").write_text("x2-new-bytes\n", encoding="utf-8")
        control_2 = self.workspace / "control/1.2.json"
        control_2.write_text(
            json.dumps({"write_set": ["bundle/x.txt"]}) + "\n", encoding="utf-8"
        )
        before_bytes = self.accepted.read_bytes()
        result_2 = self.record(control_2)
        self.assertNotEqual(result_2.returncode, 0)
        self.assertIn(
            "accepted state drifted in an undeclared parent directory; add it to the write set: bundle",
            result_2.stdout,
        )
        self.assertEqual(self.accepted.read_bytes(), before_bytes)

    def test_record_accepted_refreshes_a_directory_the_new_control_declares(self) -> None:
        self.control.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        bundle = self.repo / "bundle"
        bundle.mkdir()
        (bundle / "x.txt").write_text("x1\n", encoding="utf-8")
        (bundle / "z.txt").write_text("z1\n", encoding="utf-8")
        self.init_accepted()
        result_1 = self.record()
        self.assertEqual(result_1.returncode, 0, result_1.stdout + result_1.stderr)
        (bundle / "x.txt").write_text("x2-new-bytes\n", encoding="utf-8")
        control_2 = self.workspace / "control/1.2.json"
        control_2.write_text(json.dumps({"write_set": ["bundle"]}) + "\n", encoding="utf-8")
        result_2 = self.record(control_2)
        self.assertEqual(result_2.returncode, 0, result_2.stdout + result_2.stderr)
        verify_result = self.verify()
        self.assertEqual(verify_result.returncode, 0, verify_result.stdout + verify_result.stderr)

    def test_re_recording_a_control_verifies_instead_of_re_baselining(self) -> None:
        self.init_accepted()
        (self.repo / "allowed.txt").write_text("first\n", encoding="utf-8")
        result_1 = self.record()
        self.assertEqual(result_1.returncode, 0, result_1.stdout + result_1.stderr)
        (self.repo / "allowed.txt").write_text("mutated\n", encoding="utf-8")
        before_bytes = self.accepted.read_bytes()
        result_2 = self.record()
        self.assertNotEqual(result_2.returncode, 0)
        self.assertIn(
            "accepted state drifted under an already-recorded control: allowed.txt",
            result_2.stdout,
        )
        self.assertEqual(self.accepted.read_bytes(), before_bytes)
        verify_result = self.verify()
        self.assertNotEqual(verify_result.returncode, 0)

    def test_re_recording_a_clean_control_is_idempotent(self) -> None:
        self.init_accepted()
        (self.repo / "allowed.txt").write_text("first\n", encoding="utf-8")
        result_1 = self.record()
        self.assertEqual(result_1.returncode, 0, result_1.stdout + result_1.stderr)
        before_bytes = self.accepted.read_bytes()
        result_2 = self.record()
        self.assertEqual(result_2.returncode, 0, result_2.stdout + result_2.stderr)
        self.assertEqual(self.accepted.read_bytes(), before_bytes)
        verify_result = self.verify()
        self.assertEqual(verify_result.returncode, 0, verify_result.stdout + verify_result.stderr)


if __name__ == "__main__":
    unittest.main()
