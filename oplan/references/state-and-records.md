# State, record, and transition contracts

## 1. Workspace and Git preflight

Before creating the run workspace, capture Git status so oplan's own records are never mistaken
for pre-existing user changes. Establish the baseline commit as described below, then create this
structure before the first planner runs:

```text
.oplan/<run-name>/
  request.md                 # immutable verbatim user brief
  intake.md                  # pre-run scope conversation and its constraints
  baseline.md                # verified Git base and protected dirty paths
  model-bindings.md          # role model/effort bindings and ordered worker_ladder
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
4. Write concrete role bindings to `model-bindings.md`, each a `<model>/<effort>` pair, plus the
   ordered worker and research ladders whose rungs are pairs too, cheapest reliable rung first:

   ```text
   main_harness: <model>/<effort>
   phase_planner: <model>/high
   executor: <model>/medium
   worker_ladder: <cheapest reliable model>/medium, <next stronger model>/default
   ```

   `references/model-policy.md` holds the per-role starting efforts and the rule for changing one.
5. Record `run_modes:` in `baseline.md`. The default is `autonomous` with automatic leaf commits.
   Record a supervised value (`pause-between-phases` or `step-by-step`) only when the user's
   request explicitly asked for it; never infer supervision. Under a supervised mode, the pause
   point persists a checkpoint blocker and enters `AWAITING_HUMAN_DECISION` instead of continuing:
   `pause-between-phases` pauses at each non-final `CLOSE_PHASE`, `step-by-step` pauses after each
   `ACCEPT_LEAF` and after each journaled evidence step. Also record `commit_mode:` in `baseline.md`. The default is `auto` — accepted
   leaves are committed. Record `none` only when the user's request explicitly forbids commits;
   never infer it. When `commit_mode: none`, initialize the cumulative accepted-state manifest
   before the first dispatch by running this command:

   `<python> <skill-dir>/scripts/worktree_guard.py init-accepted <git-root> <workspace>/attempts/accepted-state.json`
6. Record the depth intake in `baseline.md` with exactly one machine-readable
   `depth_profile: fast|standard|paranoid` line and exactly one
   `work_mode: engineering|experiment` line. Both are required and neither has a default when
   absent. The harness asks ONE question in a single message that names its recommendation, the
   reason for it, and what each level buys and costs in one or two lines each, and it accepts the
   user's answer verbatim. The recommendation rule is: `paranoid` for safety-critical,
   irreversible, security-sensitive, or shared-tooling work; `standard` for typical features,
   refactors, and migrations; `fast` for low blast radius, easy rollback, strong existing
   coverage, or throwaway work; `work_mode: experiment` when the task is measurement-driven, and
   `engineering` otherwise. When a task matches more than one of those rows, recommend the more
   thorough profile (`paranoid` over `standard` over `fast`). When the user cannot answer
   (autonomous restart or resume), the harness picks by applying that same recommendation rule
   including its tie-break, records the choice AND its rationale in `journal.md` and `baseline.md`,
   and proceeds; it never blocks the run on this question.
   Record the autonomy intake in `baseline.md` too, with exactly one machine-readable
   `autonomy: interactive|full` line, asked the same one-question-at-a-time way with
   `interactive` recommended. `interactive` means the harness presents the whole plan and waits for
   approval before the first executor, and again whenever a phase curator reports a material
   change; `full` means the agents decide and the run never waits for approval. When the user
   cannot answer, the harness records `interactive` with its rationale in `baseline.md` and
   `journal.md` and proceeds, and never infers `full`, so an unattended run parks at its first
   run-plan approval gate in `AWAITING_HUMAN_DECISION` with a persisted checkpoint blocker, which
   is durable, resumable, and loses no work (D-002).
   Rigor is proportional; core safety is not.
7. Hold the pre-run scope grill before spawning the first phase planner and write `intake.md`.
   Cover, asking only what `request.md` has not already answered, one question at a time, each with
   the harness's advice and a recommendation: what actually ships as the production deliverable,
   success criteria in the user's terms, explicit non-goals, irreversible or outward-facing actions
   expected, and the rough time or cost budget or the kill criteria. Use the installed `grill-me`
   skill when present, otherwise the bundled fallback style in `grill-gate.md`. When the user is
   unreachable at initialization, record the skip and its reason, treat `request.md` alone as
   intent, and flag the gap in the first briefing. `intake.md` uses this schema:

   ```text
   status: complete | skipped-user-unreachable
   grill_tool: grill-me | fallback | none
   reason: <one line, only when status is skipped-user-unreachable>

   ## Q&A (verbatim)

   ### Q1 — <topic>
   Asked: <the question as asked, including the recommendation given>
   Answer: <the user's words, verbatim>

   ## Constraints

   - C-1 — <one unambiguous statement> (from Q1)
   ```

   A `C-#` constraint ranks with an approved `D-###`. The phase planner reads `intake.md` as
   approved intent, no plan may contradict a constraint, and changing one is a design amendment
   routed through the human gate. `validate_run.py` requires `intake.md` to exist in every
   workspace and to carry exactly one `status:` line whose only legal values are `complete` and
   `skipped-user-unreachable`, so a skipped grill is recorded in the file and never by omitting
   it (D-016).
8. Run `validate_run.py` before spawning the first planner.

### 1.1 Depth profiles

`depth_profile` is normative for review depth and planning effort:

| Profile | Plan review | Spec audit | System review | Planning effort |
|---|---|---|---|---|
| `paranoid` | every revision, uncapped | every leaf | high-risk leaves and every phase gate | reviewers reproduce findings |
| `standard` | once per phase revision, hard cap of three unsuccessful rounds | every leaf | phase gate plus leaves the planner marked high risk for a material reason | planners do not prototype beyond what an undecided design choice needs |
| `fast` | no independent plan reviewer | high-risk leaves only | phase gate only | coarser leaves encouraged |

A run workspace whose `baseline.md` predates these two keys, or predates `autonomy`, is migrated by
appending the missing recorded lines to it, and that append is a harness action because run records
are harness-owned and no leaf `write_set` may name a path inside `.oplan/`. A workspace from a run
that finished before the approval gate existed records `autonomy: full`, because that is how it
actually executed (D-008). When a change in flight makes a new `baseline.md` key required, that
append is not left until each workspace happens to be touched again:
the harness appends the missing line to every existing workspace baseline it will validate,
before the first executor dispatch of the phase that introduces the key.
The same rule covers a newly required workspace RECORD: when a change in flight makes a record such
as `intake.md` required, the harness writes that record in every existing workspace it will
validate, before the first executor dispatch of the phase that introduces the requirement (D-017).
The section 5 acceptance self-heal rows are narrower on purpose — their input is a missing required
`baseline.md` key alone — so a missing required record that reaches acceptance is routed by the
unconditional acceptance-failure row to a repair planner.

