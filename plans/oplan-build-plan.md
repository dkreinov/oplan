# Plan: Build the `oplan` skill per DESIGN.md

**Task:** Build the orchestrated planning skill exactly per DESIGN.md — deliverables in §14. All §15 open questions are now resolved (see Frozen decisions below). DESIGN.md remains the single source of truth for everything else.

**Execution mode:** autonomous (chosen 2026-07-23)
**Phase structure:** single-phase plan (7 steps, one repo, one session of markdown authoring)
**Recommended model:** Opus — design is frozen; this is careful markdown authoring, no novel architecture. (Session currently runs Fable; safe to `/model` down to Opus before Step 1 since this plan file is the anchor.)
**Recommended thinking budget:** High — the paper test (Step 6) needs careful contradiction-hunting; the rest is structured writing.
**Context recommendation:** continue in current session — it is fresh (only DESIGN.md/STATUS.md read, questions gate).
**Subagent policy:** ALLOWED — user granted standing permission ("go, with subagent always", 2026-07-23). Step 6's paper test runs as a read-only fresh-context subagent (bounded: reads `oplan/**` + `DESIGN.md`, writes nothing; fixes are applied locally by the orchestrator). Other steps stay local — they are authoring steps with a single write set.

## Frozen decisions (from the questions gate, 2026-07-23)

1. **Skill name:** `oplan`. Workshop copy: `oplan/` in this repo. Install target (AFTER tests pass, not in this plan): `~/.claude/skills/oplan/`.
2. **Executor report contract** (verbatim — SKILL.md and executor template must copy this exactly):
   ```
   STATUS: done | failed | stopped-with-question
   DID: <=5 lines — what changed, per file
   VALIDATION: exact command run + last lines of output
   SURPRISES: <=3 lines, or "none"
   DEVIATIONS: <=3 lines, or "none"
   QUESTION: only if stopped — the exact decision needed
   METRICS: retries=N, validation_first_try=yes|no
   (hard cap: 30 lines total)
   ```
3. **Field guide:** `field-guide/index.md`, budget **40 lines** — soft cap: exceeding it requires a one-line justification in journal.md, and fullness/overflow is recorded in phase-boundary metrics.
4. **Model tiers:** SKILL.md speaks in generic tiers — PLANNER (strong), WORKER (cheap), CHECKER (middle) — with a per-harness binding table. Claude Code v0.1 binding: orchestrator Opus · executor Sonnet · auditor Sonnet · next-phase planner Opus · escalation ladder Haiku < Sonnet < Opus < Fable (one rung up per escalation).
5. **Fire-drill cost ceiling:** $10 API-equivalent, written into `tests/fire-drill.md` before any run; exceeding it = logged FAIL finding.

## Assumptions (stated, not asked)

