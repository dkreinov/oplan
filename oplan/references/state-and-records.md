# State, record, and transition contracts

## 1. Workspace and Git preflight

Before creating the run workspace, capture Git status so oplan's own records are never mistaken
for pre-existing user changes. Establish the baseline commit as described below, then create this
structure before the first planner runs:

```text
.oplan/<run-name>/
  request.md                 # immutable verbatim user brief
  baseline.md                # verified Git base and protected dirty paths
  model-bindings.md          # role bindings and ordered worker_ladder
  design.md                  # intent and decision registry
  plan.md                    # phase tree and held-out phase acceptance
  phase-state.md             # small control record
  journal.md                 # append-only technical history
  STATUS.md                  # current snapshot only
  briefing.md                # append-only human story
  field-guide/index.md       # curated cross-phase surprises
  control/                   # small JSON leaf controls the harness may read
  packets/                   # executor specifications
  seals/                     # immutable reviewed SHA-256 files
  blockers/ research/ attempts/ logs/ reviews/
```

If `oplan` may disappear, also copy the active skill, templates, references, and scripts into the
workspace. `request.md` is the user's task, constraints, and referenced input paths copied
verbatim. Planning interpretation belongs in `design.md`.

Before planning, run a Git preflight:

1. Require a Git worktree. If the repository is empty and unborn, create an explicit empty
   `chore(oplan): establish baseline` commit. If an unborn repository already contains files,
   persist an `AWAITING_HUMAN_DECISION` blocker before asking permission to baseline them.
2. Resolve `git rev-parse HEAD` to a full commit SHA and record it in `baseline.md` and
   `LAST_ACCEPTED`. Record the SHA-256 of immutable `request.md`. Use exact machine-readable lines
   `commit: <SHA>`, `request_sha256: <SHA-256>`, and `protected_paths: ["path", ...]`.
   Never store symbolic `HEAD` or a missing object.
3. Record every path captured before workspace creation that was dirty, staged, or untracked as a
   protected repo-relative path. Exclude only the new `.oplan/<run-name>/` workspace itself. A planner may
   read it but no leaf may touch it. If the task needs one, persist a human decision blocker; do
   not stash, reset, or commit unrelated work.
4. Write concrete role bindings and the ordered worker ladder to `model-bindings.md`.
5. Record `run_modes:` in `baseline.md`. The default is `autonomous` with automatic leaf commits.
   Record a supervised value (`pause-between-phases` or `step-by-step`) only when the user's
   request explicitly asked for it; never infer supervision. Under a supervised mode, the pause
   point persists a checkpoint blocker and enters `AWAITING_HUMAN_DECISION` instead of continuing:
   `pause-between-phases` pauses at each non-final `CLOSE_PHASE`, `step-by-step` pauses after each
   `ACCEPT_LEAF`.
6. Run `validate_run.py` before spawning the first planner.

## 2. Control state

The harness rewrites `phase-state.md` atomically before every external action. Keep it at most 30
lines and use exactly these keys:

```text
RUN: <name>
STATE: INITIALIZING | PLANNING | REVIEWING_PLAN | EXECUTING | VALIDATING |
       REVIEWING_RESULT | CLOSING_PHASE | COMPLETE | BLOCKED | AWAITING_HUMAN_DECISION
PHASE: <N> "<name>"
PHASE_CONTROL: <control/phase-N[-rK].json, or none while initializing/planning>
LEAF: <step-id or none>
NEXT_ACTION: <legal action plus all arguments, or none only when COMPLETE/BLOCKED>
ACTIVE_AGENT: <role + task id, or none>
LAST_ACCEPTED: <full commit SHA>
ACCEPTED_THIS_PHASE: <step ids or none>
DECISIONS_IN_FORCE: <approved D-### list or none>
OPEN_BLOCKER: <classification + artifact path, or none>
RETRY: <current attempt count>
TERMINAL_REASON: <reason only for COMPLETE/BLOCKED/AWAITING_HUMAN_DECISION; otherwise none>
```

Legal `NEXT_ACTION` verbs by state:

