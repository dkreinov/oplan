# Model and harness policy

Bind roles by capability tier instead of hardcoding transient model names, and bind each role to an
effort as well as a tier. A binding is a `<model>/<effort>` pair, never a model alone: one step down
in reasoning effort costs roughly 2 points of task success at about half the cost, and two steps down
roughly 8 points at a quarter — the same order of effect as a model change. A run that records only
model names has left half of its capability policy unstated. Write both parts wherever a binding is
written, and pass both at every dispatch.
In a binding, `default` means the effort the host session inherited — not a vendor default, and not
the middle of the scale.

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

## Starting effort by role

Recorded defaults, not settled facts: a run may depart from them by writing different pairs in its
`model-bindings.md` and recording why. The rule behind the column is that workers may be cheapened
and inspectors may not.

| Role | Starting effort | Why |
|---|---|---|
| Main harness | the host session's own effort | it follows tools and state; it does not reason out a plan |
| Phase planner | high | decomposition and material trade-offs are the run's scarcest reasoning |
| Plan reviewer | default | the cheapest point at which a defect can still be intercepted |
| Executor, mechanical leaf | medium | a ~2-point penalty against a ~5x break-even margin |
| Executor, `worker_tier: strong` leaf | default | its product is judged by a human, not by a gate |
| Spec auditor | default | its recall below default is unmeasured; see the recall trap below |
| System reviewer | high, and the strongest effort available at a phase gate | deep multi-step tracing is where effort matters most, and this is the lens that has caught what every cheaper gate passed |
| Phase curator | medium | it reconciles recorded evidence; it does not originate design |
| Research agent | low for a quotable-span lookup, medium otherwise | a hard question is covered by escalation, not by effort |
| Evidence reviewer | default | completing one named gap after a low-confidence audit is a judgment call |

Ladders are ladders of pairs: `worker_ladder` and `research_ladder` record a `<model>/<effort>` value
per rung, cheapest reliable rung first.

## Where effort may be cut

Cut effort where a miss is caught by a later gate; never where a miss IS the failure. A worker's
mistake meets a frozen validation, an independent audit, and a system review, so a small drop in its
first-try rate costs one cheap fix cycle. An inspector's miss is the silent kind: nothing downstream
looks again, and the defect is found by a human reading shipped output, if it is found at all.

Before cutting any role's effort, compute the break-even — how much worse that role's failure rate
would have to get before the extra failures cost more than the cut saves — and take the cut only when
that number sits far above the measured effort penalty. Measured here: the executor cut clears by
about 5x, break-even near a 10-point failure increase against a ~2-point penalty, while the spec
auditor's break-even is near 3 points, below the penalty itself, so the identical cut is negative
expected value there.

Do not justify an inspector's effort with a benchmark accuracy delta. Accuracy is not recall: where
real defects are rare, a rubber stamp scores in the nineties. On this skill's own audit corpus one
audit in fourteen carried a real catch, so an inspector that always returned `match` would have
agreed with the record 93% of the time. Only a seeded defect measures the catch.

The cheapest tier is admissible only inside a leaf class whose validation is fully mechanical, and
only once that class is defined in writing. On simple reasoning the cheapest tier scores around 63%
where the strongest scores 92% at roughly a tenth of the price, and every ruling this skill asks of
an inspector — does this output match this packet, is this finding material — sits above that line.
Define the mechanical class first, pilot the cheap tier inside it, measure, and only then bind it.

Raising a role's effort without raising its wall-time bound weakens the role the raise was meant to
strengthen: the longer trace runs into the cancellation boundary and the harness redispatches the
role with narrowed scope. The system reviewer's bound is 45 minutes for that reason (SKILL.md
section 10).

An effort-only bump is not a rung of the retry ladder. The rungs are the values `worker_ladder`
records. Every worker failure observed in this skill's runs so far was a packet defect — a question
the packet did not answer — and no amount of effort repairs a defective packet: that failure routes
to a repair planner, not to a bigger worker.

Exception to the inexpensive-executor rule: a leaf whose product IS creative or natural-language
content (prose, narration, UX copy, translation — especially non-English) must run on a strong
tier named in its packet (`worker_tier: strong`). Small models produce fluent-looking text with
invented words and broken grammar in low-resource languages, and neither frozen mechanical
validation nor an inexpensive auditor can detect it; the defect surfaces only when a human reads
the output. Measured example: a cheap-tier worker writing Hebrew narration passed every
mechanical gate and a cheap spec audit while containing non-words.

Planners, reviewers, researchers, curators, and executors require a genuinely new session/process
with conversation inheritance disabled. A prompt that says “ignore earlier chat” is not isolation.
If the host cannot provide a clean context, set `BLOCKED`; do not silently weaken this rule.

At initialization, write nonempty concrete `<model>/<effort>` bindings to `model-bindings.md` for
`main_harness`, `phase_planner`, `plan_reviewer`, `executor`, `spec_auditor`, `system_reviewer`,
`phase_curator`, `research_agent`, and `evidence_reviewer`. Also write ordered `worker_ladder` and
`research_ladder` values from cheapest reliable tier to strongest allowed tier, each rung a pair too.
“Next stronger” and “top tier” always refer to the relevant recorded order; never invent a tier
during a retry.

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

Change a binding — model or effort — only at a run boundary or as a journaled amendment at a leaf
boundary, and never in the middle of a comparison. Keep role prompts, models, and efforts fixed
across the leaves being compared, so the variable under measurement is the only one that moved. A
mid-run change makes the run a mixture and disqualifies it as a comparison arm: the run that added
this section amended its own bindings twice between leaves, so its leaves executed at three different
settings and none of its per-role first-try numbers can be read as evidence for any one of them. When
an amendment is worth its cost anyway, take it at a leaf boundary, journal the change and its reason,
and record that every leaf before it belongs to the previous arm.

## What the next runs must measure

The starting efforts above are a hypothesis. Three measurements can falsify them, and a run that
records them makes the next binding change evidence rather than taste:

1. Per-role first-try rate at the recorded efforts, against the journal baselines of runs that
   executed at inherited effort (executor 10/13 and 3/6 in the two recorded runs). A worker whose
   rate falls materially below its baseline retires that worker's cut.
2. Auditor recall: seed exactly one one-sentence deviation from the packet into one candidate per
   phase, and record whether that phase's spec audit named it. The baseline is 1/1 at the cheap tier
   at inherited effort. Accuracy over ordinary candidates measures nothing here; only the seeded
   deviation measures the catch.
3. System-review repairs per accepted leaf, and the wall time each review actually used against its
   45-minute bound. Repairs per leaf rising indicts the upstream cuts; wall time sitting at the bound
   indicts the bound.

This section is guidance for whoever reads the journal, not a step the harness executes. Making the
seeded deviation mandatory would need its own row in the transition table, specifying the seeding,
the disclosure, and the removal of the seed; that is deliberately out of scope here.
