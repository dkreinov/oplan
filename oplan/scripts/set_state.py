#!/usr/bin/env python3
"""Write a schema-valid phase-state.md update; refuse any illegal state, verb, or argument set."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from validate_run import (  # noqa: E402
    ACTION_REQUIRED_KEYS,
    ACTIONS_BY_STATE,
    STATE_KEYS,
    STATES,
    TERMINAL,
    atomic_write,
    parse_state,
)

KEY_ORDER = [
    "RUN", "STATE", "PHASE", "PHASE_CONTROL", "LEAF", "NEXT_ACTION", "ACTIVE_AGENT",
    "LAST_ACCEPTED", "ACCEPTED_THIS_PHASE", "DECISIONS_IN_FORCE", "OPEN_BLOCKER", "RETRY",
    "TERMINAL_REASON",
]


def main() -> int:
    if len(sys.argv) < 3:
        print("usage: set_state.py <workspace> KEY=VALUE [KEY=VALUE ...]")
        return 2
    workspace = Path(sys.argv[1]).resolve()
    state_path = workspace / "phase-state.md"
    if not state_path.is_file():
        print(f"set-state: missing {state_path}")
        return 2
    values = parse_state(state_path, [])
    updates: dict[str, str] = {}
    for token in sys.argv[2:]:
        if "=" not in token:
            print(f"set-state: argument must be KEY=VALUE: {token}")
            return 2
        key, value = token.split("=", 1)
        if key not in STATE_KEYS:
            print(f"set-state: unknown key {key}")
            return 2
        updates[key] = value.strip()
    values.update(updates)

    errors: list[str] = []
    missing = STATE_KEYS - values.keys()
    if missing:
        errors.append(f"missing keys {sorted(missing)}")
    current = values.get("STATE", "")
    if current not in STATES:
        errors.append(f"illegal STATE {current!r}")
    next_action = values.get("NEXT_ACTION", "")
    verb = next_action.split(maxsplit=1)[0] if next_action else ""
    if current in ACTIONS_BY_STATE and verb not in ACTIONS_BY_STATE[current]:
        errors.append(f"action {verb!r} is illegal for STATE {current!r}")
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
                f"action {verb} malformed={malformed} missing_args={sorted(missing_args)} "
                f"unexpected_args={sorted(unexpected_args)} duplicate_args={duplicate_args} "
                f"empty_args={empty_args}"
            )
    reason = values.get("TERMINAL_REASON")
    if current in TERMINAL and reason in {"", "none", None}:
        errors.append("terminal state requires TERMINAL_REASON")
    if current not in TERMINAL and reason not in {"none", None}:
        errors.append("nonterminal state requires TERMINAL_REASON: none")

    if errors:
        print("set-state: REFUSED, nothing written")
        for error in errors:
            print(f"- {error}")
        return 1

    content = "".join(f"{key}: {values[key]}\n" for key in KEY_ORDER)
    atomic_write(state_path, content)
    print(f"set-state: OK ({', '.join(sorted(updates))})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
