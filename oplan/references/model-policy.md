# Model and harness policy

Bind roles by capability tier instead of hardcoding transient model names.

| Role | Tier | Principle |
|---|---|---|
| Main harness | coordinator | Needs reliable tool/state following, not feature-design depth |
| Phase planner | strongest justified planner | Original decomposition and material trade-offs are scarce frontier moments |
| Plan reviewer | strong independent checker | Catch ambiguity before it multiplies into worker cost |
| Executor | inexpensive reliable worker | Follow one complete packet; never make design decisions |
| Spec auditor | inexpensive independent checker | Compare packet and scoped output narrowly |
| System reviewer | strong checker for integration | Inspect cross-cutting behavior and accumulated structure |
| Phase curator | strongest justified planner | Reconcile phase evidence and propagate decisions without implementing |
| Research agent | inexpensive, escalate once if needed | Answer one repository/documentation fact and cite evidence |
| Evidence reviewer | inexpensive independent checker | Complete one named gap after a low-confidence spec audit |

Planners, reviewers, researchers, curators, and executors require a genuinely new session/process
with conversation inheritance disabled. A prompt that says “ignore earlier chat” is not isolation.
If the host cannot provide a clean context, set `BLOCKED`; do not silently weaken this rule.

At initialization, write nonempty concrete bindings to `model-bindings.md` for `main_harness`,
`phase_planner`, `plan_reviewer`, `executor`, `spec_auditor`, `system_reviewer`, `phase_curator`,
`research_agent`, and `evidence_reviewer`. Also write ordered `worker_ladder` and
`research_ladder` values from cheapest reliable tier to strongest allowed tier. “Next stronger”
and “top tier” always refer to the relevant recorded order; never invent a tier during a retry.

Choose tiers from measured total-task behavior:

- planner cost;
- downstream worker tokens;
- first-pass rate and retries;
- escalations and human interventions;
- defects caught at later gates;
- total completed-task cost and elapsed time.

A stronger planner can use fewer planning tokens yet cause more worker activity, or the reverse.
Do not optimize one role in isolation. Commit count and raw token volume are not productivity
metrics; churn and conflicts may indicate thrashing.

Change a binding only at a version boundary and record the evidence. Keep role prompts and effort
fixed during a comparison so the model is the main changed variable.