| State | Legal verbs |
|---|---|
| `INITIALIZING` | `INITIALIZE_BASELINE` |
| `PLANNING` | `SPAWN_PHASE_PLANNER`, `SPAWN_RESEARCH_AGENT` |
| `REVIEWING_PLAN` | `SPAWN_PLAN_REVIEWER`, `SEAL_PHASE` |
| `EXECUTING` | `REPORT_PHASE_PLAN`, `SPAWN_EXECUTOR`, `REVERT_CANDIDATE` |
| `VALIDATING` | `RUN_VALIDATION` |
| `REVIEWING_RESULT` | `SPAWN_SPEC_AUDITOR`, `COMPLETE_EVIDENCE`, `SPAWN_SYSTEM_REVIEWER`, `ACCEPT_LEAF` |
| `CLOSING_PHASE` | `RUN_PHASE_ACCEPTANCE`, `RUN_OVERALL_ACCEPTANCE`, `SPAWN_SYSTEM_REVIEWER`, `SPAWN_PHASE_CURATOR`, `CLOSE_PHASE` |
| `AWAITING_HUMAN_DECISION` | `ASK_HUMAN` |
| `COMPLETE`, `BLOCKED` | `none` |

Every action carries its artifact path, phase, leaf/control, scope, mode, source, and attempt when
applicable. Examples:

```text
NEXT_ACTION: SPAWN_PHASE_PLANNER phase=2 mode=repair source=reviews/phase-2-plan-r1.md
NEXT_ACTION: SPAWN_EXECUTOR control=control/2.1.json
NEXT_ACTION: RUN_VALIDATION control=control/2.1.json attempt=1
NEXT_ACTION: SPAWN_SYSTEM_REVIEWER scope=phase-2 source=reviews/phase-2-acceptance.md
NEXT_ACTION: ASK_HUMAN blocker=blockers/B-003.md
```

Write the next state before printing a human report. The control record, never chat history, tells
a replacement harness what to do.

## 3. Decision records

Use stable decision IDs in `design.md`:

```text
### D-001 — <short name>
Status: proposed | approved | amended | superseded
Decision: <one unambiguous statement>
Why: <reason/trade-off>
Decided by: planner | human answer recorded at <blocker path>
Evidence: <source path>
Affected phases/packets: <list>
Supersedes: <D-### or none>
```

The planner writes new decisions as `proposed` before plan review. On `ship`, the harness runs the
documented `--seal` command, which mechanically promotes the phase's referenced proposals to
`approved` and updates `DECISIONS_IN_FORCE`; it does not reinterpret them. Never silently edit an approved decision.
Add an amendment/successor and replan every unaccepted descendant that depends on it.

## 4. Plan, control records, and seals

`plan.md` contains the overall goal, phase sketches, current task tree, held-out phase acceptance,
packet/control paths, risks, dependencies, non-goals, and decision IDs.

For every packet, the planner also writes `control/<step-id>.json`:

```json
{
  "step": "2.1",
  "phase": 2,
  "packet": "packets/2.1.md",
  "write_set": ["src/example.py", "tests/test_example.py"],
  "validation": "python -m pytest tests/test_example.py",
  "risk": "low",
  "decisions": ["D-001"],
  "wall_time_minutes": 15
}
```

`wall_time_minutes` is a parent-enforced cancellation boundary, never a promise the worker must
estimate or meet; the packet tells the worker not to rush or self-abort. When an executor is still
running at the boundary, the harness cancels it and treats the attempt exactly like an executor
`failed` result in the transition table.

`packet` is workspace-relative; every `write_set` path is Git-root-relative. This is the only leaf artifact the harness reads. It contains exactly what the harness needs to
validate, scope a revert/commit, route risk, and update decision metrics. It must contain no phase
acceptance, rationale, code, or feature-planning prose.

The planner also writes one active versioned phase control and the harness records its path in
`PHASE_CONTROL`:

```json
{
  "phase": 2,
  "revision": 1,
  "name": "integrate storage",
  "queue": ["control/2.1.json", "control/2.2.json"],
  "acceptance": ["python -m pytest tests/integration"],
  "overall_acceptance": [],
  "next_phase": {"number": 3, "name": "finish migration"},
  "plan_review": "reviews/phase-2-plan-r1.md"
}
```

The queue is the dispatch order and contains each active leaf exactly once. Acceptance commands
stay out of leaf packets and leaf controls. `next_phase` is either the consecutive phase identity
or `null`. A final phase (`next_phase: null`) must contain nonempty held-out
`overall_acceptance`; non-final phases use an empty list. A post-seal repair writes a new
phase-control revision and new review path; it never overwrites the sealed phase control. All
leaf, phase, and overall commands run from the Git worktree root.

After the active plan review artifact says `VERDICT: ship`, set
`NEXT_ACTION: SEAL_PHASE phase=N source=<PHASE_CONTROL>` and run:

```text
python3 <skill-dir>/scripts/validate_run.py <workspace> --phase N --seal
```