These invariants hold in ALL profiles: the Git baseline and protected paths, sealed packets and
controls, the single product writer, guard capture/check/revert around every executor,
harness-rerun frozen validation, path-restricted commits, crash-safe records, and
`validate_run.py` gates. A profile never changes any of them.

Under `depth_profile: fast` the harness writes the plan-review record itself at the versioned
`reviews/phase-N-plan-rK.md` path named by the phase control, recording that no independent
reviewer ran under `fast`, what `validate_run.py` checked, and the plan summary, and ending with
the exact line `VERDICT: ship` so `SEAL_PHASE` is unchanged.

### 1.2 Work mode: experiment

Under `work_mode: experiment` the plan is a run matrix of arms and configurations with a
measurement plan, success metrics, and a stopping rule. Recording the outcome is the leaf's job:
a measurement that returns a negative or unexpected result is data, not a defect, so that leaf is
validated and accepted like any other, never reverted and never retried for its result.

The retry and revert ladder applies only to infrastructure faults — the job never ran, or its
artifacts are absent or corrupt. A measurement leaf's frozen validation is the existence and
integrity of its measured artifacts. Plan review checks the matrix and the method once rather than
each run. The next arm, or the stop, is decided between leaves by a fresh planner from the recorded
results and is recorded as a new `D-###` with its evidence path.
Here a measurement leaf is one whose control record carries `kind: measurement`; without it a leaf
is engineering, and section 5's `ACCEPT_LEAF` rows key on it and dispatch that planner `mode=repair`
with its recorded results as `source`, so a new arm enters the run as a new phase-control revision
`control/phase-N-rK.json` whose `queue` names the arm's leaf controls, installed by the `planner
planned` row, never overwriting the sealed control. On the stopping rule it writes no phase control,
no plan review, and the planner returns `stop-experiment`, routed to the phase gate: a `queue` may
not be empty, and a returned control re-opens a sealed review and re-dispatches an accepted leaf.
Engineering leaves inside an experiment run follow the depth profile normally.

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
| `PLANNING` | `SPAWN_PHASE_PLANNER`, `SPAWN_RESEARCH_AGENT`, `SPAWN_RESEARCH_AGENTS` |
| `REVIEWING_PLAN` | `SPAWN_PLAN_REVIEWER`, `SEAL_PHASE` |
| `EXECUTING` | `REPORT_PHASE_PLAN`, `SPAWN_EXECUTOR`, `RUN_EVIDENCE`, `REVERT_CANDIDATE` |
| `VALIDATING` | `RUN_VALIDATION` |
| `REVIEWING_RESULT` | `SPAWN_SPEC_AUDITOR`, `SPAWN_LEAF_REVIEWERS`, `COMPLETE_EVIDENCE`, `SPAWN_SYSTEM_REVIEWER`, `ACCEPT_LEAF` |
| `CLOSING_PHASE` | `RUN_PHASE_ACCEPTANCE`, `RUN_OVERALL_ACCEPTANCE`, `RUN_FINAL_GATE`, `SPAWN_SYSTEM_REVIEWER`, `SPAWN_PHASE_CURATOR`, `CLOSE_PHASE` |
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

Required action arguments (normative source: `ACTION_REQUIRED_KEYS` in `oplan/scripts/validate_run.py`):

| Verb | Required arguments |
|---|---|
| `INITIALIZE_BASELINE` | none |
| `SPAWN_PHASE_PLANNER` | `mode`, `phase`, `source` |
| `SPAWN_RESEARCH_AGENT` | `attempt`, `blocker` |
| `SPAWN_RESEARCH_AGENTS` | `attempt`, `blockers` |
| `SPAWN_PLAN_REVIEWER` | `phase`, `source` |
| `SEAL_PHASE` | `phase`, `source` |
| `REPORT_PHASE_PLAN` | `phase`, `source` |
| `SPAWN_EXECUTOR` | `control` |
| `RUN_EVIDENCE` | `control` |
| `REVERT_CANDIDATE` | `control` |
| `RUN_VALIDATION` | `attempt`, `control` |
| `SPAWN_SPEC_AUDITOR` | `control` |
| `SPAWN_LEAF_REVIEWERS` | `control` |
| `COMPLETE_EVIDENCE` | `control`, `review` |
| `SPAWN_SYSTEM_REVIEWER` | `scope`, `source` |
| `ACCEPT_LEAF` | `control` |
| `RUN_PHASE_ACCEPTANCE` | `phase`, `source` |
| `RUN_OVERALL_ACCEPTANCE` | `phase`, `source` |
| `RUN_FINAL_GATE` | `phase`, `source` |
| `SPAWN_PHASE_CURATOR` | `phase`, `source` |
| `CLOSE_PHASE` | `phase` |
| `ASK_HUMAN` | `blocker` |
| `none` | none |

Never hand-write `phase-state.md`. Update it with

`<python> <skill-dir>/scripts/set_state.py <workspace> KEY=VALUE [KEY=VALUE ...]`

which merges the updates into the current record, refuses to write anything on an illegal state,
verb, argument set, or terminal-reason mismatch, and writes atomically in canonical key order. Run
`validate_run.py` after every state transition, not only after artifact-writing roles.

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
`approved` and updates `DECISIONS_IN_FORCE`; it does not reinterpret them. That promotion covers
only decisions referenced by a sealed leaf control: a decision no leaf references — a
phase-structure decision, for example — stays `proposed` forever and can never legally enter
`DECISIONS_IN_FORCE`, so the planner must reference every decision from at least one leaf control
or record phase-shape reasoning in `plan.md` prose instead of a `D-###`. Never silently edit an approved decision.
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

`validation` stores the resolved `<python>` executable, never the placeholder (D-006).
A leaf control may also carry one optional `kind: measurement|engineering` field; it is absent by
default, an absent `kind` means `engineering`, and only `measurement` changes routing (section 5).
`validate_run.py` rejects any other value.

A queue may also contain **evidence controls** — read-only lookups against existing artifacts that
carry none of the leaf ceremony:

