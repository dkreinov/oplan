# Plan reviewer packet

> Send this to a fresh strong reviewer. Give artifact paths, not a main-thread summary.

Review Phase {{N}} before any executor runs. You did not write the plan. Read:

- the active `{{phase_control}}` named by `phase-state.md`
- `{{workspace}}/design.md`
- `{{workspace}}/intake.md` — recorded approved intent whose `C-#` constraints rank
  with approved decisions
- Phase {{N}} in `{{workspace}}/plan.md`
- only the leaf controls in the active phase control's queue
- only the packets named by those leaf controls
- `{{workspace}}/field-guide/index.md`
- relevant code only where a packet makes a factual claim

Attack these failure classes:

1. a worker must guess a design choice;
2. two leaves can decide the same question or interpret a decision ID differently;
3. a packet omits a required file, contract, dependency, non-goal, or risk;
4. validation cannot mechanically prove the leaf goal;
5. leaf order is wrong or hidden dependencies exist;
6. the task tree is too coarse for isolated inexpensive workers;
7. phase acceptance does not test the phase goal;
8. the plan grows duplicate concepts, megafiles, or unnecessary abstractions;
9. the plan changes approved intent without a recorded human decision.
10. a packet and its control record disagree, a write set overlaps a protected baseline path,
    the phase control queue/order/held-out acceptance does not match the reviewed plan, or an
    evidence control's `run` commands could write a product file or a workspace record.
11. a phase or leaf spends effort on something the recorded intent already excludes:
    no phase or leaf may spend effort on anything `intake.md` records as a non-goal or a don't-care.
    Read `{{workspace}}/intake.md`, check every phase and every leaf against its recorded `C-#`
    constraints, and confirm that every phase's stated purpose, including a later sketch, traces
    to `request.md`, `intake.md`, or an approved decision. Confident, internally consistent
    over-scoping into what the human recorded as indifference is an `intent` finding, not a note.
    The pre-run scope grill is not optional, so
    a workspace with no `intake.md` is itself an `intent` finding.
12. a packet orders an edit that a sealed gate pins — its own frozen validation, a held-out phase
    or overall acceptance instrument, or an existing test asserts the exact content, key set, or
    property the packet orders changed. That is an impossible leaf: its executor will stop, and
    the repair cycle costs more than this check. An edit to an artifact a held-out gate has
    already armed on — append-never: a gate pins one of its properties — is the same finding, even when the
    edit looks harmless — ask not only "can this change a number?" but "can this change any
    property the gate pins, such as ordering or timestamps?"

## Materiality

A finding may block — `fix-first`, `mismatch`, or `repair` — ONLY when you name both (a)
a concrete trigger scenario reachable in this run's intended use, and (b) why the defect's expected
cost exceeds the cost of one fix cycle. Every other finding goes under `NOTES` as a non-blocking
recorded note. Style, completeness, and hypothetical findings never block on their own.

Write the full review to the versioned path named by the active phase control (for example,
`{{workspace}}/reviews/phase-{{N}}-plan-r1.md`). The review FILE itself must end with the same
machine-readable verdict block shown below — the seal step mechanically greps the artifact for
`VERDICT: ship`, so a verdict that exists only in your chat report blocks the run. Then return
at most 28 lines:

```text
VERDICT: ship | fix-first | human-decision
FINDINGS:
  - [decision|boundary|validation|order|decomposition|acceptance|structure|intent] <step> — <issue>
  - none
NOTES: <=3 non-blocking observations or none
BLOCKERS:
  - [repo_fact|product|authority] <question>
  - none
BLOCKER_PATH: <versioned blockers/ path written before return, or none>
PLAIN: <=2 lines describing what you checked and found
```

Use `human-decision` only for a material product/scope/UX or authority question. Implementation
choices are planner defects, not human questions.

When returning any blocker, write its exact question, classification, checked evidence,
recommended next owner, and resume action to `BLOCKER_PATH`. Do not leave it only in the report.