This writes immutable `seals/<step-id>.sha256` files covering both packet and control record, plus
a seal for the active phase control and its review.
Before dispatch, retry, audit, validation, and commit, rerun with `--require-sealed`. A mismatch is
`BLOCKED`; never regenerate a changed seal. A repair after sealing uses a new versioned step ID.

## 5. Total verdict transitions

Follow this table mechanically. “Revert” means restore only the control record's write set to
`LAST_ACCEPTED`, removing newly created paths, while preserving every protected baseline path.
Before every fresh role starts, set state/`ACTIVE_AGENT`. Persist its capped return atomically to
`attempts/<role>-<scope>-a<N>.report` before interpreting it or advancing state. For an executor,
the guard snapshot explicitly excludes that one expected report path so it can be persisted before
the comparison without masking any other workspace write. Attempt numbers,
mismatch counts, and malformed-report counts are derived from these immutable versioned artifacts;
never keep them only in chat. `RETRY` mirrors the current action's attempt count.

| Input | Candidate treatment | Next state and action |
|---|---|---|
| planner `planned` | none | install returned `PHASE_CONTROL`; `REVIEWING_PLAN`; `SPAWN_PLAN_REVIEWER phase=N source=<PHASE_CONTROL>` |
| workspace/control validation fail | revert any unaccepted candidate | persist validation evidence, then `BLOCKED` |
| planner `record-gap` | none | persist invalid-record evidence, then `BLOCKED` |
| planner `blocked/repo_fact` | none | require returned `BLOCKER_PATH`; `PLANNING`; `SPAWN_RESEARCH_AGENT blocker=<path> attempt=1` |
| planner `blocked/product|authority` | none | persist blocker, then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>` |
| plan review `ship` | none | `REVIEWING_PLAN`; `SEAL_PHASE phase=N source=<PHASE_CONTROL>` |
| seal success | immutable reviewed artifacts | `EXECUTING`; `REPORT_PHASE_PLAN phase=N source=<PHASE_CONTROL>` |
| phase-plan report appended/printed | none | `EXECUTING`; `SPAWN_EXECUTOR control=<first queued control>` |
| seal failure/mismatch | revert any unaccepted candidate | `BLOCKED` |
| plan review `fix-first` | none | `PLANNING`; fresh planner `mode=repair source=<full review path>` |
| plan review `human-decision` | none | persist blocker, then human gate |
| executor `done` | retain candidate | `VALIDATING`; `RUN_VALIDATION control=<path> attempt=N` |
| validation pass | retain candidate | `REVIEWING_RESULT`; `SPAWN_SPEC_AUDITOR control=<path>` |
| executor exceeds `wall_time_minutes` | cancel the agent, revert | count as executor `failed` at the current attempt |
| executor `failed` or validation fail, attempts <2 | revert | `EXECUTING`; fresh executor at same tier with failing-log path |
| second failure | revert | `EXECUTING`; fresh executor at next recorded tier |
| top-tier failure | revert | `BLOCKED`; `NEXT_ACTION: none` |
| first malformed role report | revert executor candidate; otherwise none | redispatch the same role fresh once from original artifacts |
| second malformed role report | revert executor candidate; otherwise none | `BLOCKED`; `NEXT_ACTION: none` |
| executor `stopped-with-question` | verify/revert all write-set changes | `PLANNING`; fresh planner `mode=repair source=<question artifact>` |
| spec audit `match/high` | retain | high risk → leaf system review; low risk → `ACCEPT_LEAF` |
| spec audit `match/low` | retain | `REVIEWING_RESULT`; `COMPLETE_EVIDENCE control=<path> review=<path>` using fresh evidence reviewer |
| evidence completion becomes high | retain | continue as `match/high` |
| evidence remains low | revert candidate | `BLOCKED` |
| spec audit first `mismatch` | revert | fresh executor with original sealed packet; increment mismatch count |
| spec audit second `mismatch` | revert | `BLOCKED` |
| high-risk leaf system `pass` | retain | `REVIEWING_RESULT`; `ACCEPT_LEAF control=<path>` |
| high-risk leaf system `repair` | revert | `PLANNING`; fresh planner `mode=repair source=<system review>` |
| any review `human-decision` | revert unaccepted candidate | persist blocker, then human gate |
| phase acceptance fail | accepted commits remain | `PLANNING`; fresh planner `mode=repair source=<acceptance log>` |
| all queued leaves accepted | accepted commits remain | `CLOSING_PHASE`; `RUN_PHASE_ACCEPTANCE phase=N source=<PHASE_CONTROL>` |
| phase acceptance pass | accepted commits remain | `CLOSING_PHASE`; `SPAWN_SYSTEM_REVIEWER scope=phase-N source=<acceptance review>` |
| phase system `repair` | accepted commits remain | `PLANNING`; fresh planner `mode=repair source=<system review>` |
| phase system `human-decision` | accepted commits remain | persist blocker, then human gate |
| phase system `pass` | none | `CLOSING_PHASE`; `SPAWN_PHASE_CURATOR phase=N source=<system review>` |
| curator `reconciled`, `next_phase` present | none | `CLOSING_PHASE`; `CLOSE_PHASE phase=N` then install next planning action |
| curator `reconciled`, final phase | none | `CLOSING_PHASE`; `RUN_OVERALL_ACCEPTANCE phase=N source=<PHASE_CONTROL>` |
| curator `repair` | accepted commits remain | `PLANNING`; fresh planner `mode=repair source=<curation review>` |
| curator `human-decision` | accepted commits remain | persist blocker, then human gate |
| research `evidence` | none | `PLANNING`; fresh planner `mode=repair source=<evidence path>` |
| research first `not-found` | none | fresh research agent at next tier, attempt 2 |
| research second `not-found` | none | `BLOCKED` |
| research `authority` | none | persist blocker, then human gate |
| persisted human answer | revert unaccepted candidate if any | `PLANNING`; fresh planner `mode=repair source=<blocker path>` |
| overall acceptance pass | none | `CLOSING_PHASE`; `CLOSE_PHASE phase=N`, print final phase report, then `COMPLETE` |
| overall acceptance fail | accepted commits remain | `PLANNING`; fresh planner `mode=repair source=<overall log>` |

`ACCEPT_LEAF` verifies the seal, stages only `write_set`, and commits with path-restricted Git
semantics (`git commit --only -- <write_set>`) so unrelated pre-staged changes cannot enter. Verify
the commit diff contains no path outside the intended write set, record its full SHA as `LAST_ACCEPTED`,
append the journal, and advance to the next leaf or phase gate. At phase
close, write the report and, if another phase exists, atomically set `STATE: PLANNING` and
`PHASE_CONTROL: none` and `NEXT_ACTION: SPAWN_PHASE_PLANNER phase=N+1 mode=new source=none` before printing. The final phase
becomes `COMPLETE` only after curation and overall acceptance.

## 6. Human, research, and recovery records

Before any human question, write `blockers/B-###.md` with classification, exact question,
recommendation, alternatives, evidence already checked, answer field, and resume action; then
atomically enter `AWAITING_HUMAN_DECISION`. Ask only after the state is durable. On reply, copy the
answer verbatim into that file and spawn a fresh repair planner with it as `SOURCE`; never pass an
oral answer to an executor.

