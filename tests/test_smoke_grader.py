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


def grade_dispatch_count(workspace: Path, ceiling: int) -> tuple[bool, str]:
    """Maps onto a `claude plugin eval` `count` grader."""
    attempts_dir = workspace / "attempts"
    if not attempts_dir.is_dir():
        return False, f"no attempts/ directory under {workspace}"
    count = len(list(attempts_dir.glob("*.agent")))
    if count <= ceiling:
        return True, f"{count} attempts/*.agent files at or below ceiling {ceiling}"
    return False, f"{count} attempts/*.agent files exceeds ceiling {ceiling}"


def grade_full_suite_runs(workspace: Path, command: str, expected: int = 2) -> tuple[bool, str]:
    """Maps onto a `claude plugin eval` `regex`/`count` grader."""
    logs_dir = workspace / "logs"
    if not logs_dir.is_dir():
        return False, f"no logs/ directory under {workspace}"
    count = 0
    for log_path in logs_dir.iterdir():
        if not log_path.is_file():
            continue
        try:
            text = log_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if command in text:
            count += 1
    if count == expected:
        return True, f"'{command}' appears in {count} logs/ files, matching expected {expected}"
    return False, f"'{command}' appears in {count} logs/ files, expected {expected}"


def grade_dispatch_timestamps(workspace: Path) -> tuple[bool, str]:
    """Maps onto a `claude plugin eval` `regex` grader."""
    journal_path = workspace / "journal.md"
    if not journal_path.is_file():
        return False, f"no journal.md under {workspace}"
    try:
        text = journal_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as exc:
        return False, f"journal.md is not readable UTF-8 text: {exc}"
    dispatch_lines = [line for line in text.splitlines() if line.startswith("dispatch ")]
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
            (logs / "phase-1.log").write_text(f"$ {command}\nPASS\n", encoding="utf-8")
            (logs / "phase-1-final.log").write_text(f"$ {command}\nPASS\n", encoding="utf-8")
            passed, message = grade_full_suite_runs(workspace, command, expected=2)
            self.assertTrue(passed, message)

    def test_full_suite_runs_fails_on_bad_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            logs = workspace / "logs"
            logs.mkdir()
            command = "python -m pytest tests -q"
            (logs / "phase-1.log").write_text(f"$ {command}\nPASS\n", encoding="utf-8")
            passed, message = grade_full_suite_runs(workspace, command, expected=2)
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

    def test_full_suite_ran_exactly_twice(self) -> None:
        workspace = self.live_workspace()
        passed, message = grade_full_suite_runs(workspace, self.FULL_SUITE_COMMAND)
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
