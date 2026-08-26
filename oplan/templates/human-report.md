# Human phase reports

> The harness prints these from capped role reports and verified gate results. Append them to
> `briefing.md`. Do not expose full plans, diffs, logs, or internal agent vocabulary.

Every line in these blocks must lead with what happened and why it matters in ordinary words.
Run-internal vocabulary — leaf IDs, D-numbers, seals, revisions — may follow but never leads.

The phase briefing below and the phase report below are the only phase-boundary writes of
`briefing.md` and the only points at which `STATUS.md` is rewritten: both are
written at phase boundaries only.

## Before a phase

```text
=== PHASE <N> — PLAN ===
WHAT THIS ADDS: <1-2 lines>
WHY NOW: <one line>
STEPS:
  - <what happens> — because <why>
DONE WHEN: <phase acceptance in ordinary words>
BIGGEST RISK: <risk and how it will be noticed>
DEPTH: <fast|standard|paranoid> — <one line on what that buys and costs>
CHANGED SINCE LAST TIME: <what changed from the last presentation and why — or nothing>
MORE DETAIL: ask for any phase or leaf and I will explain it from the written records
MODE: continuing automatically | waiting for your approval of this plan | waiting for your decision because <reason>
=== END PLAN ===
```

In autonomous mode, print and continue. Never end the turn merely because a phase plan was shown.
Under `autonomy: interactive` this plan block is a wait: print it, persist the checkpoint blocker,
and stop until the human answers.

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

## When a phase's evidence changes the plan

```text
=== PLAN CHANGE — PHASE <N> ===
WHAT CHANGED: <one or two lines in ordinary words>
WHY: <the evidence that forced it>
WHAT IT AFFECTS: <phases, deliverables, or constraints>
YOUR OPTIONS: approve | ask for more detail | ask for a different approach
=== END PLAN CHANGE ===
```

Under `autonomy: full` this block is printed and the run continues.
