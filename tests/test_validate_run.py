from __future__ import annotations

import json
import hashlib
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO = Path(__file__).resolve().parents[1]
VALIDATOR = REPO / "oplan/scripts/validate_run.py"
GUARD = REPO / "oplan/scripts/worktree_guard.py"


class ValidateRunTests(unittest.TestCase):
    def make_workspace(self, decision: str = "D-001") -> Path:
        self.tempdir = tempfile.TemporaryDirectory()
        repo = Path(self.tempdir.name)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "oplan test"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "oplan@example.invalid"], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "commit", "--allow-empty", "-q", "-m", "baseline"], check=True
        )
        sha = subprocess.run(
            ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True, capture_output=True, check=True
        ).stdout.strip()
        root = repo / ".oplan/test"
        for directory in ("control", "packets", "seals", "blockers", "research", "attempts", "logs", "reviews", "field-guide"):
            (root / directory).mkdir(parents=True)
        for filename in ("plan.md", "journal.md", "STATUS.md", "briefing.md"):
            (root / filename).write_text("\n", encoding="utf-8")
        request = "Build output.\n"
        (root / "request.md").write_text(request, encoding="utf-8")
        (root / "intake.md").write_text(
            "status: complete\ngrill_tool: none\n", encoding="utf-8"
        )
        request_hash = hashlib.sha256((root / "request.md").read_bytes()).hexdigest()
        (root / "baseline.md").write_text(
            f"commit: {sha}\nrequest_sha256: {request_hash}\nprotected_paths: []\n"
            "run_modes: autonomous\ncommit_mode: auto\n"
            "depth_profile: standard\nwork_mode: engineering\nautonomy: interactive\n",
            encoding="utf-8",
        )
        (root / "model-bindings.md").write_text(
            "\n".join(
                [
                    "main_harness: coordinator",
                    "phase_planner: strong",
                    "plan_reviewer: strong",
                    "executor: cheap",
                    "spec_auditor: cheap",
                    "system_reviewer: strong",
                    "phase_curator: strong",
                    "research_agent: cheap",
                    "evidence_reviewer: cheap",
                    "worker_ladder: cheap, strong",
                    "research_ladder: cheap, strong",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "field-guide/index.md").write_text("# Guide\n", encoding="utf-8")
        (root / "design.md").write_text(
            "# Design\n\n### D-001 — output\nStatus: approved\nDecision: write text\n",
            encoding="utf-8",
        )
        (root / "phase-state.md").write_text(
            "\n".join(
                [
                    "RUN: test",
                    "STATE: REVIEWING_PLAN",
                    'PHASE: 1 "build"',
                    "PHASE_CONTROL: control/phase-1.json",
                    "LEAF: none",
                    "NEXT_ACTION: SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                    "ACTIVE_AGENT: none",
                    f"LAST_ACCEPTED: {sha}",
                    "ACCEPTED_THIS_PHASE: none",
                    "DECISIONS_IN_FORCE: D-001",
                    "OPEN_BLOCKER: none",
                    "RETRY: 0",
                    "TERMINAL_REASON: none",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        validation = "test -f output.txt"
        (root / "packets/1.1.md").write_text(
            "\n".join(
                [
                    "# Executor packet",
                    "**Goal:** write output",
                    "**Files you may create or modify — exhaustive:** output.txt",
                    "**Commands:** none",
                    f"**Frozen validation:** {validation}",
                    f"**Dependent decisions:** {decision}",
                    "**Contracts:** text",
                    "**Non-goals:** none",
                    "**Risk:** low — local file",
                    "## Budgets",
                    "STATUS: done | failed | stopped-with-question",
                    "FAILURE_CAUSE: <=3 lines when failed, otherwise none",
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "control/1.1.json").write_text(
            json.dumps(
                {
                    "step": "1.1",
                    "phase": 1,
                    "packet": "packets/1.1.md",
                    "write_set": ["output.txt"],
                    "validation": validation,
                    "risk": "low",
                    "decisions": [decision],
                    "wall_time_minutes": 15,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "control/phase-1.json").write_text(
            json.dumps(
                {
                    "phase": 1,
                    "revision": 1,
                    "name": "build",
                    "queue": ["control/1.1.json"],
                    "acceptance": ["test -f output.txt"],
                    "overall_acceptance": ["test -f output.txt"],
                    "next_phase": None,
                    "plan_review": "reviews/phase-1-plan-r1.md",
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        (root / "reviews/phase-1-plan-r1.md").write_text("VERDICT: ship\n", encoding="utf-8")
        return root

    def run_validator(self, workspace: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATOR), str(workspace), "--phase", "1", *extra],
            text=True,
            capture_output=True,
            check=False,
        )

    def tearDown(self) -> None:
        if hasattr(self, "tempdir"):
            self.tempdir.cleanup()

    def test_valid_workspace_passes(self) -> None:
        result = self.run_validator(self.make_workspace())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("oplan run validation: PASS", result.stdout)

    def test_undefined_decision_fails(self) -> None:
        result = self.run_validator(self.make_workspace("D-999"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("references undefined decision D-999", result.stdout)

    def test_illegal_action_for_state_fails(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json", "SPAWN_EXECUTOR control=control/1.1.json"
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is illegal for STATE", result.stdout)

    def test_symbolic_last_accepted_fails(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            re_sub(r"^LAST_ACCEPTED: .+$", "LAST_ACCEPTED: HEAD", state.read_text(encoding="utf-8")),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be a full commit SHA", result.stdout)

    def test_action_requires_artifact_arguments(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                "SPAWN_PLAN_REVIEWER source=control/phase-1.json",
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing_args=['phase']", result.stdout)

    def test_action_rejects_duplicate_arguments(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                "SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json phase=1",
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate_args=['phase']", result.stdout)

    def test_seal_detects_packet_mutation(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                "SEAL_PHASE phase=1 source=control/phase-1.json",
            ),
            encoding="utf-8",
        )
        sealed = self.run_validator(workspace, "--seal")
        self.assertEqual(sealed.returncode, 0, sealed.stdout + sealed.stderr)
        packet = workspace / "packets/1.1.md"
        packet.write_text(packet.read_text(encoding="utf-8") + "mutated\n", encoding="utf-8")
        result = self.run_validator(workspace, "--require-sealed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("seal mismatch", result.stdout)

    def test_seal_promotes_referenced_decision(self) -> None:
        workspace = self.make_workspace()
        design = workspace / "design.md"
        design.write_text(
            design.read_text(encoding="utf-8").replace("Status: approved", "Status: proposed"),
            encoding="utf-8",
        )
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8")
            .replace(
                "SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                "SEAL_PHASE phase=1 source=control/phase-1.json",
            )
            .replace("DECISIONS_IN_FORCE: D-001", "DECISIONS_IN_FORCE: none"),
            encoding="utf-8",
        )
        result = self.run_validator(workspace, "--seal")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Status: approved", design.read_text(encoding="utf-8"))
        self.assertIn("DECISIONS_IN_FORCE: D-001", state.read_text(encoding="utf-8"))
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "DECISIONS_IN_FORCE: D-001", "DECISIONS_IN_FORCE: none"
            ),
            encoding="utf-8",
        )
        rerun = self.run_validator(workspace, "--seal")
        self.assertEqual(rerun.returncode, 0, rerun.stdout + rerun.stderr)
        self.assertIn("DECISIONS_IN_FORCE: D-001", state.read_text(encoding="utf-8"))

    def test_seal_detects_phase_control_mutation(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                "SEAL_PHASE phase=1 source=control/phase-1.json",
            ),
            encoding="utf-8",
        )
        sealed = self.run_validator(workspace, "--seal")
        self.assertEqual(sealed.returncode, 0, sealed.stdout + sealed.stderr)
        phase_control = workspace / "control/phase-1.json"
        data = json.loads(phase_control.read_text(encoding="utf-8"))
        data["acceptance"] = ["true"]
        phase_control.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        result = self.run_validator(workspace, "--require-sealed")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("phase-control/review seal mismatch", result.stdout)

    def test_decision_in_force_must_be_defined(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "DECISIONS_IN_FORCE: D-001", "DECISIONS_IN_FORCE: D-999"
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DECISIONS_IN_FORCE references undefined D-999", result.stdout)

    def test_duplicate_decision_id_fails(self) -> None:
        workspace = self.make_workspace()
        design = workspace / "design.md"
        design.write_text(
            design.read_text(encoding="utf-8")
            + "\n### D-001 — duplicate\nStatus: approved\nDecision: conflict\n",
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate decision IDs ['D-001']", result.stdout)

    def test_protected_baseline_path_cannot_be_written(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace(
                "protected_paths: []", 'protected_paths: ["output.txt"]'
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("overlaps protected baseline path output.txt", result.stdout)

    def test_packet_path_must_match_step(self) -> None:
        workspace = self.make_workspace()
        control_path = workspace / "control/1.1.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["packet"] = "packets/other.md"
        control_path.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")
        (workspace / "packets/other.md").write_text(
            (workspace / "packets/1.1.md").read_text(encoding="utf-8"), encoding="utf-8"
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("packet must equal packets/1.1.md", result.stdout)

    def test_write_set_cannot_touch_git_or_workspace(self) -> None:
        workspace = self.make_workspace()
        control_path = workspace / "control/1.1.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["write_set"] = [".git/config", ".oplan/test/design.md"]
        control_path.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")
        packet = workspace / "packets/1.1.md"
        packet.write_text(
            packet.read_text(encoding="utf-8").replace(
                "**Files you may create or modify — exhaustive:** output.txt",
                "**Files you may create or modify — exhaustive:** .git/config .oplan/test/design.md",
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("write_set overlaps Git metadata or oplan workspace", result.stdout)

    def test_invalid_step_reports_instead_of_crashing(self) -> None:
        workspace = self.make_workspace()
        control_path = workspace / "control/1.1.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["step"] = None
        control_path.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid step ID", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_wall_time_must_be_positive_integer(self) -> None:
        workspace = self.make_workspace()
        control_path = workspace / "control/1.1.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["wall_time_minutes"] = 0
        control_path.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("wall_time_minutes must be a positive integer", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_measurement_kind_is_accepted(self) -> None:
        workspace = self.make_workspace()
        control_path = workspace / "control/1.1.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["kind"] = "measurement"
        control_path.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")
        result = self.run_validator(workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("oplan run validation: PASS", result.stdout)

    def test_kind_rejects_unknown_value(self) -> None:
        workspace = self.make_workspace()
        control_path = workspace / "control/1.1.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        control["kind"] = "bogus"
        control_path.write_text(json.dumps(control, indent=2) + "\n", encoding="utf-8")
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("kind must be measurement or engineering", result.stdout)

    def test_absent_kind_still_validates(self) -> None:
        workspace = self.make_workspace()
        control_path = workspace / "control/1.1.json"
        control = json.loads(control_path.read_text(encoding="utf-8"))
        self.assertNotIn("kind", control)
        result = self.run_validator(workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("oplan run validation: PASS", result.stdout)

    def test_non_utf8_packet_reports_instead_of_crashing(self) -> None:
        workspace = self.make_workspace()
        (workspace / "packets/1.1.md").write_bytes(b"\xff\xfe")
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("artifact must be UTF-8 text", result.stdout)
        self.assertEqual(result.stderr, "")

    def test_commit_mode_must_be_auto_or_none(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("commit_mode: auto", "commit_mode: bogus"),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commit_mode must be auto or none", result.stdout)

    def test_protected_baseline_overlap_allowed_under_commit_mode_none(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8")
            .replace("protected_paths: []", 'protected_paths: ["output.txt"]')
            .replace("commit_mode: auto", "commit_mode: none"),
            encoding="utf-8",
        )
        init_result = subprocess.run(
            [sys.executable, str(GUARD), "init-accepted", str(workspace.parents[1]), str(workspace / "attempts/accepted-state.json")],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(init_result.returncode, 0, init_result.stdout + init_result.stderr)
        result = self.run_validator(workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_run_modes_is_required(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("run_modes: autonomous\n", ""),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline.md: missing run_modes", result.stdout)

    def test_run_modes_rejects_unknown_value(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("run_modes: autonomous", "run_modes: bogus"),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("run_modes must be autonomous, pause-between-phases, or step-by-step", result.stdout)

    def test_commit_mode_is_required(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("commit_mode: auto\n", ""),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline.md: missing commit_mode", result.stdout)

    def test_commit_mode_must_appear_once(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8") + "commit_mode: auto\n",
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("commit_mode must appear exactly once", result.stdout)

    def test_depth_profile_is_required(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("depth_profile: standard\n", ""),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline.md: missing depth_profile", result.stdout)

    def test_depth_profile_rejects_unknown_value(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("depth_profile: standard", "depth_profile: bogus"),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("depth_profile must be fast, standard, or paranoid", result.stdout)

    def test_depth_profile_must_appear_once(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8") + "depth_profile: standard\n",
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("depth_profile must appear exactly once", result.stdout)

    def test_work_mode_is_required(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("work_mode: engineering\n", ""),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline.md: missing work_mode", result.stdout)

    def test_work_mode_rejects_unknown_value(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("work_mode: engineering", "work_mode: bogus"),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("work_mode must be engineering or experiment", result.stdout)

    def test_work_mode_must_appear_once(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8") + "work_mode: engineering\n",
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("work_mode must appear exactly once", result.stdout)

    def test_autonomy_is_required(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("autonomy: interactive\n", ""),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("baseline.md: missing autonomy", result.stdout)

    def test_autonomy_rejects_unknown_value(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("autonomy: interactive", "autonomy: bogus"),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("autonomy must be interactive or full", result.stdout)

    def test_autonomy_must_appear_once(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8") + "autonomy: interactive\n",
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("autonomy must appear exactly once", result.stdout)

    def test_intake_is_required(self) -> None:
        workspace = self.make_workspace()
        (workspace / "intake.md").unlink()
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing workspace artifact: intake.md", result.stdout)

    def test_intake_status_is_required(self) -> None:
        workspace = self.make_workspace()
        intake = workspace / "intake.md"
        intake.write_text("grill_tool: none\n", encoding="utf-8")
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("intake.md: missing status", result.stdout)

    def test_intake_status_rejects_unknown_value(self) -> None:
        workspace = self.make_workspace()
        intake = workspace / "intake.md"
        intake.write_text(
            intake.read_text(encoding="utf-8").replace("status: complete", "status: bogus"),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status must be complete or skipped-user-unreachable", result.stdout)

    def test_intake_status_must_appear_once(self) -> None:
        workspace = self.make_workspace()
        intake = workspace / "intake.md"
        intake.write_text(
            intake.read_text(encoding="utf-8") + "status: complete\n",
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("intake.md: status must appear exactly once", result.stdout)

    def test_run_final_gate_is_legal_in_closing_phase(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8")
            .replace("STATE: REVIEWING_PLAN", "STATE: CLOSING_PHASE")
            .replace(
                "NEXT_ACTION: SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                "NEXT_ACTION: RUN_FINAL_GATE phase=1 source=reviews/phase-1-system.md",
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("oplan run validation: PASS", result.stdout)

    def test_run_final_gate_requires_source(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8")
            .replace("STATE: REVIEWING_PLAN", "STATE: CLOSING_PHASE")
            .replace(
                "NEXT_ACTION: SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                "NEXT_ACTION: RUN_FINAL_GATE phase=1",
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing_args=['source']", result.stdout)

    def test_run_final_gate_is_illegal_outside_closing_phase(self) -> None:
        workspace = self.make_workspace()
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "NEXT_ACTION: SPAWN_PLAN_REVIEWER phase=1 source=control/phase-1.json",
                "NEXT_ACTION: RUN_FINAL_GATE phase=1 source=reviews/phase-1-system.md",
            ),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("is illegal for STATE", result.stdout)

    def test_missing_required_file_reports_instead_of_crashing(self) -> None:
        workspace = self.make_workspace()
        (workspace / "baseline.md").unlink()
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing workspace artifact: baseline.md", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_commit_mode_none_requires_accepted_state_manifest(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("commit_mode: auto", "commit_mode: none"),
            encoding="utf-8",
        )
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing attempts/accepted-state.json", result.stdout)

    def test_commit_mode_none_requires_current_step_in_manifest(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("commit_mode: auto", "commit_mode: none"),
            encoding="utf-8",
        )
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "ACCEPTED_THIS_PHASE: none", "ACCEPTED_THIS_PHASE: 1.1"
            ),
            encoding="utf-8",
        )
        init_result = subprocess.run(
            [sys.executable, str(GUARD), "init-accepted", str(workspace.parents[1]), str(workspace / "attempts/accepted-state.json")],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(init_result.returncode, 0, init_result.stdout + init_result.stderr)
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing current accepted steps ['1.1']", result.stdout)

    def test_commit_mode_none_rejects_non_object_manifest_without_traceback(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("commit_mode: auto", "commit_mode: none"),
            encoding="utf-8",
        )
        (workspace / "attempts/accepted-state.json").write_text("[]\n", encoding="utf-8")
        result = self.run_validator(workspace)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("accepted-state.json", result.stdout)
        self.assertNotIn("Traceback", result.stdout + result.stderr)

    def test_commit_mode_none_accepts_a_recorded_step(self) -> None:
        workspace = self.make_workspace()
        baseline = workspace / "baseline.md"
        baseline.write_text(
            baseline.read_text(encoding="utf-8").replace("commit_mode: auto", "commit_mode: none"),
            encoding="utf-8",
        )
        state = workspace / "phase-state.md"
        state.write_text(
            state.read_text(encoding="utf-8").replace(
                "ACCEPTED_THIS_PHASE: none", "ACCEPTED_THIS_PHASE: 1.1"
            ),
            encoding="utf-8",
        )
        (workspace.parents[1] / "output.txt").write_text("payload\n", encoding="utf-8")
        accepted_manifest = workspace / "attempts/accepted-state.json"
        init_result = subprocess.run(
            [sys.executable, str(GUARD), "init-accepted", str(workspace.parents[1]), str(accepted_manifest)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(init_result.returncode, 0, init_result.stdout + init_result.stderr)
        record_result = subprocess.run(
            [
                sys.executable,
                str(GUARD),
                "record-accepted",
                str(workspace.parents[1]),
                str(workspace / "control/1.1.json"),
                str(accepted_manifest),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(record_result.returncode, 0, record_result.stdout + record_result.stderr)
        manifest = json.loads(accepted_manifest.read_text(encoding="utf-8"))
        self.assertEqual(manifest["controls"][0]["path"], ".oplan/test/control/1.1.json")
        self.assertEqual(Path(manifest["controls"][0]["path"]).stem, "1.1")
        result = self.run_validator(workspace)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("oplan run validation: PASS", result.stdout)
        self.assertNotIn("missing current accepted steps", result.stdout)


def re_sub(pattern: str, replacement: str, text: str) -> str:
    import re

    return re.sub(pattern, replacement, text, flags=re.MULTILINE)


if __name__ == "__main__":
    unittest.main()
