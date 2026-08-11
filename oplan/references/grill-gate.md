# Optional grill-me escalation gate

Use this only when a phase planner or plan reviewer returns a blocker. `grill-me` is an interactive
design interrogation tool, not a generic debugging or research agent.

## Classification

| Blocker | Owner | Action |
|---|---|---|
| Repository or documentation fact | research agent | Use `templates/research-agent.md`; write cited evidence; replan cleanly |
| Implementation choice within approved intent | phase planner | Decide, add `D-###`, and finish the plan |
| Material product/scope/UX/acceptance trade-off | human via `grill-me` | Ask one question at a time with a recommendation |
| Permission, credentials, destructive or irreversible action | human authority gate | Ask directly; do not turn it into a long interview |

Do not invoke `grill-me` for failing tests, code uncertainty, naming that the planner owns,
researchable facts, or every routine phase boundary.

## Installed skill path

If `grill-me` is installed and callable, invoke it with:

- the exact unresolved question;
- relevant `D-###` decisions and non-goals;
- the code/document paths already inspected;
- the trade-off the planner could not settle;
- an instruction to ask one question at a time and recommend an answer.

Do not expose the full journal or unrelated plan history.

Some distributions package `grill-me` only as an alias for a separate `grilling` skill. Confirm
the invoked skill can actually start its interview primitive. If the alias target is missing or
skill-to-skill invocation fails, treat `grill-me` as unavailable and use the fallback immediately;
do not block the run on installing a dependency.

## Fallback when grill-me is unavailable

Before invoking the installed skill or this fallback, write `blockers/B-###.md` and atomically set
`STATE: AWAITING_HUMAN_DECISION`, `NEXT_ACTION: ASK_HUMAN blocker=<path>`, and the resume action in
the blocker. A crash must not erase the question or what follows the answer.

Run this protocol in the main human conversation:

1. State the single unresolved decision and why it changes the outcome.
2. Give the recommended answer first, with one trade-off sentence.
3. Give at most two alternatives.
4. Ask one question and wait.
5. Inspect the repository instead of asking anything answerable from files.
6. Stop when the decision is clear enough to write one unambiguous `D-###` statement.

After the answer:

1. copy the human answer verbatim into the blocker artifact;
2. append the intervention to `journal.md`;
3. set `STATE: PLANNING` and name that blocker as the repair planner's `SOURCE`;
4. discard the blocked planner and spawn a fresh one;
5. let that planner write the proposed `D-###`; promote it only after plan review says `ship`.

Never hand the human answer directly to an executor.
