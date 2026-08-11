# Plan reviewer packet

> Send this to a fresh strong reviewer. Give artifact paths, not a main-thread summary.

Review Phase {{N}} before any executor runs. You did not write the plan. Read:

- the active `{{phase_control}}` named by `phase-state.md`
- `{{workspace}}/design.md`
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
10. a packet and its control record disagree, a write set overlaps a protected baseline path, or
    the phase control queue/order/held-out acceptance does not match the reviewed plan.

Write the full review to the versioned path named by the active phase control (for example,
`{{workspace}}/reviews/phase-{{N}}-plan-r1.md`) and return at most 25 lines:

```text
VERDICT: ship | fix-first | human-decision
FINDINGS:
  - [decision|boundary|validation|order|decomposition|acceptance|structure|intent] <step> — <issue>
  - none
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
