# Human phase reports

> The harness prints these from capped role reports and verified gate results. Append them to
> `briefing.md`. Do not expose full plans, diffs, logs, or internal agent vocabulary.

## Before a phase

```text
=== PHASE <N> — PLAN ===
WHAT THIS ADDS: <1-2 lines>
WHY NOW: <one line>
STEPS:
  - <what happens> — because <why>
DONE WHEN: <phase acceptance in ordinary words>
BIGGEST RISK: <risk and how it will be noticed>
MODE: continuing automatically | waiting for your decision because <reason>
=== END PLAN ===
```

In autonomous mode, print and continue. Never end the turn merely because a phase plan was shown.

## After a phase

```text
=== PHASE <N> — REPORT ===
PLANNED: <one line>
BUILT: <one bullet per accepted leaf>
DISCOVERED: <surprises that affect understanding or later work>
WENT WRONG: <failures, cause, retries/escalations, and resolution—or nothing>
DESIGN CHANGES: <D-### additions/amendments—or none>
STRUCTURAL FLAGS: <megafiles/core changes/duplication and disposition—or none>
CHECKED: <phase acceptance and system review results>
COST/TIME: <verified values or unavailable>
RISKS LEFT: <or none>
NEXT: <next phase and immediate NEXT_ACTION, or complete>
NEED FROM YOU: <decision/action or nothing>
=== END REPORT ===
```

State failures as plainly as successes. `DISCOVERED` must report new information, not restate
completed work. If `NEED FROM YOU` is `nothing`, continue immediately.
