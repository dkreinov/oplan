#!/usr/bin/env python3
"""Validate oplan's load-bearing cross-file contracts without external dependencies."""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


def action_argument_table(text: str) -> dict[str, set[str]] | None:
    lines = text.splitlines()
    header_index = None
    for index, line in enumerate(lines):
        if line.strip() == "| Verb | Required arguments |":
            header_index = index
            break
    if header_index is None:
        return None

    mapping: dict[str, set[str]] = {}
    for line in lines[header_index + 1 :]:
        if not line.startswith("|"):
            break
        cells = line.split("|")
        if all(re.fullmatch(r"-*", cell.strip()) for cell in cells):
            continue
        inner = [cell.strip() for cell in cells[1:-1]]
        if len(inner) != 2:
            continue
        verb_match = re.fullmatch(r"`([A-Za-z_]+)`", inner[0])
        if verb_match is None:
            continue
        argument_cell = inner[1]
        if argument_cell == "none":
            arguments: set[str] = set()
        else:
            arguments = set(re.findall(r"`([a-z_]+)`", argument_cell))
        mapping[verb_match.group(1)] = arguments
    return mapping


def main() -> int:
    errors: list[str] = []
    text = SKILL.read_text(encoding="utf-8")
    lines = text.splitlines()

    require(len(lines) <= 500, f"SKILL.md is {len(lines)} lines; maximum is 500", errors)
    require(text.startswith("---\n"), "SKILL.md lacks YAML frontmatter", errors)

    parts = text.split("---", 2)
    require(len(parts) == 3, "SKILL.md frontmatter is not closed", errors)
    if len(parts) == 3:
        keys = {
            line.split(":", 1)[0].strip()
            for line in parts[1].splitlines()
            if line.strip() and not line.startswith(" ") and ":" in line
        }
        require(keys == {"name", "description"}, f"frontmatter keys must be name+description, got {sorted(keys)}", errors)

    required_phrases = [
        "A successful phase close is never a terminal state.",
        "The main thread coordinates; it never produces feature plans or product code.",
        "Use [phase-planner.md](templates/phase-planner.md) for **Phase 1 and every later phase**.",
        "`PHASE_CLOSED` is an event, never a terminal state.",
        "Do not invoke `grill-me` merely because a phase ended.",
        "Conversation inheritance must be disabled",
        "Do not invent an unlisted transition.",
        "--phase N --seal",
        "Never wait with no spawned target.",
        "do not wrap it in another command string in any language",
    ]
    for phrase in required_phrases:
        require(phrase in text, f"missing load-bearing phrase: {phrase}", errors)

    terminal_block = re.search(
        r"Legal terminal states are exactly:(.*?)(?:\n## |\Z)", text, re.DOTALL
    )
    require(terminal_block is not None, "terminal-state block missing", errors)
    if terminal_block:
        block = terminal_block.group(1)
        for state in ("COMPLETE", "BLOCKED", "AWAITING_HUMAN_DECISION"):
            require(f"`{state}`" in block, f"terminal state {state} missing", errors)

    forbidden = [
        "Default at every phase boundary: pause",
        "wait for the human's go-ahead before the first dispatch",
        "templates/next-phase-planner.md",
        "python3 <skill-dir>",
    ]
    for phrase in forbidden:
        require(phrase not in text, f"obsolete contract remains: {phrase}", errors)

    linked = re.findall(r"\]\((templates|references)/([^)]+)\)", text)
    for folder, name in linked:
        require((ROOT / folder / name).is_file(), f"missing linked resource: {folder}/{name}", errors)

    required_files = [
        "templates/phase-planner.md",
        "templates/plan-reviewer.md",
        "templates/executor-packet.md",
        "templates/auditor.md",
        "templates/system-reviewer.md",
        "templates/research-agent.md",
        "templates/phase-curator.md",
        "templates/evidence-reviewer.md",
        "templates/human-report.md",
        "references/state-and-records.md",
        "references/grill-gate.md",
        "references/model-policy.md",
        "scripts/validate_run.py",
        "scripts/worktree_guard.py",
    ]
    for relative in required_files:
        require((ROOT / relative).is_file(), f"required resource missing: {relative}", errors)

    report_contract = [
        "If you hit a question the packet does not answer, STOP and return the question. Never decide it yourself.",
        "STATUS: done | failed | stopped-with-question",
        "FAILURE_CAUSE:",
        "STRUCTURAL_FLAGS:",
        "CHANGE_PROPOSAL:",
        "METRICS: retries=N, validation_first_try=yes|no",
    ]
    packet = (ROOT / "templates/executor-packet.md").read_text(encoding="utf-8")
    for phrase in report_contract:
        require(phrase in packet, f"executor report contract missing: {phrase}", errors)

    state_and_records = (ROOT / "references/state-and-records.md").read_text(encoding="utf-8")
    state_and_records_phrases = [
        "Retry-only context such as a failing-log path belongs in the fresh agent prompt",
        "The guard defends against accidental scope violations, not against an executor that deliberately forges harness records.",
        "`ACTION_REQUIRED_KEYS` in `oplan/scripts/validate_run.py`",
        "<python> <skill-dir>/scripts/worktree_guard.py init-accepted",
    ]
    for phrase in state_and_records_phrases:
        require(phrase in state_and_records, f"state-and-records.md missing phrase: {phrase}", errors)
    require(
        "python3 <skill-dir>" not in state_and_records,
        "state-and-records.md: obsolete contract remains: python3 <skill-dir>",
        errors,
    )

    system_reviewer = (ROOT / "templates/system-reviewer.md").read_text(encoding="utf-8")
    system_reviewer_phrases = [
        "re-read every file path and decision ID",
        "verified cumulative `attempts/accepted-state.json`",
    ]
    for phrase in system_reviewer_phrases:
        require(phrase in system_reviewer, f"system-reviewer.md missing phrase: {phrase}", errors)

    evidence_reviewer = (ROOT / "templates/evidence-reviewer.md").read_text(encoding="utf-8")
    require(
        "pre-attempt snapshot-to-worktree diff" in evidence_reviewer,
        "evidence-reviewer.md missing phrase: pre-attempt snapshot-to-worktree diff",
        errors,
    )

    worktree_guard = (ROOT / "scripts/worktree_guard.py").read_text(encoding="utf-8")
    worktree_guard_phrases = [
        "oplan-accepted-state/v1",
        "init-accepted",
        "record-accepted",
        "verify-accepted",
        "path traverses a symlink or junction",
        "write_set directory contains a symlink or junction",
        "accepted state drifted outside the accepted write set",
        "cannot restore symlink write_set path (unsupported)",
    ]
    for phrase in worktree_guard_phrases:
        require(phrase in worktree_guard, f"worktree guard missing {phrase}", errors)

    try:
        spec = importlib.util.spec_from_file_location(
            "oplan_validate_run", ROOT / "scripts/validate_run.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        validator_action_required_keys = module.ACTION_REQUIRED_KEYS
    except Exception as exc:  # noqa: BLE001 - never let this validator crash
        errors.append(f"could not load ACTION_REQUIRED_KEYS from scripts/validate_run.py: {exc}")
    else:
        doc_table = action_argument_table(state_and_records)
        require(
            doc_table is not None,
            "state-and-records.md: required action arguments table missing",
            errors,
        )
        if doc_table is not None:
            doc_verbs = set(doc_table)
            validator_verbs = set(validator_action_required_keys)
            require(
                doc_verbs == validator_verbs,
                f"state-and-records.md: action-argument table verbs differ: {sorted(doc_verbs ^ validator_verbs)}",
                errors,
            )
            for verb in sorted(doc_verbs & validator_verbs):
                doc_args = doc_table[verb]
                validator_args = validator_action_required_keys[verb]
                require(
                    doc_args == validator_args,
                    f"state-and-records.md: action-argument mismatch for {verb}: "
                    f"doc={sorted(doc_args)} validator={sorted(validator_args)}",
                    errors,
                )

    if errors:
        print("oplan contract validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"oplan contract validation: PASS ({len(lines)} SKILL.md lines, {len(required_files)} resources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