- The two "golden prompt lines" (DESIGN.md §4) appear verbatim in SKILL.md and the executor template: the escalation rule ends with "STOP and return the question. Never decide it yourself."
- Metrics + journal format spec live inside SKILL.md (DESIGN.md §14.5 allows this) — no separate spec file.
- Smoke test and fire drill are AUTHORED here but RUN in later sessions (the fire drill explicitly requires a scratch folder outside this repo so executors can't read the trap descriptions).
- No installation to `~/.claude/skills/` in this plan — DESIGN.md §14.1 says install only when tests pass.
- All artifacts follow DESIGN.md §16: simple-explainer style, mermaid in .md files.
- STATUS.md is rewritten (photograph rule), never appended.

---

## Step 1: Write `oplan/SKILL.md` — the complete skill

**Goal**: The full skill text: YAML frontmatter (name `oplan`, description with trigger conditions); purpose + when to use (and when NOT: single-step tasks → plain plan-skill); roles architecture with mermaid diagram (orchestrator / plan reviewer / executor / auditor / next-phase planner); orchestrator procedure (plan Phase 1 → fresh-eyes plan review → dispatch packets one at a time → orchestrator re-runs frozen validation → auditor verdict → checkpoint files → phase gate → fresh next-phase planner → phase-boundary pause + canonical handoff); hard rules (single writer, split-brain prevention: every design decision made at plan time, sequential phases, crash-only file discipline); the two golden lines (§4) verbatim; file rules table (journal.md append-only · STATUS.md photograph/rewrite, orchestrator-only writer · phase-state.md checkpoint per acceptance · field-guide/index.md 40-line soft cap + justification rule); verification 3 layers + escalation ladder (fail validation twice → same packet one tier up, log every escalation); tier definitions + Claude binding table (frozen decision 4); executor report contract verbatim (frozen decision 2); metrics spec (§11's six metrics, journal entry format per step); phase-boundary context rule (§8: record orchestrator token count, default = pause + user /clear + paste handoff).

**Files**: `oplan/SKILL.md`

**Commands**: None (file authoring)

**Success criteria**: Every DESIGN.md section §3–§9 + §11 has a corresponding SKILL.md section; all frozen contract strings present verbatim; contains ≥1 mermaid diagram; simple-explainer language throughout.

**Validation**:
```
grep -c "STOP and return the question. Never decide it yourself." oplan/SKILL.md   # >=1
grep -c "hard cap: 30 lines" oplan/SKILL.md                                        # >=1
grep -c "Haiku < Sonnet < Opus < Fable" oplan/SKILL.md                             # >=1
grep -c "40 lines" oplan/SKILL.md                                                  # >=1
grep -c "mermaid" oplan/SKILL.md                                                   # >=1
grep -c "METRICS:" oplan/SKILL.md                                                  # >=1
```
All six greps ≥1.

⚠️ Risk: SKILL.md silently drifting from DESIGN.md wording on a rule (two-way-readable text). Mitigation: Step 6 paper test hunts exactly this; validation greps pin the highest-value strings now.

### After completing this step:
- [ ] Run the validation greps and report results
- [ ] Create work_log.md (template) and log Step 1
- [ ] `git add oplan/SKILL.md work_log.md && git commit -m "feat: Step 1 - oplan SKILL.md complete skill text"`
- [ ] Summary + Next: Step 2 executor packet template
- [ ] Step-by-step: STOP | Autonomous: proceed

## Step 2: Write `oplan/templates/executor-packet.md`

**Goal**: The fill-in template the orchestrator uses to dispatch an executor. Must contain all 7 packet elements (DESIGN.md §5): (1) spec-complete step (goal, files, commands, frozen validation command); (2) relevant frozen contracts excerpt slot; (3) hard write-set boundary + non-goals boilerplate (only these files; no refactoring; no fixing adjacent code; never touch tests/validation — with the test-writing-step exception noted); (4) escalation rule verbatim; (5) `field-guide/index.md` injection slot; (6) budgets (retry limit, token/time bounds); (7) required report format verbatim (frozen decision 2).

**Files**: `oplan/templates/executor-packet.md`

**Commands**: None

**Success criteria**: All 7 elements present; placeholders clearly marked (e.g. `{{...}}`); report contract byte-identical to SKILL.md's.

**Validation**:
```
grep -c "STOP and return the question. Never decide it yourself." oplan/templates/executor-packet.md  # >=1
grep -c "hard cap: 30 lines" oplan/templates/executor-packet.md                                       # >=1
grep -c "field-guide" oplan/templates/executor-packet.md                                              # >=1
diff <(sed -n '/STATUS: done/,/hard cap/p' oplan/SKILL.md) <(sed -n '/STATUS: done/,/hard cap/p' oplan/templates/executor-packet.md)   # empty = identical
```

### After completing this step:
- [ ] Run validations, report; update work_log.md
- [ ] `git add oplan/templates/executor-packet.md && git commit -m "feat: Step 2 - executor packet template"`
- [ ] Summary + Next: Step 3 auditor + next-phase planner templates
- [ ] Step-by-step: STOP | Autonomous: proceed

## Step 3: Write `oplan/templates/auditor.md` and `oplan/templates/next-phase-planner.md`

**Goal**: Auditor template: receives ONLY the diff + the step spec (nothing else — that's the lens), answers "does the work match the spec, nothing more, nothing less?", fixed short verdict format (match/mismatch + findings). Next-phase-planner template: fresh strong agent, reads the WRITTEN RECORD ONLY (journal.md, phase-state.md, field-guide, design.md, previous phase plan skeletons), produces Phase N+1 detailed plan for orchestrator review; explicitly forbidden from inheriting anything not in files (this doubles as the written-record completeness test).

**Files**: `oplan/templates/auditor.md`, `oplan/templates/next-phase-planner.md`

**Commands**: None

**Success criteria**: Auditor sees only diff+spec (stated as a hard rule); planner reads files only; both have fixed output formats.

**Validation**:
```
grep -ci "only the diff and the step spec" oplan/templates/auditor.md        # >=1
grep -ci "nothing more, nothing less" oplan/templates/auditor.md             # >=1
grep -ci "written record" oplan/templates/next-phase-planner.md              # >=1
```

### After completing this step:
- [ ] Run validations, report; update work_log.md
- [ ] `git add oplan/templates/auditor.md oplan/templates/next-phase-planner.md && git commit -m "feat: Step 3 - auditor and next-phase planner templates"`
- [ ] Summary + Next: Step 4 smoke test
- [ ] Step-by-step: STOP | Autonomous: proceed

## Step 4: Write `tests/smoke-test.md`

**Goal**: The smoke-test task definition + pass checklist (DESIGN.md §10.2): a trivial do-nothing task (e.g., create two tiny text files in a scratch folder, one "phase" of two steps) that proves plumbing only — every role spawns, receives its packet, returns the fixed-format report; journal.md / STATUS.md / phase-state.md / field-guide written; no traps. Checklist is binary per item.

**Files**: `tests/smoke-test.md`

**Commands**: None

**Success criteria**: A fresh session could run the smoke test from this file alone: task text, how to invoke oplan, and a pass/fail checklist covering every role + every file artifact.

**Validation**:
```
grep -ci "checklist" tests/smoke-test.md        # >=1
grep -c "phase-state.md" tests/smoke-test.md    # >=1
grep -c "journal.md" tests/smoke-test.md        # >=1
```

### After completing this step:
- [ ] Run validations, report; update work_log.md
- [ ] `git add tests/smoke-test.md && git commit -m "test: Step 4 - smoke test task and checklist"`
- [ ] Summary + Next: Step 5 fire drill
- [ ] Step-by-step: STOP | Autonomous: proceed

## Step 5: Write `tests/fire-drill.md`

**Goal**: The fire-drill spec (DESIGN.md §10.3): tiny real disposable task = a slice of the English app (Hebrew–English word-list data model + quiz logic + tests, ~200 lines), to be RUN in a scratch folder OUTSIDE this repo. Contains: the task brief handed to oplan; the planted traps — ambiguity trap (one step spec deliberately silent on a real decision; pass = executor STOPs with QUESTION) and audit trap (one subtle spec violation seeded; pass = auditor or frozen validation catches it); the resume-drill procedure (kill orchestrator mid-phase; fresh session resumes from files alone); the full pass/fail checklist (artifacts complete + current, all validations ran, zero executor design decisions, metrics collected); and the **$10 API-equivalent cost ceiling** recorded up front. Trap descriptions live ONLY in this file — the drill runs outside the repo precisely so executors can't read them.

**Files**: `tests/fire-drill.md`

**Commands**: None

**Success criteria**: A fresh session could conduct the whole drill from this file: setup, task brief, both traps with exact pass/fail conditions, resume procedure, checklist, ceiling.

**Validation**:
```
grep -c '\$10' tests/fire-drill.md              # >=1
grep -ci "ambiguity trap" tests/fire-drill.md   # >=1
grep -ci "audit trap" tests/fire-drill.md       # >=1
grep -ci "resume" tests/fire-drill.md           # >=1
grep -ci "outside" tests/fire-drill.md          # >=1  (scratch folder outside repo)
```

⚠️ Risk: traps leaking to executors if the drill is ever run inside this repo. Mitigation: the file's first line states the outside-repo requirement; checklist includes it.

### After completing this step:
- [ ] Run validations, report; update work_log.md
- [ ] `git add tests/fire-drill.md && git commit -m "test: Step 5 - fire drill with traps, resume drill, cost ceiling"`
- [ ] Summary + Next: Step 6 paper test
- [ ] Step-by-step: STOP | Autonomous: proceed

## Step 6: Run the paper test and fix findings

**Goal**: DESIGN.md §10.1 — walk through SKILL.md + all three templates playing every role (orchestrator, plan reviewer, executor, auditor, next-phase planner), hunting: contradictions between sections; gaps (a role needs information no rule delivers to it); two-way-readable instructions; contract mismatches between SKILL.md and templates. Fix every finding in the source files. Record findings + fixes in work_log.md. (If the user allowed the subagent option: a read-only fresh-context subagent performs the hunt and returns findings; fixes still applied locally.)

**Files**: potentially `oplan/SKILL.md`, `oplan/templates/*.md` (fixes only)

**Commands**: None

**Success criteria**: A written walkthrough exists for each role ("as the executor, my packet gives me X, I return Y"); zero unresolved findings; all Step 1–3 validation greps still pass after fixes.

**Validation**: Re-run ALL validation greps from Steps 1–3 (contracts survived the fixes) + findings list with resolution status in work_log.md.

⚠️ Risk: paper test finds a real design-level contradiction (not just wording). That is NOT fixable silently — Hard Rule: STOP and surface to the user, since DESIGN.md is frozen.

### After completing this step:
- [ ] Run validations, report; update work_log.md (findings + fixes)
- [ ] If files changed: `git add oplan/ && git commit -m "fix: Step 6 - paper test findings"` (else skip)
- [ ] Summary + Next: Step 7 STATUS rewrite + cleanup
- [ ] Step-by-step: STOP | Autonomous: proceed

## Step 7: Rewrite STATUS.md + final cleanup

**Goal**: Rewrite STATUS.md as a fresh photograph (never append): what exists now (all §14 deliverables ✅ with paths), updated mermaid if needed, next action = run smoke test (then fire drill in scratch folder, then English-app real run), open items (English-app details still awaited from Dennis; install to ~/.claude/skills/oplan/ only after tests pass). Remove any scratch artifacts. Verify repo is clean and every deliverable is committed.

**Files**: `STATUS.md`

**Commands**: `git status` (must be clean after commit)

**Success criteria**: STATUS.md accurately photographs the post-build state with zero stale lines (no "Not started" rows for things that now exist); working tree clean.

**Validation**:
```
grep -c "oplan" STATUS.md            # >=1
grep -ci "smoke test" STATUS.md      # >=1 (the next action)
grep -c "Not started" STATUS.md      # must be 0
git status --porcelain               # empty after final commit
```

### After completing this step:
- [ ] Run validations, report; update work_log.md (final summary)
- [ ] `git add STATUS.md && git commit -m "docs: Step 7 - STATUS photograph after oplan build"`
- [ ] Summary + Next: Plan complete — retrospective
- [ ] Step-by-step: STOP | Autonomous: plan complete, present retrospective.

---

## Handoff prompt

```text
--- HANDOFF PROMPT (paste into fresh session) ---
Continue plan from: plans/oplan-build-plan.md
Read first: plans/oplan-build-plan.md fully, then DESIGN.md, then work_log.md (if it exists)
Resume at: first step not marked complete in work_log.md
Execution mode: <not chosen yet | as recorded in work_log.md>
Model: Opus
Context: OK to start fresh — plan file + DESIGN.md are self-sufficient
Before executing:
1. Read the files above fully.
2. Check git status.
3. Re-acknowledge the Frozen decisions section (report contract, 40-line field guide, tier binding, $10 ceiling) before writing.
4. If execution mode is "not chosen yet", ask the user to choose step-by-step or autonomous.
Important:
- DESIGN.md is frozen — a design-level contradiction found mid-build is a STOP, not a silent fix.
- All artifacts: simple-explainer style + mermaid in .md files (DESIGN.md §16).
- STATUS.md is rewritten (photograph), never appended.
- Stage only files listed in each step.
--- END HANDOFF PROMPT ---
```