```json
{
  "step": "3.3",
  "phase": 3,
  "kind": "evidence",
  "run": ["grep lr_schedule runs/qat_probe_leg1_a1.log"],
  "wall_time_minutes": 5
}
```

An evidence control has exactly these keys — no packet, no write set, no validation, no risk, no
decisions — and its seal covers the control file alone. Its commands run from the Git worktree
root and must be read-only against product files and workspace records: anything that writes a
product file is a leaf, and the plan review checks evidence commands for this along with the rest
of the phase control. The harness executes evidence steps itself in queue order (section 5); no
executor, spec audit, guard capture, or commit is involved, and evidence steps never enter
`ACCEPTED_THIS_PHASE` or the accepted-state manifest. Under `depth_profile: fast`, where no
independent plan reviewer runs, the harness checks the read-only duty itself while writing the
plan-review record. During an evidence run `phase-state.md` records `LEAF: <step-id>`,
`ACTIVE_AGENT: none`, and `RETRY: 0`; each `run` command is an opaque top-level command under the
no-interpolation rule of SKILL.md section 9; on resume an interrupted evidence step re-runs from
scratch, truncating its log.

`wall_time_minutes` is a parent-enforced cancellation boundary, never a promise the worker must
estimate or meet; the packet tells the worker not to rush or self-abort. When an executor is still
running at the boundary, the harness cancels it and treats the attempt exactly like an executor
`failed` result in the transition table.

`packet` is workspace-relative; every `write_set` path is Git-root-relative. This is the only leaf artifact the harness reads. It contains exactly what the harness needs to
validate, scope a revert/commit, route risk, and update decision metrics. It must contain no phase
acceptance, rationale, code, or feature-planning prose. A write-set path, each existing ancestor,
and every descendant of a declared directory must be a real path and not a symlink or junction;
guard capture rejects a redirect before dispatch and guard check rejects one introduced by an
executor.

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
stay out of leaf packets and leaf controls. A leaf's `validation` is scoped to what its write set
can change; `acceptance` carries the project-wide checks, so every phase runs the full suite once
whatever its leaves validated. `next_phase` is either the consecutive phase identity
or `null`. A final phase (`next_phase: null`) must contain nonempty held-out
`overall_acceptance`; non-final phases use an empty list. A post-seal repair writes a new
phase-control revision and new review path; it never overwrites the sealed phase control. All
leaf, phase, and overall commands run from the Git worktree root.

After the active plan review artifact says `VERDICT: ship`, set
`NEXT_ACTION: SEAL_PHASE phase=N source=<PHASE_CONTROL>` and run:

```text
<python> <skill-dir>/scripts/validate_run.py <workspace> --phase N --seal
```

`<python>` is resolved as defined in `SKILL.md`, and the actual executable name is persisted in
controls and logs.

This writes immutable `seals/<step-id>.sha256` files covering both packet and control record, plus
a seal for the active phase control and its review.
Before dispatch, retry, audit, validation, and commit, rerun with `--require-sealed`. A mismatch is
`BLOCKED`; never regenerate a changed seal. A repair after sealing uses a new versioned step ID.

## 5. Total verdict transitions

Follow this table mechanically. When more than one row matches an input, the most specific matching row wins:
a row whose Input names a `depth_profile`, a `work_mode`, a `run_modes` value, an `autonomy` value,
a reported `MATERIAL_CHANGE`, a leaf `risk`, the phase's finality (a `next_phase` that is
`null`), more than one returned `repo_fact` blocker, a `repo_fact` blocker returned together with
a `product` or `authority` blocker, or a research fan-out in progress or joined
is a
specialisation of
the unconditional row with the same input subject, and each such row is placed directly above the
row it specialises.
In this table, a non-executor role dispatch — phase planner, plan reviewer, system reviewer, spec auditor, phase curator, or research agent — is every role that carries a wall-time bound but no control JSON.
“Revert” means run
`<python> <skill-dir>/scripts/worktree_guard.py restore <git-root> <snapshot> <control>`, which
restores every write-set path to its exact pre-attempt bytes — preserving uncommitted content that
predated the attempt — while never touching a path outside the write set or a protected baseline
path.

Before every fresh role starts, set `ACTIVE_AGENT: <role> pending`; then make the actual host
spawn-tool call; persist the host-returned task/thread identifier to
`attempts/<role>-<scope>-a<N>.agent`; for an executor dispatch that identifier path is passed to
`worktree_guard.py capture` as an additional excluded path alongside the expected capped-report
path; `phase-state.md` keeps `<role> pending` for the whole attempt window and receives the concrete
identifier only after `worktree_guard.py check` passes; a synchronous host that returns no
identifier records `<role> synchronous` and must never fabricate one; a state write never counts as
a spawn and an empty receiver set is never a valid wait; a failed spawn is a host-action failure
that is persisted and handled inside the same bounded retry/escalation policy, and the role is never
described as running. This paragraph states who writes what, not when `capture` runs; section 6
owns the ordering, and nothing here may contradict it.

Persist each role's capped return atomically to `attempts/<role>-<scope>-a<N>.report` before
interpreting it or advancing state. Attempt numbers, mismatch counts, and malformed-report counts
are derived from these immutable versioned artifacts; never keep them only in chat. `RETRY` mirrors
the current action's attempt count.

