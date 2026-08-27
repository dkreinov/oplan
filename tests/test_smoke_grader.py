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

# A .result line is "<exit code>  <command>" -- two spaces between the fields.
RESULT_LINE_RE = re.compile(r"^\d+ {2}(?P<command>.+)$")

# A populated `start=` field: the "=" must be followed by a real value, not by
# whitespace and not by the "<" that opens a format placeholder.
START_FIELD_RE = re.compile(r"start=[^\s<]")

# A gate log's STEM carries an acceptance or overall marker. No contract pins a
# phase-acceptance log path, so this pattern is empirical: it is the union of
# what the four real run workspaces under .oplan/ actually name their gate logs
# -- "phase-1-acceptance", "phase-1-acceptance2-pytest", "acc-pytest",
# "acc2-pytest", "overall-pytest", "phase-1-r2-overall". Leaf validation logs
# ("1.1", "1.4") carry no such marker.
GATE_LOG_STEM_RE = re.compile(r"(?:^|-)(?:acc(?:eptance)?|overall)\d*(?:-|$)")

# Evidence inside a log that a test suite actually ran and reported a result.
# A gate log must match this as well as GATE_LOG_STEM_RE, which is what keeps
# "phase-1-r2-overall-join.log" (the validate_run.py leg) and
# "acc-contracts.log" (the contract-validator leg) from being counted as suite
# runs even though their names carry a gate marker.
SUITE_OUTPUT_RE = re.compile(r"\b\d+ (?:passed|failed|error|errors)\b|\bno tests ran\b")


def _is_dispatch_candidate(line: str) -> bool:
    """Is this line CLAIMING to be a D-005 metrics line?

    Selecting candidates on the bare ``"dispatch "`` prefix matches wrapped prose:
    a real journal wrapped "...every dispatch appends one timestamped `dispatch`
    line to the journal." onto a line beginning "dispatch appends", which was then
    graded as a malformed metrics line.

    Requiring a digit instead is worse, not better -- it lets a line that DROPPED
    its counter escape validation entirely, turning a loud failure into silence,
    and the counter is half of what D-005 requires. So a line qualifies on either
    signal: a leading number, or the presence of a ``start=`` field. Prose has
    neither; every malformed metrics line has at least one, and is then judged
    strictly against DISPATCH_LINE_RE.
    """
    prefix = "dispatch "
    if not line.startswith(prefix):
        return False
    if line[len(prefix):][:1].isdigit():
        return True
    # `start=` must be followed by an actual value, not by whitespace or the
    # `<` of a placeholder. Accepting a bare "start=" re-admits the very bug
    # this function exists to fix: journal prose quoting the D-005 format
    # (``dispatch <n> <role> start= end=``) would be graded as a malformed
    # metrics line. .oplan/speed-run/journal.md contains both that quotation
    # and a wrapped "dispatch appends..." line.
    return bool(START_FIELD_RE.search(line))


def grade_dispatch_count(workspace: Path, ceiling: int) -> tuple[bool, str]:
    """Maps onto a `claude plugin eval` `count` grader."""
    attempts_dir = workspace / "attempts"
    if not attempts_dir.is_dir():
        return False, f"no attempts/ directory under {workspace}"
    count = len(list(attempts_dir.glob("*.agent")))
    if count <= ceiling:
        return True, f"{count} attempts/*.agent files at or below ceiling {ceiling}"
    return False, f"{count} attempts/*.agent files exceeds ceiling {ceiling}"


