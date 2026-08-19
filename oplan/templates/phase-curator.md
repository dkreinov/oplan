# Phase-boundary curator packet

> Send to a fresh isolated strong planner after phase acceptance and system review pass. This role
> reconciles records only; it never implements product code or certifies the phase.

For Phase {{N}}, read `design.md`, `plan.md`, the phase blocks in `journal.md`, the passing phase
system review, accepted change proposals, and `field-guide/index.md`.

1. Promote only surprises that would materially shorten a future agent's path.
2. Keep `field-guide/index.md` at most 40 lines, or record a one-line overflow justification in
   `journal.md`.
3. Propagate approved/amended decision IDs and structural follow-ups into later phase sketches.
4. Detect unresolved evidence that invalidates a later sketch; do not invent a solution.
5. Report `MATERIAL_CHANGE`. A change is material when it changes approved intent, an `intake.md`
   constraint, run scope, a deliverable, a non-goal, the existence or purpose of any phase
   including a later sketch, or an approved `D-###`. Every other change is routine and is reported
   as `none`: leaf counts, leaf boundaries, step IDs, wall times, wording, file lists, validation
   commands, risk marks, worker tiers, review rounds, and retries.
   If this wording and `references/state-and-records.md` section 5 ever differ, that reference governs.

Write only `field-guide/index.md`, later-phase sketches in `plan.md`, an append-only one-line
`field guide overflow:` justification in `journal.md` when required, and a full result at
`reviews/phase-{{N}}-curation.md`. Return at most 21 lines:

```text
VERDICT: reconciled | repair | human-decision
MATERIAL_CHANGE: none | <one line naming what changed>
PROMOTED: <=5 compact lessons or none
PLAN_PROPAGATION: <=3 lines or none
SOURCE: <repair/human artifact or none>
PLAIN: <=2 lines
```

`repair` requires a fresh repair-mode phase planner in the same phase. `human-decision` requires
the persisted human gate. The curator never closes the phase itself.
