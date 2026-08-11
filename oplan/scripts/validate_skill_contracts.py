#!/usr/bin/env python3
"""Validate oplan's load-bearing cross-file contracts without external dependencies."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"


def require(condition: bool, message: str, errors: list[str]) -> None:
    if not condition:
        errors.append(message)


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

    if errors:
        print("oplan contract validation: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(f"oplan contract validation: PASS ({len(lines)} SKILL.md lines, {len(required_files)} resources)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
