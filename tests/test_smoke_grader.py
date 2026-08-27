from __future__ import annotations

import json
import os
import re
import tempfile
import unittest
from pathlib import Path


DISPATCH_LINE_RE = re.compile(
    r"^dispatch \d+ [a-z][a-z -]* start=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z "
    r"end=\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
)

# A line is a CANDIDATE D-005 metrics line when it opens with "dispatch " and a
# number. Selecting on the bare "dispatch " prefix also matches wrapped prose in
# journal.md -- a real journal wrapped the sentence "...every dispatch appends one
# timestamped `dispatch` line to the journal." onto a line starting with
# "dispatch appends", which was then graded as a malformed metrics line. The digit
# is what separates a metrics line from a sentence; strict validation of the
# candidates still happens against DISPATCH_LINE_RE, so a genuinely malformed
# metrics line is still caught rather than skipped.
DISPATCH_CANDIDATE_RE = re.compile(r"^dispatch \d+\b")

# A .result line is "<exit code>  <command>" -- two spaces between the fields.
RESULT_LINE_RE = re.compile(r"^\d+ {2}(?P<command>.+)$")

# Phase-gate acceptance logs are identified by this filename suffix. See the
# grade_full_suite_runs docstring for why the command text cannot be used.
ACCEPTANCE_LOG_SUFFIX = "-acceptance"


def grade_dispatch_count(workspace: Path, ceiling: int) -> tuple[bool, str]:
    """Maps onto a `claude plugin eval` `count` grader."""
    attempts_dir = workspace / "attempts"
    if not attempts_dir.is_dir():
        return False, f"no attempts/ directory under {workspace}"
    count = len(list(attempts_dir.glob("*.agent")))
    if count <= ceiling:
        return True, f"{count} attempts/*.agent files at or below ceiling {ceiling}"
    return False, f"{count} attempts/*.agent files exceeds ceiling {ceiling}"


def grade_full_suite_runs(workspace: Path, command: str, ceiling: int = 4) -> tuple[bool, str]:
    """Maps onto a `claude plugin eval` `count` grader.

    Counts full-suite runs from the two places the harness actually records one:

    * ``logs/<gate>-overall.result`` and ``logs/<gate>-overall-join.result``,
      which carry one ``"<exit code>  <command>"`` line per command run at the
      final gate. The command text is matched here.
    * ``logs/<phase>-acceptance.log``, which carries pytest OUTPUT only -- the
      harness never echoes the command into it -- so a phase gate is identified
      by the ``-acceptance`` filename suffix instead.

    Searching every ``logs/`` file for the command text, as this grader
    originally did, can therefore never see a phase gate at all.

    The result is graded against a ceiling rather than an exact count, and the
    count is always reported so it can be used as a benchmark metric. An exact
    count cannot be right for more than one task shape: a run of N phases spends
    N phase-gate runs plus one final-gate run, and a repaired phase re-runs its
    own gate, so the correct number varies per task and per run.

    A count of zero fails: a completed run always runs its suite at least once.

    Known limitation: the ``-acceptance`` suffix is a harness convention, not a
    contract. A harness that renames its acceptance logs will be under-counted
    here, and this grader will fail closed rather than silently pass.
    """
    logs_dir = workspace / "logs"
    if not logs_dir.is_dir():
        return False, f"no logs/ directory under {workspace}"
    gate_runs: list[str] = []
    for log_path in sorted(logs_dir.iterdir()):
        if not log_path.is_file():
            continue
        if log_path.suffix == ".result":
            try:
                text = log_path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            for line in text.splitlines():
                match = RESULT_LINE_RE.match(line)
                if match and match.group("command").strip() == command:
                    gate_runs.append(log_path.name)
        elif log_path.suffix == ".log" and log_path.stem.endswith(ACCEPTANCE_LOG_SUFFIX):
            gate_runs.append(log_path.name)
    count = len(gate_runs)
    detail = ", ".join(gate_runs) if gate_runs else "none"
    if count == 0:
        return False, f"'{command}' has no recorded full-suite run in {logs_dir}"
    if count <= ceiling:
        return True, f"{count} full-suite run(s) at or below ceiling {ceiling}: {detail}"
    return False, f"{count} full-suite run(s) exceeds ceiling {ceiling}: {detail}"


def grade_dispatch_timestamps(workspace: Path) -> tuple[bool, str]:
    """Maps onto a `claude plugin eval` `regex` grader."""
    journal_path = workspace / "journal.md"
    if not journal_path.is_file():
        return False, f"no journal.md under {workspace}"
    try:
        text = journal_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return False, f"journal.md is not readable UTF-8 text: {exc}"
    dispatch_lines = [
        line for line in text.splitlines() if DISPATCH_CANDIDATE_RE.match(line)
    ]
    if not dispatch_lines:
        return False, "journal.md has no dispatch lines"
    bad = [line for line in dispatch_lines if not DISPATCH_LINE_RE.fullmatch(line)]
    if bad:
        return False, f"{len(bad)} dispatch line(s) do not match the required form: {bad[0]!r}"
    return True, f"all {len(dispatch_lines)} dispatch lines match the required form"