| Input | Candidate treatment | Next state and action |
|---|---|---|
| planner `planned` under `depth_profile: fast` | none | install the returned `PHASE_CONTROL`; the harness itself writes the plan-review record at the phase control's `plan_review` path per D-005, ending with the exact line `VERDICT: ship`; no plan reviewer is spawned; `REVIEWING_PLAN`; `SEAL_PHASE phase=N source=<PHASE_CONTROL>` |
| planner `planned` | none | install returned `PHASE_CONTROL`; `REVIEWING_PLAN`; `SPAWN_PLAN_REVIEWER phase=N source=<PHASE_CONTROL>` |
| planner `stop-experiment`, under `run_modes: step-by-step` | accepted commits remain | persist a checkpoint blocker whose recorded resume action is `CLOSING_PHASE`; `RUN_PHASE_ACCEPTANCE phase=N source=<PHASE_CONTROL>`, then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>` |
| planner `stop-experiment` | accepted commits remain | the active phase control, its `plan_review` artifact, and their seals are unchanged and no new plan-review round opens; `CLOSING_PHASE`; `RUN_PHASE_ACCEPTANCE phase=N source=<PHASE_CONTROL>` |
| workspace/control validation fail, other than a phase- or overall-acceptance failure whose every reported failure is a workspace validation reporting a missing required `baseline.md` key | revert any unaccepted candidate | persist validation evidence, then `BLOCKED` |
| `capture`, `check`, or `restore` exits 2 (`ERROR`) | revert any unaccepted candidate; when the failing command is `restore` itself, retain what is on disk and record the restoration as incomplete | persist the guard error output, then `BLOCKED`; `NEXT_ACTION: none` |
| planner `record-gap` | none | persist invalid-record evidence, then `BLOCKED` |
| planner `blocked` with a `repo_fact` blocker returned together with a `product` or `authority` blocker | none | route by the `blocked/product|authority` row; the `repo_fact` artifacts stay on disk and the post-answer repair planner returns them again if still open |
| planner `blocked/repo_fact` with more than one `repo_fact` blocker | none | require one returned versioned blocker artifact per question; `PLANNING`; `SPAWN_RESEARCH_AGENTS blockers=<comma-separated paths> attempt=1` |
| planner `blocked/repo_fact` | none | require returned `BLOCKER_PATH`; `PLANNING`; `SPAWN_RESEARCH_AGENT blocker=<path> attempt=1` |
| planner `blocked/product|authority` | none | persist blocker, then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>` |
| plan review `ship` | none | `REVIEWING_PLAN`; `SEAL_PHASE phase=N source=<PHASE_CONTROL>` |
| seal success | immutable reviewed artifacts | `EXECUTING`; `REPORT_PHASE_PLAN phase=N source=<PHASE_CONTROL>` |
| phase-plan report appended/printed, under `autonomy: interactive` | none | persist a checkpoint blocker at `blockers/CP-phase-N-plan-rK.md` whose `Reasons:` field lists every wait rule that fired at this event and whose recorded resume action is `EXECUTING`; `SPAWN_EXECUTOR control=<first queued control>`; then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>`; if another wait rule fires at this same event, add its reason to this one blocker instead of persisting a second |
| phase-plan report appended/printed | none | `EXECUTING`; `SPAWN_EXECUTOR control=<first queued control>` |
| the control a row dispatches (first queued or next queued) carries `kind: evidence` | none | that row's dispatch action is `RUN_EVIDENCE control=<path>` in place of `SPAWN_EXECUTOR control=<path>`; everything else in the row is unchanged |
| `RUN_EVIDENCE` completed | nothing to revert — an evidence step declares no writes | write full output to `logs/<step>.log`; journal the commands, exit statuses, and a short verbatim excerpt; an exit status is recorded data, never a failure and never retried; a step still running at `wall_time_minutes` is cancelled and the timeout journaled as its recorded outcome; then advance with no `ACCEPTED_THIS_PHASE` entry and no manifest write — a journaled evidence step is neither unstarted nor accepted, so when the queue still names an unstarted entry, dispatch it exactly like the `ACCEPT_LEAF` succeeded queue rows including their `run_modes` specialisations, and when no unstarted entry remains, follow the `all queued leaves accepted` rows the same way |
| seal failure/mismatch | revert any unaccepted candidate | `BLOCKED` |
| third unsuccessful plan-review round under `depth_profile: standard` | none | persist a checkpoint blocker with concrete options, then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>` |
| plan review `fix-first` | none | `PLANNING`; fresh planner `mode=repair source=<full review path>` |
| plan review `human-decision` | none | persist blocker, then human gate |
| measurement leaf `done` under `work_mode: experiment` with a negative or unexpected result | retain candidate | `VALIDATING`; `RUN_VALIDATION control=<path> attempt=N`, exactly like any `done` leaf; the result is recorded, not reverted |
| executor `done` | retain candidate | `VALIDATING`; `RUN_VALIDATION control=<path> attempt=N` |
| validation pass, leaf `risk: low`, `depth_profile: fast` | retain candidate | `REVIEWING_RESULT`; `ACCEPT_LEAF control=<path>` (the spec audit is skipped by profile, not by judgement) |
| validation pass, leaf `risk: high`, `depth_profile: fast` | retain candidate | `REVIEWING_RESULT`; `SPAWN_SPEC_AUDITOR control=<path>` — no leaf system review under `fast`, so nothing to parallelize |
| validation pass, leaf `risk: high` | retain candidate | `REVIEWING_RESULT`; `SPAWN_LEAF_REVIEWERS control=<path>` |
| validation pass | retain candidate | `REVIEWING_RESULT`; `SPAWN_SPEC_AUDITOR control=<path>` |
| `SPAWN_LEAF_REVIEWERS` reports both persisted | retain candidate | interpret the spec-audit verdict first, then route by the existing spec-audit and system-review rows exactly as if the two lenses had run serially; a `mismatch` or a `match/low` discards the parallel system report unread — journaled as discarded, never interpreted — and a `match/low` whose evidence completion becomes high spawns a fresh system reviewer serially per the `match/high` row; a `match/high` interprets the already-persisted system verdict by its rows without spawning again |
| executor exceeds `wall_time_minutes` | cancel the agent, revert | count as executor `failed` at the current attempt |
| a non-executor role dispatch exceeds its wall-time bound (first) | no candidate to revert | cancel the agent and redispatch the same role fresh once with explicitly narrowed scope |
| a non-executor role dispatch exceeds its wall-time bound (second) | no candidate to revert | persist a blocker, then human gate |
| executor `failed` or validation fail, attempts <2 | revert | `EXECUTING`; fresh executor at same tier with failing-log path |
| second failure | revert | `EXECUTING`; fresh executor at next recorded tier |
| top-tier failure | revert | `BLOCKED`; `NEXT_ACTION: none` |
| first malformed role report | revert executor candidate; otherwise none | redispatch the same role fresh once from original artifacts |
| second malformed role report | revert executor candidate; otherwise none | `BLOCKED`; `NEXT_ACTION: none` |
| executor `stopped-with-question` | verify/revert all write-set changes | `PLANNING`; fresh planner `mode=repair source=<question artifact>` |
| spec audit `match/high` under `depth_profile: fast` | retain | `REVIEWING_RESULT`; `ACCEPT_LEAF control=<path>`, because under `fast` system review runs at the phase gate only (D-013) |
| spec audit `match/high` | retain | high risk → leaf system review; low risk → `ACCEPT_LEAF` |
| spec audit `match/low` | retain | `REVIEWING_RESULT`; `COMPLETE_EVIDENCE control=<path> review=<path>` using fresh evidence reviewer |
| evidence completion becomes high | retain | continue as `match/high` |
| evidence remains low | revert candidate | `BLOCKED` |
| spec audit first `mismatch` | revert | fresh executor with original sealed packet; increment mismatch count |
| spec audit second `mismatch` | revert | `BLOCKED` |
| high-risk leaf system `pass` | retain | `REVIEWING_RESULT`; `ACCEPT_LEAF control=<path>` |
| `ACCEPT_LEAF` record or commit failure | retain the candidate; never revert and never re-invoke the executor | persist the record evidence, then `BLOCKED`; `NEXT_ACTION: none` |
| high-risk leaf system `repair` | revert | `PLANNING`; fresh planner `mode=repair source=<system review>` |
| any review `human-decision` | revert unaccepted candidate | persist blocker, then human gate |
| phase acceptance fail whose every reported failure is a workspace validation reporting a missing required `baseline.md` key | accepted commits remain | the harness appends the missing recorded line to each named workspace `baseline.md`, journals the append and its reason, and re-runs phase acceptance once; a second failure of that re-run is `PLANNING`; fresh planner `mode=repair source=<acceptance log>` |
| phase acceptance fail | accepted commits remain | `PLANNING`; fresh planner `mode=repair source=<acceptance log>` |
| `ACCEPT_LEAF` succeeded for a leaf whose control records `kind: measurement`, under `work_mode: experiment` | accepted commits remain | `PLANNING`; `SPAWN_PHASE_PLANNER phase=N mode=repair source=<the accepted measurement leaf's recorded results artifact>`; the fresh planner decides the next arm or the stop from the recorded results (D-007), so no queued arm is dispatched against a stale plan |
| `ACCEPT_LEAF` succeeded and the phase control's `queue` still names an unstarted leaf, under `run_modes: step-by-step` | accepted commits remain | persist a checkpoint blocker naming the next queued control, then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>` |
| `ACCEPT_LEAF` succeeded and the phase control's `queue` still names an unstarted leaf | accepted commits remain | `EXECUTING`; `SPAWN_EXECUTOR control=<next queued control>` |
| all queued leaves accepted, under `run_modes: step-by-step` | accepted commits remain | persist a checkpoint blocker whose recorded resume action is `CLOSING_PHASE`; `RUN_PHASE_ACCEPTANCE phase=N source=<PHASE_CONTROL>`, then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>` |
| all queued leaves accepted | accepted commits remain | `CLOSING_PHASE`; `RUN_PHASE_ACCEPTANCE phase=N source=<PHASE_CONTROL>` |
| phase acceptance pass | accepted commits remain | `CLOSING_PHASE`; `SPAWN_SYSTEM_REVIEWER scope=phase-N source=<acceptance review>` |
| phase system `repair` | accepted commits remain | `PLANNING`; fresh planner `mode=repair source=<system review>` |
| phase system `human-decision` | accepted commits remain | persist blocker, then human gate |
| phase system `pass`, final phase (`next_phase: null`) | none | `CLOSING_PHASE`; `RUN_FINAL_GATE phase=N source=<system review>` |
| phase system `pass` | none | `CLOSING_PHASE`; `SPAWN_PHASE_CURATOR phase=N source=<system review>` |
| curator `reconciled`, `next_phase` present, `MATERIAL_CHANGE` not `none`, under `autonomy: interactive` | none | persist a checkpoint blocker at `blockers/CP-phase-N-change.md` stating in plain words what changed, why, and what it affects, whose `Reasons:` field lists every wait rule that fired at this event and whose recorded resume action is `CLOSING_PHASE`; `CLOSE_PHASE phase=N` then install next planning action; then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>`; if another wait rule fires at this same event, add its reason to this one blocker instead of persisting a second |
| curator `reconciled`, `next_phase` present | none | `CLOSING_PHASE`; `CLOSE_PHASE phase=N` then install next planning action |
| curator `reconciled`, final phase, `MATERIAL_CHANGE` not `none`, under `autonomy: interactive` | none | persist a checkpoint blocker at `blockers/CP-phase-N-change.md` stating in plain words what changed, why, and what it affects, whose `Reasons:` field lists every wait rule that fired at this event and whose recorded resume action is the action the recorded overall-acceptance result dictates by the overall-acceptance rows below; then `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<path>`; if another wait rule fires at this same event, add its reason to this one blocker instead of persisting a second |
| curator `reconciled`, final phase | none | interpret the recorded overall-acceptance result of `RUN_FINAL_GATE` by the overall-acceptance rows below, exactly as if `RUN_OVERALL_ACCEPTANCE` had just returned it |
| curator `repair` | accepted commits remain | `PLANNING`; fresh planner `mode=repair source=<curation review>` |
| curator `human-decision` | accepted commits remain | persist blocker, then human gate |
| a research fan-out report arrives while another fan-out blocker still lacks a final persisted report | none | persist the report; a non-final `not-found` redispatches only that blocker fresh at the next recorded tier, its attempt derived from its `attempts/` artifacts, while `NEXT_ACTION` keeps the standing `SPAWN_RESEARCH_AGENTS` action unchanged for the whole fan-out; take no other routing action until every fan-out blocker holds a final report or one exhausts its ladder |
| research fan-out joined, every blocker `evidence` | none | `PLANNING`; one fresh planner `mode=repair source=<comma-separated evidence paths from the final reports>` |
| research fan-out joined, any blocker `authority` | none | with one authority blocker, record in it a resume action naming a repair planner whose `source` lists that blocker plus every gathered evidence path; with several, each blocker's resume action asks the next in `blockers=` list order, and only the last records the planner, whose `source` lists every authority blocker plus every gathered evidence path; then human gate on the first in list order |
| research `evidence` | none | `PLANNING`; fresh planner `mode=repair source=<evidence path>` |
| research first `not-found` | none | fresh research agent at next tier, attempt 2 |
| research second `not-found` | none | `BLOCKED` |
| research `authority` | none | persist blocker, then human gate |
| persisted human answer that asks only for more detail | none | answer every phase or leaf it names from the written records, plain words first and technical second, spawning no agent and advancing no state; `AWAITING_HUMAN_DECISION`; `ASK_HUMAN blocker=<same path>` |
| persisted human answer that requires a change to approved intent, an `intake.md` constraint, run scope, a deliverable, a non-goal, a phase's existence or purpose, or an approved `D-###` | revert unaccepted candidate if any | copy the answer verbatim and record it in the blocker as a design amendment; `PLANNING`; fresh planner `mode=repair source=<blocker path>` |
| persisted human answer whose blocker records a resume action | revert unaccepted candidate if any | perform exactly the resume action that blocker records |
| persisted human answer | revert unaccepted candidate if any | `PLANNING`; fresh planner `mode=repair source=<blocker path>` |
| overall acceptance pass | none | `CLOSING_PHASE`; `CLOSE_PHASE phase=N`, print final phase report, then `COMPLETE` |
| overall acceptance fail whose every reported failure is a workspace validation reporting a missing required `baseline.md` key | accepted commits remain | the harness appends the missing recorded line to each named workspace `baseline.md`, journals the append and its reason, and re-runs overall acceptance once; a second failure of that re-run is `PLANNING`; fresh planner `mode=repair source=<overall log>` |
| overall acceptance fail | accepted commits remain | `PLANNING`; fresh planner `mode=repair source=<the failing leg's log, or both when both fail>` |