Append one compact journal block per accepted leaf with packet/control/seal paths, worker tier,
validation, `did`, `failure_cause`, surprises, deviations, structural flags, decisions, audit and
system verdicts, retries/escalation, verified cost or `unavailable`, commit, and timestamp. At
phase close append acceptance, curation, interventions, cost by role, and harness context size or
`unavailable`. `STATUS.md` is current state only; `briefing.md` is append-only history.

On resume, read `phase-state.md` first, verify `LAST_ACCEPTED` and all relevant seals, explain any
in-flight candidate from its control record, then perform `NEXT_ACTION`. If state is inconsistent,
set `BLOCKED` with the validation evidence. An explicitly initiated recovery may then use a fresh
reconstruction reviewer over commits plus record paths. Never ask the human to repeat a decision
already present in the records.

For an executor question, the harness first runs the undeclared-write guard/revert, then copies
the report path, exact `QUESTION`, affected step, and repair resume action into
`blockers/Q-<step>-a<N>.md`. Repository-fact blocker artifacts use the same fields plus inspected
sources and are written by the planner/reviewer that reports them.

Immediately before dispatching an executor, run
`worktree_guard.py capture <git-root> <attempt-snapshot> <expected-report-relative-path>` after the
state update. Immediately after its capped return, atomically persist only that excluded report,
then run `worktree_guard.py check <git-root> <snapshot> <control> <workspace>` before interpreting
the verdict or writing anything else. Any changed path outside the
control write set, including `.oplan` or a pre-existing dirty path, is a scope violation: preserve
the guard evidence, revert the declared candidate, and set `BLOCKED`. This guard precedes
validation, audit, retry, and commit; a scoped diff alone is not isolation.