def grade_full_suite_runs(
    workspace: Path, command: str, floor: int = 2, ceiling: int = 4
) -> tuple[bool, str]:
    """DISABLED -- NOT FIT FOR USE. Do not score a benchmark run with this.

    Two independent reviews found this function reporting confidently wrong
    counts, in both directions. The demonstrated defects, all still present:

    * **Over-counts.** A harness that writes both ``<gate>-overall.result`` and
      ``<gate>-overall-pytest.log`` -- a merge of two conventions already present
      in the four real workspaces -- counts each gate twice. Two real gates are
      reported as four, and it passes.
    * **Over-counts.** A leg running a SUBSET of the suite
      (``2 passed, 77 deselected in 4.07s``) is counted identically to an
      18-minute full-suite run, because the content check never verifies WHICH
      command produced the output.
    * **Under-counts, silently.** A gate log truncated by a wall-time kill, or
      carrying one non-UTF-8 byte, is skipped with no signal.
    * **The floor cannot be set correctly.** Its documented formula -- one per
      phase-control revision plus one final gate -- gives 8 for
      ``.oplan/depth-profiles``, where this function counts 3.
    * **The ``.result`` branch is dead** against three of the four real
      workspaces, whose gates run ``python -m pytest tests/ -q -p
      no:cacheprovider`` rather than the hardcoded command. Every real count
      today comes from the filename heuristic alone.

    The root cause is that this function reverse-engineers run structure from
    filenames while the workspace already records it: ``control/phase-*.json``
    holds each gate's own ``acceptance``/``overall_acceptance`` command list and
    the revision history. The replacement should derive the expected count from
    those records rather than guess, and a benchmark harness under our own
    control should simply emit a machine-readable gate record. Both are a
    redesign, deliberately not attempted as a third patch.

    ``test_full_suite_runs_within_range`` is skipped for this reason, and the
    ``test_KNOWN_DEFECT_`` tests below pin the wrong behaviour so it stays
    visible instead of being mistaken for correct.

    What follows describes what it currently does, not what it should do.

    Counts the distinct gate runs of the full suite, deduplicated by log stem so
    a gate that wrote both ``<stem>.log`` and ``<stem>.result`` counts once.

    A gate run is recognised two ways:

    * a ``.result`` file line ``"<exit code>  <command>"`` whose command matches.
      This is the only shape any contract pins, and only for the final gate.
    * a ``.log`` file whose STEM carries an acceptance/overall marker AND whose
      CONTENT reports a suite result. Both are required. The name alone counts
      the validate_run.py and contract-validator legs of a gate, which are not
      suite runs; the content alone counts leaf validation logs, which are also
      not suite runs.

    Searching every ``logs/`` file for the command text, as this grader
    originally did, can never see a phase gate at all: phase-acceptance logs hold
    output only.

    **Why there is a floor.** No contract pins a phase-acceptance log path, and
    the four real workspaces under ``.oplan/`` use four different naming schemes.
    Name-based detection therefore cannot be trusted to find every gate, and a
    ceiling ALONE forgives that silently -- a missed gate is always "at or below"
    the ceiling, so one recognised run would excuse any number of missed ones and
    the grader would report a confidently wrong benchmark metric. The floor is
    what makes under-detection loud. Pass the number of gate runs the run is
    known to have spent: N phase-control revisions that reached acceptance, plus
    one final gate.

    A nonzero exit code still counts. A failed gate run consumed the same
    wall-clock and dollars, and filtering on success would bias the benchmark
    toward whichever harness version fails more.

    The count is graded against a range rather than an exact number: a run of N
    phases spends N phase-gate runs plus one final-gate run, and a repaired phase
    re-runs its own gate, so no single number is right for more than one task.
    """
    logs_dir = workspace / "logs"
    if not logs_dir.is_dir():
        return False, f"no logs/ directory under {workspace}"
    gate_stems: dict[str, str] = {}
    for log_path in sorted(logs_dir.iterdir()):
        if not log_path.is_file():
            continue
        try:
            text = log_path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if log_path.suffix == ".result":
            for line in text.splitlines():
                match = RESULT_LINE_RE.match(line)
                if match and match.group("command").strip() == command:
                    gate_stems.setdefault(log_path.stem, log_path.name)
        elif log_path.suffix == ".log":
            if GATE_LOG_STEM_RE.search(log_path.stem) and SUITE_OUTPUT_RE.search(text):
                gate_stems.setdefault(log_path.stem, log_path.name)
    count = len(gate_stems)
    detail = ", ".join(sorted(gate_stems.values())) if gate_stems else "none"
    if count < floor:
        return False, (
            f"{count} full-suite run(s) is below the floor of {floor} -- either the run "
            f"skipped a gate or this grader failed to recognise one in {logs_dir}: {detail}"
        )
    if count <= ceiling:
        return True, f"{count} full-suite run(s) within floor {floor} and ceiling {ceiling}: {detail}"
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
    dispatch_lines = [line for line in text.splitlines() if _is_dispatch_candidate(line)]
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

    # The four real run workspaces under .oplan/ name their gate logs four
    # different ways, because no contract pins a phase-acceptance log path.
    # Each fixture below replicates one of them verbatim.

    def _write(self, logs: Path, name: str, text: str) -> None:
        (logs / name).write_text(text, encoding="utf-8")

    PYTEST_TAIL = "128 passed, 9 skipped in 265.69s (0:04:25)\n"
    CONTRACTS_TAIL = "oplan contract validation: PASS (490 SKILL.md lines, 15 resources)\n"
    VALIDATE_TAIL = "oplan run validation: PASS (6 controls, 8 decisions)\n"
    COMMAND = "python -m pytest tests -q"

    def test_full_suite_runs_counts_speed_run_convention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            self._write(logs, "phase-1-acceptance.log", self.PYTEST_TAIL)
            self._write(logs, "phase-1-r2-acceptance.log", self.PYTEST_TAIL)
            self._write(logs, "phase-1-r2-overall.log", self.PYTEST_TAIL)
            self._write(logs, "phase-1-r2-overall.result", f"0  {self.COMMAND}\n")
            # The join leg runs validate_run.py, not the suite. Not a suite run.
            self._write(logs, "phase-1-r2-overall-join.log", self.VALIDATE_TAIL)
            self._write(
                logs,
                "phase-1-r2-overall-join.result",
                "0  python oplan/scripts/validate_run.py .oplan/speed-run\n",
            )
            # Leaf validation logs, including one whose output is a pytest tail.
            self._write(logs, "1.1.log", self.CONTRACTS_TAIL)
            self._write(logs, "1.4.log", "2 passed, 77 deselected in 4.07s\n")
            passed, message = grade_full_suite_runs(
                Path(tmp), self.COMMAND, floor=3, ceiling=4
            )
            self.assertTrue(passed, message)
            self.assertIn("3 full-suite run(s)", message)

    def test_full_suite_runs_counts_codex_salvage_convention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            self._write(logs, "phase-1-acceptance-pytest.log", self.PYTEST_TAIL)
            self._write(logs, "phase-1-acceptance2-pytest.log", self.PYTEST_TAIL)
            self._write(logs, "phase-1-acceptance-contracts.log", self.CONTRACTS_TAIL)
            self._write(logs, "phase-1-acceptance2-contracts.log", self.CONTRACTS_TAIL)
            self._write(logs, "overall-pytest.log", self.PYTEST_TAIL)
            self._write(logs, "overall-contracts.log", self.CONTRACTS_TAIL)
            self._write(logs, "overall-validate-run.log", self.VALIDATE_TAIL)
            passed, message = grade_full_suite_runs(
                Path(tmp), self.COMMAND, floor=3, ceiling=4
            )
            self.assertTrue(passed, message)
            self.assertIn("3 full-suite run(s)", message)

    def test_full_suite_runs_counts_acc_prefix_convention(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            self._write(logs, "acc-pytest.log", self.PYTEST_TAIL)
            self._write(logs, "acc2-pytest.log", self.PYTEST_TAIL)
            self._write(logs, "overall-pytest.log", self.PYTEST_TAIL)
            self._write(logs, "acc-contracts.log", self.CONTRACTS_TAIL)
            self._write(logs, "acc2-contracts.log", self.CONTRACTS_TAIL)
            self._write(logs, "overall-contracts.log", self.CONTRACTS_TAIL)
            self._write(logs, "acc-sibling.log", self.VALIDATE_TAIL)
            passed, message = grade_full_suite_runs(
                Path(tmp), self.COMMAND, floor=3, ceiling=4
            )
            self.assertTrue(passed, message)
            self.assertIn("3 full-suite run(s)", message)

    def test_full_suite_runs_fails_loudly_when_it_finds_fewer_than_the_floor(self) -> None:
        """The defect this replaced: under-counting was silently forgiven.

        A ceiling alone cannot catch a missed gate log -- fewer is always 'at or
        below'. One recognised run must not excuse three unrecognised ones.
        """
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            # Three real gate runs under a naming scheme the grader cannot see,
            # plus one it can.
            self._write(logs, "gate-alpha.log", self.PYTEST_TAIL)
            self._write(logs, "gate-beta.log", self.PYTEST_TAIL)
            self._write(logs, "gate-gamma.log", self.PYTEST_TAIL)
            self._write(logs, "phase-3-overall.result", f"0  {self.COMMAND}\n")
            passed, message = grade_full_suite_runs(
                Path(tmp), self.COMMAND, floor=4, ceiling=4
            )
            self.assertFalse(passed, message)
            self.assertIn("below the floor", message)

    def test_full_suite_runs_counts_a_failed_suite_run(self) -> None:
        """A failed gate run cost the same wall-clock and dollars. Count it."""
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            self._write(logs, "phase-1-acceptance.log", "3 failed, 125 passed in 260s\n")
            self._write(logs, "phase-1-overall.result", f"1  {self.COMMAND}\n")
            passed, message = grade_full_suite_runs(
                Path(tmp), self.COMMAND, floor=2, ceiling=4
            )
            self.assertTrue(passed, message)
            self.assertIn("2 full-suite run(s)", message)

    def test_KNOWN_DEFECT_full_suite_runs_double_counts_split_gate_legs(self) -> None:
        """Pinned wrong behaviour. Two real gates are reported as four.

        Do not "fix" this test by changing the expectation -- fix the function,
        which is disabled. See the grade_full_suite_runs docstring.
        """
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            self._write(logs, "phase-1-acceptance.log", self.PYTEST_TAIL)
            # One gate, recorded as a .result plus a separately-named leg log.
            self._write(logs, "phase-1-overall.result", f"0  {self.COMMAND}\n")
            self._write(logs, "phase-1-overall-pytest.log", self.PYTEST_TAIL)
            passed, message = grade_full_suite_runs(
                Path(tmp), self.COMMAND, floor=2, ceiling=4
            )
            self.assertTrue(passed, message)
            self.assertIn("3 full-suite run(s)", message)  # truth is 2

    def test_KNOWN_DEFECT_full_suite_runs_counts_a_subset_run_as_a_full_one(self) -> None:
        """Pinned wrong behaviour. A 4-second targeted run counts as a full suite."""
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            self._write(logs, "phase-1-acceptance.log", self.PYTEST_TAIL)
            self._write(
                logs, "phase-1-acceptance-unit.log", "2 passed, 77 deselected in 4.07s\n"
            )
            passed, message = grade_full_suite_runs(
                Path(tmp), self.COMMAND, floor=2, ceiling=4
            )
            self.assertTrue(passed, message)
            self.assertIn("2 full-suite run(s)", message)  # truth is 1

    def test_KNOWN_DEFECT_full_suite_runs_silently_skips_an_unreadable_log(self) -> None:
        """Pinned wrong behaviour. A non-UTF-8 gate log vanishes with no signal."""
        with tempfile.TemporaryDirectory() as tmp:
            logs = Path(tmp) / "logs"
            logs.mkdir()
            self._write(logs, "phase-1-acceptance.log", self.PYTEST_TAIL)
            self._write(logs, "phase-2-acceptance.log", self.PYTEST_TAIL)
            # cp1252 byte, plausible on this Windows host.
            (logs / "phase-3-acceptance.log").write_bytes(
                b"128 passed, 9 skipped \x93truncated\x94\n"
            )
            passed, message = grade_full_suite_runs(
                Path(tmp), self.COMMAND, floor=2, ceiling=4
            )
            self.assertTrue(passed, message)
            self.assertIn("2 full-suite run(s)", message)  # truth is 3

    def test_dispatch_candidate_ignores_a_quoted_format_placeholder(self) -> None:
        """Journal prose quoting the D-005 format must not be graded.

        `.oplan/speed-run/journal.md` contains this exact shape.
        """
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "journal.md").write_text(
                "dispatch 1 executor start=2026-08-26T09:00:00Z end=2026-08-26T09:04:00Z\n"
                "dispatch <n> <role> start= end= is the required form.\n",
                encoding="utf-8",
            )
            passed, message = grade_dispatch_timestamps(workspace)
            self.assertTrue(passed, message)

    def test_dispatch_timestamps_catches_line_missing_its_counter(self) -> None:
        """D-005 requires a monotonic counter AND both stamps.

        A line that drops the counter must not escape validation by failing the
        candidate filter -- that would turn a loud failure into silence.
        """
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "journal.md").write_text(
                "dispatch 1 executor start=2026-08-26T09:00:00Z end=2026-08-26T09:04:00Z\n"
                "dispatch executor start=2026-08-26T09:05:00Z end=2026-08-26T09:12:00Z\n",
                encoding="utf-8",
            )
            passed, message = grade_dispatch_timestamps(workspace)
            self.assertFalse(passed, message)

    def test_dispatch_timestamps_catches_garbage_stamps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            (workspace / "journal.md").write_text(
                "dispatch 1 executor start=2026-08-26T09:00:00Z end=2026-08-26T09:04:00Z\n"
                "dispatch  2 executor start=nope end=nope\n",
                encoding="utf-8",
            )
            passed, message = grade_dispatch_timestamps(workspace)
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
    # run. Raise the ceiling for a longer task or a run whose phase was repaired.
    # The floor is what makes a gate this grader failed to RECOGNISE loud rather
    # than silent -- set it to the number of gate runs the run actually spent.
    DEFAULT_SUITE_FLOOR = 2
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

    def test_full_suite_runs_within_range(self) -> None:
        self.skipTest(
            "grade_full_suite_runs is DISABLED -- not fit for use. It over-counts "
            "(stem-mismatched .log/.result pairs; subset-suite legs) and silently "
            "under-counts (truncated or non-UTF-8 gate logs), and its floor cannot "
            "be set correctly. See its docstring. Do not re-enable without deriving "
            "the expected count from control/phase-*.json."
        )
        workspace = self.live_workspace()
        floor = int(os.environ.get("OPLAN_SMOKE_SUITE_FLOOR", self.DEFAULT_SUITE_FLOOR))
        ceiling = int(
            os.environ.get("OPLAN_SMOKE_SUITE_CEILING", self.DEFAULT_SUITE_CEILING)
        )
        passed, message = grade_full_suite_runs(
            workspace, self.FULL_SUITE_COMMAND, floor, ceiling
        )
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