def grade_cost_ceiling(cost_json: Path, ceiling_usd: float) -> tuple[bool, str]:
    """Maps onto a `claude plugin eval` `baseline` grader."""
    if not cost_json.is_file():
        return False, f"cost JSON not found: {cost_json}"
    try:
        text = cost_json.read_text(encoding="utf-8")
    except OSError as exc:
        return False, f"cost JSON unreadable: {exc}"
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return False, f"cost JSON at {cost_json} is not valid JSON: {exc}"
    if not isinstance(data, dict) or "total_usd" not in data:
        return False, f"cost JSON at {cost_json} is missing a total_usd key"
    total = data["total_usd"]
    if not isinstance(total, (int, float)) or isinstance(total, bool):
        return False, f"total_usd in {cost_json} is not a number: {total!r}"
    if total <= ceiling_usd:
        return True, f"total_usd {total} at or below ceiling {ceiling_usd}"
    return False, f"total_usd {total} exceeds ceiling {ceiling_usd}"


class SmokeGraderFixtureTests(unittest.TestCase):
    def test_dispatch_count_passes_on_good_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            attempts = workspace / "attempts"
            attempts.mkdir()
            for index in range(3):
                (attempts / f"executor-1.{index}-a1.agent").write_text("x", encoding="utf-8")
            passed, message = grade_dispatch_count(workspace, ceiling=5)
            self.assertTrue(passed, message)

    def test_dispatch_count_fails_on_bad_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            attempts = workspace / "attempts"
            attempts.mkdir()
            for index in range(6):
                (attempts / f"executor-1.{index}-a1.agent").write_text("x", encoding="utf-8")
            passed, message = grade_dispatch_count(workspace, ceiling=5)
            self.assertFalse(passed, message)

    def test_full_suite_runs_passes_on_good_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            logs = workspace / "logs"
            logs.mkdir()
            command = "python -m pytest tests -q"
            (logs / "phase-1-acceptance.log").write_text("128 passed\n", encoding="utf-8")
            (logs / "phase-1-overall.result").write_text(f"0  {command}\n", encoding="utf-8")
            passed, message = grade_full_suite_runs(workspace, command, ceiling=4)
            self.assertTrue(passed, message)

    def test_full_suite_runs_fails_on_bad_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            logs = workspace / "logs"
            logs.mkdir()
            command = "python -m pytest tests -q"
            # The command text sitting inside an ordinary .log file is NOT a
            # recorded gate run: the harness never writes it there.
            (logs / "phase-1.log").write_text(f"$ {command}\nPASS\n", encoding="utf-8")
            passed, message = grade_full_suite_runs(workspace, command, ceiling=4)
            self.assertFalse(passed, message)

    def test_dispatch_timestamps_passes_on_good_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            journal = workspace / "journal.md"
            journal.write_text(
                "dispatch 1 phase-planner start=2026-08-26T09:00:00Z end=2026-08-26T09:04:00Z\n"
                "dispatch 2 executor start=2026-08-26T09:05:00Z end=2026-08-26T09:12:00Z\n",
                encoding="utf-8",
            )
            passed, message = grade_dispatch_timestamps(workspace)
            self.assertTrue(passed, message)

    def test_dispatch_timestamps_fails_on_bad_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            journal = workspace / "journal.md"
            journal.write_text(
                "dispatch 1 phase-planner start=2026-08-26T09:00:00Z end=2026-08-26T09:04:00Z\n"
                "dispatch 2 executor start=2026-08-26T09:05:00Z\n",
                encoding="utf-8",
            )
            passed, message = grade_dispatch_timestamps(workspace)
            self.assertFalse(passed, message)

    def test_full_suite_runs_counts_result_files_and_acceptance_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            logs = workspace / "logs"
            logs.mkdir()
            command = "python -m pytest tests -q"
            # Phase-gate acceptance logs hold pytest OUTPUT only; the command text
            # never appears in them, so they are identified by name.
            (logs / "phase-1-acceptance.log").write_text("128 passed\n", encoding="utf-8")
            (logs / "phase-2-acceptance.log").write_text("128 passed\n", encoding="utf-8")
            # The final gate records its command in a .result file, one
            # "<exit>  <command>" line per command.
            (logs / "phase-2-overall.result").write_text(
                f"0  {command}\n", encoding="utf-8"
            )
            # A different command in a .result file must not be counted.
            (logs / "phase-2-overall-join.result").write_text(
                "0  python oplan/scripts/validate_run.py .oplan/demo\n", encoding="utf-8"
            )
            # A leaf validation log must not be counted.
            (logs / "2.1.log").write_text("2 passed\n", encoding="utf-8")
            passed, message = grade_full_suite_runs(workspace, command, ceiling=4)
            self.assertTrue(passed, message)
            self.assertIn("3", message)

    def test_full_suite_runs_fails_above_ceiling(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            logs = workspace / "logs"
            logs.mkdir()
            command = "python -m pytest tests -q"
            for phase in range(5):
                (logs / f"phase-{phase}-acceptance.log").write_text("ok\n", encoding="utf-8")
            passed, message = grade_full_suite_runs(workspace, command, ceiling=4)
            self.assertFalse(passed, message)

    def test_full_suite_runs_fails_when_suite_never_ran(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            logs = workspace / "logs"
            logs.mkdir()
            (logs / "1.1.log").write_text("2 passed\n", encoding="utf-8")
            passed, message = grade_full_suite_runs(
                workspace, "python -m pytest tests -q", ceiling=4
            )
            self.assertFalse(passed, message)

    def test_dispatch_timestamps_ignores_prose_beginning_with_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            journal = workspace / "journal.md"
            # The second line is wrapped prose from a real journal. It begins with
            # "dispatch " but is not a metrics line and must not be graded as one.
            journal.write_text(
                "dispatch 1 executor start=2026-08-26T09:00:00Z end=2026-08-26T09:04:00Z\n"
                "dispatch appends one timestamped `dispatch` line to the journal.\n",
                encoding="utf-8",
            )
            passed, message = grade_dispatch_timestamps(workspace)
            self.assertTrue(passed, message)

    def test_dispatch_timestamps_still_catches_malformed_real_line(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            journal = workspace / "journal.md"
            # Numbered, so it IS a metrics line, but its end= stamp is missing.
            journal.write_text(
                "dispatch 1 executor start=2026-08-26T09:00:00Z end=2026-08-26T09:04:00Z\n"
                "dispatch 2 executor start=2026-08-26T09:05:00Z\n",
                encoding="utf-8",
            )
            passed, message = grade_dispatch_timestamps(workspace)
            self.assertFalse(passed, message)

    def test_cost_ceiling_passes_on_good_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cost_json = Path(tmp) / "cost.json"
            cost_json.write_text(json.dumps({"total_usd": 4.5}), encoding="utf-8")
            passed, message = grade_cost_ceiling(cost_json, ceiling_usd=10.0)
            self.assertTrue(passed, message)

    def test_cost_ceiling_fails_on_bad_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cost_json = Path(tmp) / "cost.json"
            cost_json.write_text(json.dumps({"total_usd": 15.75}), encoding="utf-8")
            passed, message = grade_cost_ceiling(cost_json, ceiling_usd=10.0)
            self.assertFalse(passed, message)


class SmokeGraderLiveTests(unittest.TestCase):
    FULL_SUITE_COMMAND = "python -m pytest tests -q"
    DEFAULT_DISPATCH_CEILING = 40
    DEFAULT_COST_CEILING_USD = 40.0
    # A three-phase scenario spends three phase-gate runs plus one final-gate
    # run. Raise it for a longer task or a run whose phase was repaired.
    DEFAULT_SUITE_CEILING = 4

    def live_workspace(self) -> Path:
        raw = os.environ.get("OPLAN_SMOKE_WORKSPACE")
        if not raw:
            self.skipTest("OPLAN_SMOKE_WORKSPACE is not set; no live smoke workspace to grade")
        return Path(raw)

    def test_dispatch_count_within_ceiling(self) -> None:
        workspace = self.live_workspace()
        ceiling = int(
            os.environ.get("OPLAN_SMOKE_DISPATCH_CEILING", self.DEFAULT_DISPATCH_CEILING)
        )
        passed, message = grade_dispatch_count(workspace, ceiling)
        self.assertTrue(passed, message)

    def test_full_suite_runs_within_ceiling(self) -> None:
        workspace = self.live_workspace()
        ceiling = int(
            os.environ.get("OPLAN_SMOKE_SUITE_CEILING", self.DEFAULT_SUITE_CEILING)
        )
        passed, message = grade_full_suite_runs(workspace, self.FULL_SUITE_COMMAND, ceiling)
        self.assertTrue(passed, message)

    def test_dispatch_timestamps_are_well_formed(self) -> None:
        workspace = self.live_workspace()
        passed, message = grade_dispatch_timestamps(workspace)
        self.assertTrue(passed, message)

    def test_cost_within_ceiling(self) -> None:
        raw = os.environ.get("OPLAN_SMOKE_COST_JSON")
        if not raw:
            self.skipTest("OPLAN_SMOKE_COST_JSON is not set; no live cost report to grade")
        ceiling = float(
            os.environ.get("OPLAN_SMOKE_COST_CEILING_USD", self.DEFAULT_COST_CEILING_USD)
        )
        passed, message = grade_cost_ceiling(Path(raw), ceiling)
        self.assertTrue(passed, message)


if __name__ == "__main__":
    unittest.main()