When more than one wait rule would fire at the same event — an `autonomy: interactive` run-plan
approval, an `autonomy: interactive` change escalation, a `run_modes` pause, or the experiment-stop
checkpoint — persist exactly one combined checkpoint blocker whose `Reasons:` field lists every rule
that fired, never two sequential waits; its recorded resume action is the action the run would
perform at that event if no wait rule existed, that is the unconditional row for that event; and one
human answer clears every listed reason.

`RUN_FINAL_GATE` is the final phase's close gate and one of the run's two concurrent actions —
the other is the `SPAWN_RESEARCH_AGENTS` fan-out below. Its
log and result files are keyed to the gate's phase-control revision: `<gate>` below is the active
phase control's filename stem (such as `phase-2` or `phase-2-r3`), so a repaired phase's new
revision opens a fresh gate whose files cannot be satisfied by a discarded or failed gate's
leftovers. The gate splits the sealed `overall_acceptance` list in two mechanically: a command
whose text literally names the run workspace path, in either slash form — such as a
`validate_run.py <workspace>` check — is a workspace-reading command and
runs only at the join, after the curator has returned, so it reads quiesced records exactly as
the serial flow did; every other command is a product command and runs in the background leg. A
planner therefore writes any acceptance command that reads run-workspace records with the
workspace path literally in its text — its Git-root-relative spelling, `.oplan/<run-name>` — and
the plan review checks that along with the rest of the phase control; under `depth_profile: fast`,
where no independent plan reviewer runs, the harness checks it itself while writing the
plan-review record. The harness starts the product commands from the Git worktree root, truncating and
writing full output to `logs/<gate>-overall.log`, and after the last one exits writes
`logs/<gate>-overall.result` with one `<exit code>  <command>` line per command;
the result file is the completion marker, and a log without its result file is incomplete.
Without waiting on that leg, the harness spawns the fresh phase curator under the normal
non-executor dispatch rules; `ACTIVE_AGENT` names the curator alone, because the acceptance side is
harness-run commands, not an agent. The join is reached when the curator's capped report is
persisted and the background result file exists. The join interprets the curator's verdict first.
A curator
`repair` or `human-decision` follows its unconditional row, the harness cancels any still-running
background command and deletes the gate's log and result files, and the acceptance output is
discarded unread — journaled as discarded, never interpreted — so the repaired phase re-runs
overall acceptance fresh at its own close under its new revision's `<gate>` names. Only a curator
`reconciled` runs the workspace-reading commands, which write their own
`logs/<gate>-overall-join.log` and `logs/<gate>-overall-join.result` pair under the same
truncate-then-result rule, and interprets the combined recorded result of both result files; the
missing-baseline-key self-heal re-run happens at that join too. When the `MATERIAL_CHANGE` wait
fires at this join, the harness resolves the combined result first and only then persists the
checkpoint blocker, so the recorded resume action is dictated by a result that already exists. On
resume, `RUN_FINAL_GATE` is re-performed whole: a curator attempt with no persisted capped report
is re-dispatched under the normal attempt counting, and a leg without its own result file re-runs
from scratch, truncating its files. A workspace whose final-phase curator was dispatched by the
pre-gate serial
flow has no gate log at all: on its `reconciled` verdict, run the sealed overall-acceptance
commands now — serially, at the join, writing the `<gate>-overall-join` log and result pair — and
interpret them by the same rows. Running sealed
product commands before the curator's verdict
— or before an `autonomy: interactive` change checkpoint is answered — is not a product action:
the commands were sealed at plan review, they validate rather than build, and any verdict or human
answer that changes the plan discards their output.

