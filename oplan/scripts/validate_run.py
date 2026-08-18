#!/usr/bin/env python3
"""Validate an oplan run's Git base, state, controls, packets, decisions, and seals."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


STATES = {
    "INITIALIZING", "PLANNING", "REVIEWING_PLAN", "EXECUTING", "VALIDATING",
    "REVIEWING_RESULT", "CLOSING_PHASE", "COMPLETE", "BLOCKED",
    "AWAITING_HUMAN_DECISION",
}
TERMINAL = {"COMPLETE", "BLOCKED", "AWAITING_HUMAN_DECISION"}
STATE_KEYS = {
    "RUN", "STATE", "PHASE", "PHASE_CONTROL", "LEAF", "NEXT_ACTION", "ACTIVE_AGENT", "LAST_ACCEPTED",
    "ACCEPTED_THIS_PHASE", "DECISIONS_IN_FORCE", "OPEN_BLOCKER", "RETRY", "TERMINAL_REASON",
}
ACTIONS_BY_STATE = {
    "INITIALIZING": {"INITIALIZE_BASELINE"},
    "PLANNING": {"SPAWN_PHASE_PLANNER", "SPAWN_RESEARCH_AGENT"},
    "REVIEWING_PLAN": {"SPAWN_PLAN_REVIEWER", "SEAL_PHASE"},
    "EXECUTING": {"REPORT_PHASE_PLAN", "SPAWN_EXECUTOR", "REVERT_CANDIDATE"},
    "VALIDATING": {"RUN_VALIDATION"},
    "REVIEWING_RESULT": {
        "SPAWN_SPEC_AUDITOR", "COMPLETE_EVIDENCE", "SPAWN_SYSTEM_REVIEWER", "ACCEPT_LEAF",
    },
    "CLOSING_PHASE": {
        "RUN_PHASE_ACCEPTANCE", "RUN_OVERALL_ACCEPTANCE", "SPAWN_SYSTEM_REVIEWER",
        "SPAWN_PHASE_CURATOR", "CLOSE_PHASE",
    },
    "AWAITING_HUMAN_DECISION": {"ASK_HUMAN"},
    "COMPLETE": {"none"},
    "BLOCKED": {"none"},
}
ACTION_REQUIRED_KEYS = {
    "INITIALIZE_BASELINE": set(),
    "SPAWN_PHASE_PLANNER": {"phase", "mode", "source"},
    "SPAWN_RESEARCH_AGENT": {"blocker", "attempt"},
    "SPAWN_PLAN_REVIEWER": {"phase", "source"},
    "SEAL_PHASE": {"phase", "source"},
    "REPORT_PHASE_PLAN": {"phase", "source"},
    "SPAWN_EXECUTOR": {"control"},
    "REVERT_CANDIDATE": {"control"},
    "RUN_VALIDATION": {"control", "attempt"},
    "SPAWN_SPEC_AUDITOR": {"control"},
    "COMPLETE_EVIDENCE": {"control", "review"},
    "SPAWN_SYSTEM_REVIEWER": {"scope", "source"},
    "ACCEPT_LEAF": {"control"},
    "RUN_PHASE_ACCEPTANCE": {"phase", "source"},
    "RUN_OVERALL_ACCEPTANCE": {"phase", "source"},
    "SPAWN_PHASE_CURATOR": {"phase", "source"},
    "CLOSE_PHASE": {"phase"},
    "ASK_HUMAN": {"blocker"},
    "none": set(),
}
PACKET_MARKERS = (
    "**Goal:**",
    "**Files you may create or modify — exhaustive:**",
    "**Commands:**",
    "**Frozen validation:**",
    "**Dependent decisions:**",
    "**Contracts:**",
    "**Non-goals:**",
    "**Risk:**",
    "## Budgets",
    "STATUS: done | failed | stopped-with-question",
    "FAILURE_CAUSE:",
)
CONTROL_KEYS = {"step", "phase", "packet", "write_set", "validation", "risk", "decisions", "wall_time_minutes"}
OPTIONAL_CONTROL_KEYS = {"kind"}
PHASE_CONTROL_KEYS = {
    "phase", "revision", "name", "queue", "acceptance", "overall_acceptance", "next_phase",
    "plan_review",
}
MODEL_BINDING_KEYS = {
    "main_harness", "phase_planner", "plan_reviewer", "executor", "spec_auditor",
    "system_reviewer", "phase_curator", "research_agent", "evidence_reviewer", "worker_ladder",
    "research_ladder",
}
SHA_RE = re.compile(r"^[0-9a-f]{40}(?:[0-9a-f]{24})?$")
WORKTREE_GUARD = Path(__file__).with_name("worktree_guard.py")


def git(workspace: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(workspace), *args], text=True, capture_output=True, check=False
    )


def parse_state(path: Path, errors: list[str]) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) > 30:
        errors.append(f"phase-state.md: {len(lines)}/30 lines")
    values: dict[str, str] = {}
    for number, line in enumerate(lines, 1):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            errors.append(f"phase-state.md:{number}: expected KEY: value")
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        if key in values:
            errors.append(f"phase-state.md:{number}: duplicate key {key}")
        values[key] = value.strip()
    missing = STATE_KEYS - values.keys()
    extra = values.keys() - STATE_KEYS
    if missing:
        errors.append(f"phase-state.md: missing keys {sorted(missing)}")
    if extra:
        errors.append(f"phase-state.md: unknown keys {sorted(extra)}")
    return values


def parse_decisions(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    decisions: dict[str, str] = {}
    pattern = re.compile(r"^### (D-\d{3})\b(?P<body>.*?)(?=^### D-\d{3}\b|\Z)", re.MULTILINE | re.DOTALL)
    for match in pattern.finditer(text):
        status = re.search(r"^Status:\s*(proposed|approved|amended|superseded)\s*$", match.group("body"), re.MULTILINE)
        decisions[match.group(1)] = status.group(1) if status else "missing"
    return decisions


def safe_relative(value: str) -> bool:
    path = Path(value)
    return bool(value) and value != "." and not path.is_absolute() and ".." not in path.parts


def paths_overlap(first: str, second: str) -> bool:
    a, b = Path(first).parts, Path(second).parts
    return a == b[: len(a)] or b == a[: len(b)]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def atomic_write(path: Path, content: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        Path(temporary).replace(path)
    except BaseException:
        try:
            Path(temporary).unlink()
        except FileNotFoundError:
            pass
        raise


def expected_seal(workspace: Path, control_path: Path, control: dict[str, object]) -> str:
    packet_path = workspace / str(control["packet"])
    control_rel = control_path.relative_to(workspace).as_posix()
    packet_rel = packet_path.relative_to(workspace).as_posix()
    return f"{sha256(packet_path)}  {packet_rel}\n{sha256(control_path)}  {control_rel}\n"


def expected_phase_seal(workspace: Path, phase_path: Path, phase_control: dict[str, object]) -> str:
    review_path = workspace / str(phase_control["plan_review"])
    phase_rel = phase_path.relative_to(workspace).as_posix()
    review_rel = review_path.relative_to(workspace).as_posix()
    return f"{sha256(phase_path)}  {phase_rel}\n{sha256(review_path)}  {review_rel}\n"


def promote_decisions(text: str, decision_ids: set[str]) -> str:
    for decision in sorted(decision_ids):
        pattern = re.compile(
            rf"(^### {re.escape(decision)}\b.*?^Status:\s*)proposed(\s*$)",
            re.MULTILINE | re.DOTALL,
        )
        text, count = pattern.subn(r"\1approved\2", text, count=1)
        if count != 1:
            raise ValueError(f"could not promote {decision}")
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--phase", type=int, help="validate controls and packets for this phase")
    seals = parser.add_mutually_exclusive_group()
    seals.add_argument("--seal", action="store_true", help="write missing immutable seals after ship")
    seals.add_argument("--require-sealed", action="store_true", help="require and verify all selected seals")
    args = parser.parse_args()
    if (args.seal or args.require_sealed) and args.phase is None:
        parser.error("--seal/--require-sealed requires --phase")

    workspace = args.workspace.resolve()
    errors: list[str] = []
    required_files = [
        "request.md", "baseline.md", "model-bindings.md", "design.md", "plan.md",
        "phase-state.md", "journal.md", "STATUS.md", "briefing.md", "field-guide/index.md",
    ]
    required_dirs = ["control", "packets", "seals", "blockers", "research", "attempts", "logs", "reviews"]
    for relative in required_files:
        path = workspace / relative
        if not path.is_file():
            errors.append(f"missing workspace artifact: {relative}")
        elif relative in {"request.md", "baseline.md", "model-bindings.md"} and not path.read_text(encoding="utf-8").strip():
            errors.append(f"workspace artifact is empty: {relative}")
    for relative in required_dirs:
        if not (workspace / relative).is_dir():
            errors.append(f"missing workspace directory: {relative}")

    hygiene_files = [workspace / name for name in required_files if name != "request.md"]
    for directory in ("control", "packets", "seals", "blockers", "research", "attempts", "reviews"):
        root = workspace / directory
        if root.is_dir():
            hygiene_files.extend(path for path in root.rglob("*") if path.is_file())
    for path in hygiene_files:
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            errors.append(f"{path.relative_to(workspace)}: artifact must be UTF-8 text")
            continue
        for number, line in enumerate(lines, 1):
            if line.endswith((" ", "\t")):
                errors.append(f"{path.relative_to(workspace)}:{number}: trailing whitespace")

    state: dict[str, str] = {}
    state_path = workspace / "phase-state.md"
    if state_path.is_file():
        state = parse_state(state_path, errors)
        current = state.get("STATE", "")
        if current not in STATES:
            errors.append(f"phase-state.md: illegal STATE {current!r}")
        next_action = state.get("NEXT_ACTION", "")
        verb = next_action.split(maxsplit=1)[0] if next_action else ""
        if current in ACTIONS_BY_STATE and verb not in ACTIONS_BY_STATE[current]:
            errors.append(f"phase-state.md: action {verb!r} is illegal for STATE {current!r}")
        elif verb in ACTION_REQUIRED_KEYS:
            tokens = next_action.split()[1:]
            malformed = [token for token in tokens if "=" not in token]
            pairs = [token.split("=", 1) for token in tokens if "=" in token]
            keys = [key for key, _value in pairs]
            arguments = set(keys)
            missing_args = ACTION_REQUIRED_KEYS[verb] - arguments
            unexpected_args = arguments - ACTION_REQUIRED_KEYS[verb]
            duplicate_args = sorted({key for key in keys if keys.count(key) > 1})
            empty_args = sorted(key for key, value in pairs if not value)
            if malformed or missing_args or unexpected_args or duplicate_args or empty_args:
                errors.append(
                    f"phase-state.md: action {verb} malformed={malformed} "
                    f"missing_args={sorted(missing_args)} unexpected_args={sorted(unexpected_args)} "
                    f"duplicate_args={duplicate_args} empty_args={empty_args}"
                )
        reason = state.get("TERMINAL_REASON")
        if current in TERMINAL and reason in {"", "none", None}:
            errors.append("phase-state.md: terminal state requires TERMINAL_REASON")
        if current not in TERMINAL and reason not in {"none", None}:
            errors.append("phase-state.md: nonterminal state requires TERMINAL_REASON: none")

    repo_check = git(workspace, "rev-parse", "--show-toplevel")
    git_root: Path | None = None
    if repo_check.returncode:
        errors.append("workspace is not inside a Git worktree")
    else:
        git_root = Path(repo_check.stdout.strip()).resolve()

    last_accepted = state.get("LAST_ACCEPTED", "")
    if not SHA_RE.fullmatch(last_accepted):
        errors.append("phase-state.md: LAST_ACCEPTED must be a full commit SHA, not HEAD")
    elif git_root is not None and git(workspace, "cat-file", "-e", f"{last_accepted}^{{commit}}").returncode:
        errors.append(f"phase-state.md: LAST_ACCEPTED commit does not exist: {last_accepted}")

    protected_paths: set[str] = set()
    commit_mode = ""
    baseline_path = workspace / "baseline.md"
    if baseline_path.is_file():
        baseline = baseline_path.read_text(encoding="utf-8")
        mode_matches = re.findall(r"^commit_mode:\s*(\S+)\s*$", baseline, re.MULTILINE)
        if not mode_matches:
            errors.append("baseline.md: missing commit_mode")
        elif len(mode_matches) > 1:
            errors.append("baseline.md: commit_mode must appear exactly once")
        else:
            commit_mode = mode_matches[0]
            if commit_mode not in {"auto", "none"}:
                errors.append("baseline.md: commit_mode must be auto or none")
        run_modes_matches = re.findall(r"^run_modes:\s*(\S+)\s*$", baseline, re.MULTILINE)
        if not run_modes_matches:
            errors.append("baseline.md: missing run_modes")
        elif len(run_modes_matches) > 1:
            errors.append("baseline.md: run_modes must appear exactly once")
        else:
            run_modes = run_modes_matches[0]
            if run_modes not in {"autonomous", "pause-between-phases", "step-by-step"}:
                errors.append(
                    "baseline.md: run_modes must be autonomous, pause-between-phases, or step-by-step"
                )
        depth_profile_matches = re.findall(r"^depth_profile:\s*(\S+)\s*$", baseline, re.MULTILINE)
        if not depth_profile_matches:
            errors.append("baseline.md: missing depth_profile")
        elif len(depth_profile_matches) > 1:
            errors.append("baseline.md: depth_profile must appear exactly once")
        else:
            depth_profile = depth_profile_matches[0]
            if depth_profile not in {"fast", "standard", "paranoid"}:
                errors.append("baseline.md: depth_profile must be fast, standard, or paranoid")
        work_mode_matches = re.findall(r"^work_mode:\s*(\S+)\s*$", baseline, re.MULTILINE)
        if not work_mode_matches:
            errors.append("baseline.md: missing work_mode")
        elif len(work_mode_matches) > 1:
            errors.append("baseline.md: work_mode must appear exactly once")
        else:
            work_mode = work_mode_matches[0]
            if work_mode not in {"engineering", "experiment"}:
                errors.append("baseline.md: work_mode must be engineering or experiment")
        match = re.search(r"^commit:\s*([0-9a-f]{40}(?:[0-9a-f]{24})?)\s*$", baseline, re.MULTILINE)
        if not match:
            errors.append("baseline.md: missing full 'commit: <SHA>'")
        elif git_root is not None and git(workspace, "cat-file", "-e", f"{match.group(1)}^{{commit}}").returncode:
            errors.append(f"baseline.md: commit does not exist: {match.group(1)}")
        protected_match = re.search(r"^protected_paths:\s*(\[.*\])\s*$", baseline, re.MULTILINE)
        if not protected_match:
            errors.append("baseline.md: protected_paths must be a JSON array")
        else:
            try:
                raw_paths = json.loads(protected_match.group(1))
                if not isinstance(raw_paths, list) or not all(isinstance(p, str) and safe_relative(p) for p in raw_paths):
                    raise ValueError
                protected_paths = set(raw_paths)
            except (json.JSONDecodeError, ValueError):
                errors.append("baseline.md: protected_paths must contain safe relative paths")
        request_match = re.search(r"^request_sha256:\s*([0-9a-f]{64})\s*$", baseline, re.MULTILINE)
        if not request_match:
            errors.append("baseline.md: missing request_sha256")
        elif (workspace / "request.md").is_file() and request_match.group(1) != sha256(workspace / "request.md"):
            errors.append("request.md: immutable brief hash mismatch")

    bindings = workspace / "model-bindings.md"
    if bindings.is_file():
        binding_values = {
            key: value.strip()
            for key, value in re.findall(r"^([a-z_]+):\s*(.*)$", bindings.read_text(encoding="utf-8"), re.MULTILINE)
        }
        missing_bindings = sorted(
            key for key in MODEL_BINDING_KEYS if not binding_values.get(key)
        )
        if missing_bindings:
            errors.append(f"model-bindings.md: missing nonempty bindings {missing_bindings}")

    decisions: dict[str, str] = {}
    design_path = workspace / "design.md"
    if design_path.is_file():
        design_text = design_path.read_text(encoding="utf-8")
        decision_headings = re.findall(r"^### (D-\d{3})\b", design_text, re.MULTILINE)
        duplicates = sorted({decision for decision in decision_headings if decision_headings.count(decision) > 1})
        if duplicates:
            errors.append(f"design.md: duplicate decision IDs {duplicates}")
        decisions = parse_decisions(design_path)
        for decision, status in decisions.items():
            if status == "missing":
                errors.append(f"design.md: {decision} has no legal Status")
    in_force = set(re.findall(r"\bD-\d{3}\b", state.get("DECISIONS_IN_FORCE", "")))
    for decision in in_force:
        if decision not in decisions:
            errors.append(f"phase-state.md: DECISIONS_IN_FORCE references undefined {decision}")
        elif decisions[decision] not in {"approved", "amended"}:
            errors.append(f"phase-state.md: DECISIONS_IN_FORCE includes non-approved {decision}")

    controls: list[tuple[Path, dict[str, object]]] = []
    all_controls: dict[str, tuple[Path, dict[str, object]]] = {}
    phase_path: Path | None = None
    phase_control: dict[str, object] | None = None
    proposed_to_promote: set[str] = set()
    referenced_to_force: set[str] = set()
    control_dir = workspace / "control"
    if control_dir.is_dir():
        for control_path in sorted(control_dir.glob("*.json")):
            if control_path.name.startswith("phase-"):
                continue
            try:
                control = json.loads(control_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(f"{control_path.name}: invalid JSON: {exc}")
                continue
            if not isinstance(control, dict):
                errors.append(f"{control_path.name}: control must be a JSON object")
                continue
            missing = CONTROL_KEYS - control.keys()
            extra = control.keys() - CONTROL_KEYS - OPTIONAL_CONTROL_KEYS
            if missing or extra:
                errors.append(f"{control_path.name}: control keys missing={sorted(missing)} extra={sorted(extra)}")
                continue
            all_controls[control_path.relative_to(workspace).as_posix()] = (control_path, control)

    if args.phase is not None:
        phase_rel = state.get("PHASE_CONTROL", "")
        if not safe_relative(phase_rel) or not phase_rel.startswith("control/phase-"):
            errors.append("phase-state.md: --phase requires a safe PHASE_CONTROL path")
        else:
            phase_path = workspace / phase_rel
            try:
                loaded_phase = json.loads(phase_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
                errors.append(f"{phase_rel}: invalid phase control: {exc}")
            else:
                if not isinstance(loaded_phase, dict):
                    errors.append(f"{phase_rel}: phase control must be a JSON object")
                else:
                    phase_control = loaded_phase
                    missing = PHASE_CONTROL_KEYS - phase_control.keys()
                    extra = phase_control.keys() - PHASE_CONTROL_KEYS
                    if missing or extra:
                        errors.append(f"{phase_rel}: phase-control keys missing={sorted(missing)} extra={sorted(extra)}")
                    phase_number = phase_control.get("phase")
                    revision = phase_control.get("revision")
                    if phase_number != args.phase or not isinstance(revision, int) or revision < 1:
                        errors.append(f"{phase_rel}: phase/revision mismatch")
                    expected_stem = f"phase-{args.phase}" if revision == 1 else f"phase-{args.phase}-r{revision}"
                    if phase_path.stem != expected_stem:
                        errors.append(f"{phase_rel}: filename does not match phase/revision")
                    if not isinstance(phase_control.get("name"), str) or not str(phase_control.get("name")).strip():
                        errors.append(f"{phase_rel}: name must be nonempty")
                    queue = phase_control.get("queue")
                    if not isinstance(queue, list) or not queue or not all(
                        isinstance(item, str) and safe_relative(item) and item.startswith("control/")
                        for item in queue
                    ):
                        errors.append(f"{phase_rel}: queue must contain safe control paths")
                        queue = []
                    if len(queue) != len(set(queue)):
                        errors.append(f"{phase_rel}: queue contains duplicates")
                    for item in queue:
                        if item not in all_controls:
                            errors.append(f"{phase_rel}: queue references missing leaf control {item}")
                        else:
                            controls.append(all_controls[item])
                    acceptance = phase_control.get("acceptance")
                    if not isinstance(acceptance, list) or not acceptance or not all(
                        isinstance(command, str) and command.strip() for command in acceptance
                    ):
                        errors.append(f"{phase_rel}: acceptance must contain nonempty commands")
                    overall = phase_control.get("overall_acceptance")
                    if not isinstance(overall, list) or not all(
                        isinstance(command, str) and command.strip() for command in overall
                    ):
                        errors.append(f"{phase_rel}: overall_acceptance must contain command strings")
                        overall = []
                    next_phase = phase_control.get("next_phase")
                    if next_phase is None:
                        if not overall:
                            errors.append(f"{phase_rel}: final phase requires overall_acceptance")
                    elif not isinstance(next_phase, dict) or set(next_phase) != {"number", "name"}:
                        errors.append(f"{phase_rel}: next_phase must be null or number/name object")
                    elif next_phase.get("number") != args.phase + 1 or not isinstance(next_phase.get("name"), str) or not next_phase.get("name", "").strip():
                        errors.append(f"{phase_rel}: next_phase must name consecutive nonempty phase")
                    elif overall:
                        errors.append(f"{phase_rel}: non-final phase overall_acceptance must be empty")
                    review_rel = phase_control.get("plan_review")
                    if not isinstance(review_rel, str) or not safe_relative(review_rel) or not review_rel.startswith("reviews/"):
                        errors.append(f"{phase_rel}: plan_review must be a safe reviews/ path")
                    else:
                        expected_review = f"reviews/phase-{args.phase}-plan-r{revision}.md"
                        if review_rel != expected_review:
                            errors.append(f"{phase_rel}: plan_review must equal {expected_review}")
    else:
        controls = list(all_controls.values())

    if args.phase is not None and not controls:
        errors.append(f"no active leaf controls found for phase {args.phase}")

    current_state = state.get("STATE", "")
    phase_rel = state.get("PHASE_CONTROL", "")
    if current_state in {"REVIEWING_PLAN", "EXECUTING", "VALIDATING", "REVIEWING_RESULT", "CLOSING_PHASE"}:
        if not safe_relative(phase_rel) or not phase_rel.startswith("control/phase-"):
            errors.append(f"phase-state.md: STATE {current_state} requires PHASE_CONTROL")
    action_parts = state.get("NEXT_ACTION", "").split()
    action_verb = action_parts[0] if action_parts else ""
    action_values = {
        token.split("=", 1)[0]: token.split("=", 1)[1]
        for token in action_parts[1:]
        if "=" in token
    }
    if action_verb in {
        "SPAWN_PLAN_REVIEWER", "SEAL_PHASE", "REPORT_PHASE_PLAN", "RUN_PHASE_ACCEPTANCE",
        "RUN_OVERALL_ACCEPTANCE",
    }:
        if action_values.get("source") != phase_rel:
            errors.append(f"phase-state.md: {action_verb} source must equal PHASE_CONTROL")
    active_queue = {
        path.relative_to(workspace).as_posix() for path, _control in controls
    } if args.phase is not None else set()
    if args.phase is not None and action_verb in {
        "SPAWN_EXECUTOR", "REVERT_CANDIDATE", "RUN_VALIDATION", "SPAWN_SPEC_AUDITOR",
        "COMPLETE_EVIDENCE", "ACCEPT_LEAF"
    }:
        if action_values.get("control") not in active_queue:
            errors.append(f"phase-state.md: {action_verb} control is not in active phase queue")

    for control_path, control in controls:
        label = control_path.name
        step = control.get("step")
        valid_step = isinstance(step, str) and re.fullmatch(r"\d+\.\d+(?:-r\d+)?", step)
        if not valid_step:
            errors.append(f"{label}: invalid step ID")
        if valid_step and control_path.stem != step:
            errors.append(f"{label}: filename must match step ID")
        if not isinstance(control.get("phase"), int) or (
            valid_step and int(str(step).split(".", 1)[0]) != control.get("phase")
        ):
            errors.append(f"{label}: phase does not match step")
        if args.phase is not None and control.get("phase") != args.phase:
            errors.append(f"{label}: active queue control is not in phase {args.phase}")
        packet_rel = control.get("packet")
        if not isinstance(packet_rel, str) or not safe_relative(packet_rel):
            errors.append(f"{label}: packet must be a safe relative path")
            continue
        if valid_step and packet_rel != f"packets/{step}.md":
            errors.append(f"{label}: packet must equal packets/{step}.md")
        packet_path = workspace / packet_rel
        if not packet_path.is_file():
            errors.append(f"{label}: missing packet {packet_rel}")
            continue
        write_set = control.get("write_set")
        if not isinstance(write_set, list) or not write_set or not all(isinstance(p, str) and safe_relative(p) for p in write_set):
            errors.append(f"{label}: write_set must be nonempty safe relative paths")
            write_set = []
        if len(write_set) != len(set(write_set)):
            errors.append(f"{label}: duplicate write_set path")
        try:
            workspace_rel = workspace.relative_to(git_root).as_posix() if git_root is not None else ""
        except ValueError:
            workspace_rel = ""
        for path in write_set:
            if paths_overlap(path, ".git") or (workspace_rel and paths_overlap(path, workspace_rel)):
                errors.append(f"{label}: write_set overlaps Git metadata or oplan workspace: {path}")
            if commit_mode == "auto":
                for protected in protected_paths:
                    if paths_overlap(path, protected):
                        errors.append(f"{label}: write_set {path} overlaps protected baseline path {protected}")
        validation = control.get("validation")
        if not isinstance(validation, str) or not validation.strip():
            errors.append(f"{label}: validation must be nonempty")
        risk = control.get("risk")
        if risk not in {"low", "high"}:
            errors.append(f"{label}: risk must be low or high")
        if "kind" in control and control.get("kind") not in {"measurement", "engineering"}:
            errors.append(f"{label}: kind must be measurement or engineering")
        wall_time = control.get("wall_time_minutes")
        if isinstance(wall_time, bool) or not isinstance(wall_time, int) or wall_time < 1:
            errors.append(f"{label}: wall_time_minutes must be a positive integer")
        control_decisions = control.get("decisions")
        if not isinstance(control_decisions, list) or not all(isinstance(d, str) and re.fullmatch(r"D-\d{3}", d) for d in control_decisions):
            errors.append(f"{label}: decisions must be D-### strings")
            control_decisions = []
        for decision in control_decisions:
            if decision not in decisions:
                errors.append(f"{label}: references undefined decision {decision}")
            elif args.require_sealed and decisions[decision] not in {"approved", "amended"}:
                errors.append(f"{label}: sealed control uses non-approved decision {decision}")
            elif args.seal and decisions[decision] == "proposed":
                proposed_to_promote.add(decision)
            elif args.seal and decisions[decision] not in {"approved", "amended"}:
                errors.append(f"{label}: cannot seal decision {decision} with status {decisions[decision]}")
            if args.seal and decision in decisions and decisions[decision] in {"proposed", "approved", "amended"}:
                referenced_to_force.add(decision)

        try:
            packet_text = packet_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for marker in PACKET_MARKERS:
            if marker not in packet_text:
                errors.append(f"{packet_path.name}: missing {marker}")
        if f"**Risk:** {risk}" not in packet_text:
            errors.append(f"{label}: risk disagrees with packet")
        for value in [*write_set, *control_decisions]:
            if value not in packet_text:
                errors.append(f"{label}: {value!r} missing from packet")
        if isinstance(validation, str) and validation not in packet_text:
            errors.append(f"{label}: validation disagrees with packet")

        seal_path = workspace / "seals" / f"{step}.sha256"
        if seal_path.exists() or args.require_sealed:
            if not seal_path.is_file():
                errors.append(f"{label}: missing seal {seal_path.relative_to(workspace)}")
            else:
                expected = expected_seal(workspace, control_path, control)
                if seal_path.read_text(encoding="utf-8") != expected:
                    errors.append(f"{label}: seal mismatch; packet/control changed after review")

    if commit_mode == "none" and git_root is not None:
        accepted_manifest = workspace / "attempts/accepted-state.json"
        if not accepted_manifest.is_file():
            errors.append("commit_mode none: missing attempts/accepted-state.json")
        else:
            try:
                manifest = json.loads(accepted_manifest.read_text(encoding="utf-8"))
                if not isinstance(manifest, dict):
                    raise TypeError("accepted manifest must be a JSON object")
                manifest_steps = {
                    Path(item["path"]).stem
                    for item in manifest["controls"]
                    if isinstance(item, dict) and isinstance(item.get("path"), str)
                }
            except (OSError, UnicodeDecodeError, json.JSONDecodeError, TypeError, KeyError):
                manifest_steps = set()
            accepted_steps = set(re.findall(r"\d+\.\d+(?:-r\d+)?", state.get("ACCEPTED_THIS_PHASE", "")))
            missing_steps = accepted_steps - manifest_steps
            if missing_steps:
                errors.append(
                    f"accepted-state.json: missing current accepted steps {sorted(missing_steps)}"
                )
            result = subprocess.run(
                [sys.executable, str(WORKTREE_GUARD), "verify-accepted", str(git_root), str(accepted_manifest)],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode:
                detail = (result.stdout or result.stderr).strip().replace("\n", "; ")
                errors.append(f"accepted-state.json: {detail}")

    phase_seal_path: Path | None = None
    if phase_path is not None and phase_control is not None:
        phase_seal_path = workspace / "seals" / f"{phase_path.stem}.sha256"
        if phase_seal_path.exists() or args.require_sealed:
            review_rel = phase_control.get("plan_review")
            review_path = workspace / str(review_rel)
            if not review_path.is_file():
                errors.append(f"{phase_path.name}: missing plan review {review_rel}")
            elif not phase_seal_path.is_file():
                errors.append(f"{phase_path.name}: missing phase seal {phase_seal_path.relative_to(workspace)}")
            else:
                expected = expected_phase_seal(workspace, phase_path, phase_control)
                if phase_seal_path.read_text(encoding="utf-8") != expected:
                    errors.append(f"{phase_path.name}: phase-control/review seal mismatch")

    if args.seal:
        phase_rel = state.get("PHASE_CONTROL", "")
        expected_action = f"SEAL_PHASE phase={args.phase} source={phase_rel}"
        if state.get("STATE") != "REVIEWING_PLAN" or state.get("NEXT_ACTION") != expected_action:
            errors.append(f"--seal requires REVIEWING_PLAN with NEXT_ACTION: {expected_action}")
        if phase_control is None:
            errors.append(f"cannot seal phase {args.phase}: active phase control is invalid")
        else:
            review = workspace / str(phase_control.get("plan_review"))
            if not review.is_file() or not re.search(r"^VERDICT:\s*ship\s*$", review.read_text(encoding="utf-8"), re.MULTILINE):
                errors.append(f"cannot seal phase {args.phase}: active plan review VERDICT is not ship")

    guide = workspace / "field-guide/index.md"
    if guide.is_file():
        count = len(guide.read_text(encoding="utf-8").splitlines())
        journal_path = workspace / "journal.md"
        journal = journal_path.read_text(encoding="utf-8") if journal_path.is_file() else ""
        if count > 40 and "field guide overflow:" not in journal.lower():
            errors.append(f"field-guide/index.md: {count}/40 lines without journal justification")

    if errors:
        print("oplan run validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    if args.seal:
        design_text = design_path.read_text(encoding="utf-8")
        if proposed_to_promote:
            try:
                design_text = promote_decisions(design_text, proposed_to_promote)
            except ValueError as exc:
                print("oplan run validation: FAIL")
                print(f"- design.md: {exc}")
                return 1
            atomic_write(design_path, design_text)
        state_text = state_path.read_text(encoding="utf-8")
        active = sorted(in_force | referenced_to_force)
        state_text = re.sub(
            r"^DECISIONS_IN_FORCE:.*$",
            f"DECISIONS_IN_FORCE: {', '.join(active) if active else 'none'}",
            state_text,
            flags=re.MULTILINE,
        )
        atomic_write(state_path, state_text)
        for control_path, control in controls:
            seal_path = workspace / "seals" / f"{control['step']}.sha256"
            expected = expected_seal(workspace, control_path, control)
            if not seal_path.exists():
                atomic_write(seal_path, expected)
        if phase_path is not None and phase_control is not None and phase_seal_path is not None:
            expected = expected_phase_seal(workspace, phase_path, phase_control)
            if not phase_seal_path.exists():
                atomic_write(phase_seal_path, expected)

    print(f"oplan run validation: PASS ({len(controls)} controls, {len(decisions)} decisions)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