`SPAWN_LEAF_REVIEWERS` is the high-risk leaf's review pair under `standard` and `paranoid`: one
fresh spec auditor and one fresh leaf system reviewer dispatched concurrently over the same frozen
candidate, each under its own template, wall-time bound, and malformed-report count, with its own
`attempts/<role>-<step>-a<N>.agent` and `.report` artifacts. `NEXT_ACTION` holds
`SPAWN_LEAF_REVIEWERS` unchanged until both reports are persisted; `ACTIVE_AGENT` records `leaf
reviewers pending` — an exception to this section's single-identifier replacement rule, like the
research fan-out's. The join interprets the spec-audit verdict first and then routes by the
existing serial rows, so every verdict combination ends exactly where the serial order ended; the
system report is discarded unread whenever the serial order would not have spawned that review.
Both lenses are read-only over the candidate; a transient Git index collision (the auditor's `git
add -N`) is a failed role dispatch handled by the normal redispatch rules. On resume the pair is
re-performed whole: re-dispatch exactly the roles that lack a persisted report, never one that has
one.

`SPAWN_RESEARCH_AGENTS` is the planning gate's fan-out. When a planner's report returns more than
one `repo_fact` blocker — it writes one versioned `blockers/` artifact per question — the harness
spawns one fresh research agent per blocker concurrently, each under the research-agent template
with its own 20-minute non-executor bound, its own recorded research-ladder attempts, and its own
`attempts/research-<blocker-stem>-a<N>.agent` and `.report` artifacts persisted per this section's
spawn bookkeeping. `ACTIVE_AGENT` records `research fan-out pending` for the whole fan-out window — an exception
to this section's single-identifier replacement rule, because the per-agent identifiers live in
the `attempts/*.agent` artifacts; the per-agent truth lives
only in the `attempts/` artifacts, never in chat. `NEXT_ACTION` holds the plural action unchanged
from first dispatch to join: per-blocker attempts and tiers are derived from the `attempts/`
artifacts, never from the action line, and `RETRY` likewise mirrors the standing action's
`attempt=1` for the whole window. A member whose `.agent` artifact has no matching `.report` is a
crashed attempt and is re-dispatched fresh under the normal attempt counting. The section 10 wall-time bounds and the malformed-report
counts apply per blocker's own dispatch series, never across the fan-out — two different members
each overrunning or malforming once are two first events. The join is reached when every fan-out
blocker
holds a final persisted report — `evidence`, `authority`, or a `not-found` at the top recorded
tier — and any blocker exhausting its ladder cancels every still-running fan-out agent and blocks
the run exactly as a lone one does. At an
all-`evidence` join, one fresh repair planner receives every evidence path as its comma-separated
`source`, so N questions cost one planner round instead of N. On resume the fan-out is
re-performed whole: re-dispatch exactly the blockers that lack a final persisted report — a
non-final `not-found` re-dispatches at the tier its `attempts/` artifacts imply — and never a
blocker whose report is final.

The `autonomy: interactive` run-plan wait is keyed on the `REPORT_PHASE_PLAN` event and not on the
phase: every sealed phase-control revision passes through that event, so a phase whose plan is
repaired and re-sealed waits again at each revision (D-019).

A change is material when it changes approved intent, an `intake.md` constraint, run scope, a
deliverable, a non-goal, the existence or purpose of any phase including a later sketch, or an
approved `D-###`. `MATERIAL_CHANGE` is reported by the phase planner and the phase curator and is
never judged by the harness. Every other change is routine and is reported as `none`: leaf counts,
leaf boundaries, step IDs, wall times, wording, file lists, validation commands, risk marks, worker
tiers, review rounds, and retries. This paragraph is the authoritative statement of the boundary,
and the copies in `templates/phase-planner.md` and `templates/phase-curator.md` restate it for roles
that do not read this reference.

Under `depth_profile: standard`, three unsuccessful plan-review rounds are a hard cap: the third
persists a checkpoint blocker with concrete options and enters `AWAITING_HUMAN_DECISION` instead of
dispatching a fourth repair planner. Under `paranoid` plan review is uncapped and unchanged, and
under `fast` no independent plan reviewer runs at all.

An unsuccessful plan-review round is one whose plan review returns `fix-first`; a `ship` or
`human-decision` round is not counted. The count is per phase, spans every phase-control revision of
that phase so a repair planner's new revision continues rather than restarts it, and resets only
when the phase closes, derived from immutable `reviews/phase-N-plan-rK.md` artifacts, not memory.

Under both `work_mode: experiment` and `run_modes: step-by-step` the measurement row outranks both
pause rows, so a measurement acceptance routes to the between-leaf planner. On `planned` the run
continues and the pause takes effect at the next `ACCEPT_LEAF`, one leaf later; on `stop-experiment`
there is no next `ACCEPT_LEAF`, and instead
a supervised experiment run takes its checkpoint at the stop, on the `run_modes: step-by-step` row
directly above the `planner `stop-experiment`` row. A blocker recording a resume action is answered
by performing it; the `persisted human answer` row's repair planner is for those recording none, so
both checkpoints reach `CLOSING_PHASE`; `RUN_PHASE_ACCEPTANCE`, not planning over a sealed control.

Retry-only context such as a failing-log path belongs in the fresh agent prompt, not in `NEXT_ACTION`.
Every persisted action must use exactly the arguments listed for that verb in the
required action arguments table in section 2. Under `commit_mode: none` the `ACCEPT_LEAF` record or
commit failure row covers a failing `record-accepted` or `verify-accepted`; under `commit_mode:
auto` it covers a failing stage, commit, or commit-diff verification.
The guard exit-2 row covers `capture`, `check`, and `restore` only. A failing `record-accepted` or
`verify-accepted` is routed by the `ACCEPT_LEAF` record or commit failure row regardless of its
exit code, so the candidate is retained and never reverted; a `verify-accepted` failure surfaced
through `validate_run.py` is routed by the workspace/control validation fail row instead. That
routing precedent is bounded: a phase- or overall-acceptance failure whose
every reported failure is a workspace validation reporting a missing required `baseline.md` key
is routed by the acceptance-failure specialisation directly above its acceptance row and not by the
workspace/control validation fail row. When
`restore` itself exits 2, reverting is the action that failed: do not retry it, leave the worktree
exactly as the failed `restore` left it, and record the restoration as incomplete and the
candidate's write-set paths as unrestored before entering `BLOCKED`. A `capture` that exits 2
happens before the executor is dispatched, so reverting an unaccepted candidate is a defined no-op
there.

`ACCEPT_LEAF` verifies the seal. Under `commit_mode: auto`, it stages only `write_set` and commits
with path-restricted Git semantics (`git commit --only -- <write_set>`) so unrelated pre-staged
changes cannot enter, verifies the commit diff contains no path outside the intended write set, and
records its full SHA as `LAST_ACCEPTED`. Under `commit_mode: none`, it does not stage or commit;
instead it runs

`<python> <skill-dir>/scripts/worktree_guard.py record-accepted <git-root> <control> <workspace>/attempts/accepted-state.json`

and then the matching

`<python> <skill-dir>/scripts/worktree_guard.py verify-accepted <git-root> <workspace>/attempts/accepted-state.json`

before advancing, keeps `LAST_ACCEPTED` at the baseline commit SHA, and notes the manifest path and
accepted step in the journal. In both modes it appends the journal and advances to the next leaf or
phase gate.

This one cumulative manifest records ordered sealed controls plus current recursive worktree and
Git-index hashes for the union of their write sets, so a later accepted leaf may re-baseline an
earlier leaf's paths when it declares them: (D-002 as amended by D-019) `record-accepted`
re-baselines only the recorded paths at or below a path in the newly accepted control's write set,
and fails without writing when any other recorded path has changed. Because a recorded directory is
one whole-tree state, a leaf that writes inside an already-accepted directory must declare that
directory in its own `write_set`, and declaring it means accepting responsibility for everything
under it. If either command fails, that is a blocking record failure and not an acceptance
(D-020): re-running `record-accepted` for a control already in the manifest re-baselines nothing —
it verifies every recorded path, including that control's own, and fails without writing when any
has changed — so a retried `ACCEPT_LEAF` re-surfaces the failure instead of erasing it. A failing
`record-accepted` or `verify-accepted` here never reverts the candidate and never re-invokes the
executor: the harness persists the record evidence and enters `BLOCKED` per the transition-table
row for it, because recording a control is a one-shot gate with no unrecord, rollback, or force path
and the manifest is never edited by hand (D-023). Recovery is human-initiated: a leaf that must be
re-executed after its control was recorded is replanned under a new versioned step ID whose new
control file refreshes every path it declares, so that repair control's `write_set` must cover
every path the failed control declared.

Under `commit_mode: none`, a write set may overlap protected baseline paths because attempt
snapshots, not commits, preserve pre-existing bytes.

The guard owns the manifest, writes this exact schema, and it must never be edited by hand:

```json
{
  "schema": "oplan-accepted-state/v1",
  "repo": "<absolute Git worktree path>",
  "controls": [
    {"path": ".oplan/<run>/control/1.1.json", "sha256": "<64 lowercase hex>"}
  ],
  "write_set_states": {
    "path/in/write-set": {
      "worktree": "<recursive byte, type, and mode state>",
      "index": "<SHA-256 of git ls-files --stage output>"
    }
  }
}
```

At phase
close, write the report and, if another phase exists, atomically set `STATE: PLANNING` and
`PHASE_CONTROL: none` and `NEXT_ACTION: SPAWN_PHASE_PLANNER phase=N+1 mode=new source=none` before printing. The final phase
becomes `COMPLETE` only after curation and overall acceptance.

## 6. Human, research, and recovery records

Before any human question, write `blockers/B-###.md` with classification, exact question,
recommendation, alternatives, evidence already checked, answer field, and resume action; then
atomically enter `AWAITING_HUMAN_DECISION`. Ask only after the state is durable. On reply, copy the
answer verbatim into that file, then perform the resume action that file records; when it records
none, spawn a fresh repair planner with the file as `SOURCE`. Never pass an oral answer to an
executor.

A checkpoint blocker is a blocker written at a wait that is not a question. It is named
`blockers/CP-<event>.md`, it carries a `Reasons:` field listing every wait rule that fired at that
event, it records the resume action the table's row for that event names, and it uses the same
fields as `blockers/B-###.md` otherwise.

Append one compact journal block per evidence step with its commands, exit statuses, verbatim
excerpt, and log path.
Append one compact journal block per accepted leaf with packet/control/seal paths, worker tier,
validation, `did`, `failure_cause`, surprises, deviations, structural flags, decisions, audit and
system verdicts, retries/escalation, verified cost or `unavailable`, commit, and timestamp. At
phase close append acceptance, curation including the curator's reported `MATERIAL_CHANGE` line,
interventions, cost by role, and harness context size or
`unavailable`. `STATUS.md` is current state only; `briefing.md` is append-only history.

On resume, read `phase-state.md` first, verify `LAST_ACCEPTED` and all relevant seals, explain any
in-flight candidate from its control record, then perform `NEXT_ACTION`. Under `commit_mode: none`,
also run `<python> <skill-dir>/scripts/worktree_guard.py verify-accepted <git-root> <workspace>/attempts/accepted-state.json`
on the cumulative manifest before any dispatch. The run validator also requires that manifest from
initialization onward and checks that it includes every step in `ACCEPTED_THIS_PHASE`. If state is
inconsistent, set `BLOCKED` with the validation evidence. An explicitly initiated recovery may then
use a fresh reconstruction reviewer over commits plus record paths. Never ask the human to repeat a
decision already present in the records.

For an executor question, the harness first runs the undeclared-write guard/revert, then copies
the report path, exact `QUESTION`, affected step, and repair resume action into
`blockers/Q-<step>-a<N>.md`. Repository-fact blocker artifacts use the same fields plus inspected
sources and are written by the planner/reviewer that reports them.

Every harness record write for the attempt — the `phase-state.md` update, any `journal.md` append,
and every other workspace write — completes before `worktree_guard.py capture`.
All harness record writes for the attempt complete before `capture`; nothing is written between `capture` and the dispatch.
Immediately before dispatching an executor, run:

`<python> <skill-dir>/scripts/worktree_guard.py capture <git-root> <attempt-snapshot> <control> <expected-report-relative-path> <agent-id-relative-path>`

then dispatch as the next harness action, with nothing written in between. After the capped return,
atomically persist only that excluded report, then run
`<python> <skill-dir>/scripts/worktree_guard.py check <git-root> <snapshot> <control> <workspace>`
before interpreting the verdict or writing anything else. A gate re-run performed after post-gate
writes is uninterpretable and is not evidence. Any changed path outside the
control write set, including `.oplan` or a pre-existing dirty path, is a scope violation: preserve
the guard evidence, revert the declared candidate, and set `BLOCKED`. This guard precedes
validation, audit, retry, and commit; a scoped diff alone is not isolation.

`<attempt-snapshot>` must be `<workspace>/attempts/<step-id>-a<N>-snap.json`. `capture` adds the
snapshot and its `.files` sidecar to the snapshot's own exclusion list, and `check` requires every
exclusion to lie strictly below `<workspace>/attempts`, so a snapshot written anywhere else is
accepted by `capture`, dispatched against, and only then refused by `check` with exit code 2 —
after the guarded window has closed.

`worktree_guard.py capture` always runs from the worktree copy of the guard. When the guard script
itself is inside the leaf's `write_set`, the post-attempt `check` and any `restore` for that attempt
run from the pre-attempt sidecar copy at `<attempt-snapshot>.files/<guard-path>` —
the same executable that wrote the snapshot — so an executor never judges its own rewrite of the guard. A
candidate guard's own compatibility paths therefore get no gate-level exercise, so a leaf that
changes the guard's state grammar or its collection-membership predicate must prove both inside its
own frozen validation.

## 7. Guard threat model and limits

The guard defends against accidental scope violations, not against an executor that deliberately forges harness records. The pre-attempt snapshot, its sidecar copies, and the cumulative
accepted-state manifest all live inside the worktree and are therefore forgeable by a deliberately
malicious executor; closing this gap is out of scope for this run.

The manifest records a declared directory as a single whole-tree state, so it detects any change
under that directory but cannot attribute it to one file, and accepting a control that declares the
directory re-baselines everything under it in one step.
