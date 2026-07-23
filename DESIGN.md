# Orchestrated Planning Skill — Design Document

**Status:** Design frozen 2026-07-23. This document is the single source of truth for building the skill.
**Audience:** the planning session that will build the skill, and the user (Dennis).
**Writing rule for all artifacts of this project:** smart-12-year-old explainer style — simple words, easy diagrams, never skip data.

---

## 1. Goal and non-goals

**Goal:** a new Claude Code skill that plans AND executes multi-phase work using subagents:
a strong model plans, cheap models execute in clean contexts, separate fresh-context agents
audit, and the human stays in the loop through simple status pages.

**Non-goals:**
- NOT a replacement for the existing `plan-skill` (`~/.claude/commands/plan-skill.md`). That stays untouched.
- NOT a big framework. Must be small: one SKILL.md + 3 prompt templates + a tests folder.
- NOT an unstructured swarm. No parallel writers, no agent-to-agent negotiation.

**Hard constraints from the user:**
- Quick to build and test — hours, not a full day of tokens.
- Measurable — metrics collected on every run, and a kill criterion (§12).
- Human-followable — STATUS.md in simple language with mermaid diagrams.

## 2. Evidence base (why we believe this design)

| Source | Key finding we use |
|---|---|
| [Cursor: Agent swarms and model economics](https://cursor.com/blog/agent-swarm-model-economics) | Strong planner + cheap workers: 100% quality at $1,339 vs 85% at $10,565 for frontier-only. "Few moments in a large task genuinely require frontier intelligence." Spec quality > worker capability ("specs as prompts"). Field Guide: agent-curated folder, index.md injected into every agent, line budget. Review lenses: decorrelated reviewers stack. |
| [Anthropic: multi-agent research system](https://www.anthropic.com/engineering/built-multi-agent-research-system) | Orchestrator + parallel subagents beat single agent by 90.2%. Vague delegation → duplicated work; fix = explicit objectives, boundaries, scope exclusions per subagent. Judge outcomes (rubric), not steps. |
| [Cognition: Multi-Agents, What's Actually Working](https://cognition.com/blog/multi-agents-working) | "Writes stay single-threaded; additional agents contribute intelligence rather than actions." Fresh-context reviewer catches ~2 bugs/PR, 58% severe (context rot is real). Weak models can't tell when to escalate — escalation must NOT be the weak model's job. Unstructured swarms are "mostly a distraction." |
| [AgentCARD paper (arXiv 2606.20629)](https://arxiv.org/abs/2606.20629) | Mixed-model teams: up to 44% more accurate at equal cost, or equal accuracy at up to 12× lower cost. BUT the bottleneck role (planner vs executor) is domain-dependent — must be measured, not guessed. |

## 3. Architecture — roles

```
USER ◄── STATUS.md (simple explainer + mermaid, always current)
 │
 ▼
ORCHESTRATOR = main thread (strong model: Fable/Opus)
 │  plans Phase 1, makes ALL design decisions, dispatches, gates, logs
 ├─► PLAN REVIEWER   subagent, fresh context — reviews the plan (new pair of eyes)
 ├─► EXECUTOR        subagent, cheap model (Sonnet/Haiku), clean context, gets a "packet" (§5)
 ├─► AUDITOR         subagent, fresh context — sees ONLY diff + spec, gives verdict (§6)
 └─► NEXT-PHASE PLANNER  subagent, strong model, fresh context — plans Phase N+1
     from the WRITTEN RECORD ONLY, after Phase N execution finishes.
     The orchestrator (main thread) reviews its plan — symmetric fresh eyes.
```

**Rules:**
- **Single writer (Cognition):** in v0.1 executors run ONE AT A TIME. Extra agents contribute
  intelligence (review, audit, planning), not parallel actions. Parallel disjoint-file executors = v0.2, only if metrics demand speed.
- **Split-brain prevention (Cursor):** the orchestrator/planner makes every design decision.
  No decision is ever deferred to execution time. No two agents can decide the same question.
- **Sequential phases:** Phase N+1 detailed planning starts only after Phase N execution is done
  (full data available). Phase skeletons for later phases exist from the start; only the current phase is detailed.
- **Phase N+1 planned by a FRESH strong subagent from files only.** This doubles as a test that
  the written record is complete. Main thread reviews the produced plan.

## 4. The two most important prompt lines

1. **Executor escalation rule:** "If you hit a question the spec doesn't answer, STOP and return
   the question. Never decide it yourself." (worker-level split-brain prevention)
2. **Report cap:** executors return a fixed-format report, max ~30 lines. The orchestrator never
   ingests a worker's full transcript. (context-rot prevention, Cursor's planner-context principle)

## 5. Executor packet (what a clean-context executor receives)

1. The spec-complete step: goal, files, commands, frozen validation command.
2. Relevant frozen contracts only (design-doc excerpt, not the whole plan).
3. Hard write-set boundary + explicit non-goals: only these files; no refactoring; no fixing
   adjacent code; never touch tests/validation commands (unless it IS a test-writing step —
   then a different agent reviews those tests).
4. The escalation rule (§4.1).
5. `field-guide/index.md` contents (§7).
6. Budgets: retry limit, token/time bounds.
7. Required report format (status, diff summary, validation output, surprises, deviations — ≤30 lines).

## 6. Verification — three layers, executor never self-certifies

1. **Frozen mechanical gate:** each step's validation command is written by the planner at plan
   time and frozen. Executor may run it while iterating, but acceptance happens only when the
   ORCHESTRATOR re-runs it in a clean state.
2. **Auditor (output lens):** fresh-context subagent, sees only the diff + the step spec.
   Question: does the work match the spec, nothing more, nothing less? (Cognition: this
   configuration catches ~2 bugs/PR.) v0.1 has ONE auditor lens; codebase-lens auditor = v0.2.
3. **Phase gate:** phase acceptance criteria written during planning, before any executor exists
   (miniature of Cursor's held-out test suite).

**Escalation ladder (orchestrator-driven, never executor-driven — Cognition's smart-friend failure):**
step starts on the cheap tier → validation fails twice → orchestrator re-dispatches the SAME
packet one model tier up. Escalations are logged; they are the misclassification signal.

## 7. Files (per run, in the target project's workspace)

> **Amendment (2026-07-23, approved by Dennis):** a fifth file, `plan.md` (current phase in full,
> later-phase skeletons, phase acceptance criteria), was added during the build. The paper test
> showed the original four files violate §8's own crash-only principle: without it, every step
> spec and frozen validation command lives only in the orchestrator's head, and mid-phase resume
> is impossible.

| File | Job | Rule |
|---|---|---|
| `journal.md` | history — everything that happened | append-only; allowed to grow; raw input for next-phase planner |
| `STATUS.md` | photograph of NOW, for the human | REWRITTEN (reconciled) every update, never appended; line budget; simple language + mermaid diagram; no stale lines, no duplication. Written by orchestrator ONLY. |
| `phase-state.md` | "where are we" for agents | updated at every step acceptance (checkpoint) |
| `field-guide/index.md` | curated lessons, injected into EVERY agent's packet | line-budgeted; orchestrator promotes journal entries into it at phase boundaries (manual curation in v0.1) |

STATUS.md vs journal.md: if a fact is history it lives in the journal; if it is current it lives
in STATUS. Duplication impossible by design.

## 8. Context-rot handling (the orchestrator's aging context)

Facts: subagents are born fresh and die at task end — rot-immune, and they CANNOT `/clear`
themselves. Neither can the main thread — `/clear` is a user command. Claude Code auto-compaction
exists but is lossy. Therefore:

- **Crash-only principle:** if any fact exists only in the orchestrator's head and not in a file,
  that is a bug in the skill.
- Short executor reports (§4.2) + checkpoint after every acceptance (§7) keep growth slow;
  worst-case loss = current step.
- **Phase boundaries pause anyway (default):** orchestrator prints the canonical handoff prompt;
  the USER presses `/clear` and pastes — one keystroke; fresh session resumes from files.
- **Context metric:** at each phase boundary, journal records the orchestrator's accumulated token
  count. Data decides whether phase-boundary `/clear` becomes "strongly recommended" or "optional".
- **Resume drill (§10):** proves resume-from-files-alone actually works.

## 9. Inputs — the design stage sits in front, not inside

The skill takes an optional `design.md` (the frozen WHAT) as input. For greenfield features,
produce it first — e.g., with the user's `grill-me` skill (adversarial requirements
interrogation). Verdict on the installed `speckit-*` family (GitHub Spec Kit): adopt the
WHAT-before-HOW *idea*; do NOT adopt its `.specify/` scaffold or merge its pipeline. Cursor's
"specs as prompts" finding makes design.md the highest-leverage artifact — spec quality matters
more than executor strength.

## 10. Test ladder (all under git, in `tests/`)

1. **Paper test** (~free): one session walks through the skill text playing every role, hunting
   contradictions, gaps, two-way-readable instructions.
2. **Smoke test:** trivial do-nothing task. Proves plumbing only: every role spawns, receives its
   packet, returns the fixed-format report; journal/STATUS/phase-state written. No traps.
3. **Fire drill:** tiny real disposable task (~3-4 steps) with PLANTED TRAPS, run in a scratch
   folder OUTSIDE this repo (so executors can't read the trap descriptions):
   - **Ambiguity trap:** one step spec deliberately silent on a real decision.
     Pass = executor STOPs and returns the question. Fail = it guesses.
   - **Audit trap:** one subtle spec violation seeded. Pass = auditor or frozen validation catches it.
   - **Resume drill:** kill the orchestrator mid-phase; fresh session must resume from files alone.
   - Also checked: all artifacts complete and current (no stale STATUS lines), all validations
     actually ran, zero executor design-decisions, metrics collected, token cost under a preset ceiling.
   - Failed trap → fix skill text, log lesson in field guide, re-drill (cheap, task is tiny).
4. **Real run:** Phase 1 of the English-learning app (§13). Fire-drill task should be a tiny slice
   of it (e.g., Hebrew–English word-list data model + quiz logic + tests, ~200 lines) — disposable
   if bad, head start if good.

## 11. Metrics (collected automatically into the journal, per step)

1. Validation passed on first try? (yes/no)
2. Retries count.
3. Escalations to a stronger model (count + which step — misclassification signal).
4. Tokens/cost per step, split by model.
5. Human interventions (count + reason).
6. Orchestrator context size at each phase boundary (§8).

## 12. Kill criterion (agreed with user — the anti-fluff contract)

After the English-app run, compare metrics against a plain plan-skill baseline. If the new skill
does not show a clear win (fewer bugs reaching the user, fewer interventions, or meaningfully
lower cost), SHRINK it to the parts that earned their keep (likely: auditor + file discipline)
or kill it. Solo-user honest ranking of expected value: (a) fresh-eyes auditor, (b) crash-safe
written record, (c) cheap-executor savings (modest on small features, big at scale).

## 13. First real test case (details TBD from user)

English-learning app for a young Hebrew-speaking English learner (family member).
User will provide details later. Pipeline: `grill-me` → `design.md` → this skill.

## 14. Deliverables of the build

1. `SKILL.md` — the skill itself (workshop copy here; installed to `~/.claude/skills/<name>/` when it passes tests).
2. Three prompt templates: executor packet, auditor, next-phase planner.
3. `tests/` — smoke-test task, fire-drill task + traps + pass/fail checklist, resume-drill procedure.
4. `STATUS.md` for this repo (photograph rule, mermaid).
5. Metrics + journal format spec (can live inside SKILL.md).

## 15. Open questions for the planning session

1. Skill name (working name: `orchestrated-planning`; shorter candidate: `oplan`).
2. Exact report format fields and the line cap number (proposed 30).
3. Field-guide line budget number (Cursor doesn't publish theirs; propose 40 lines).
4. Default model per role for v0.1 (proposal: orchestrator Opus, executor Sonnet — Haiku only
   after first metrics; auditor Sonnet; next-phase planner Opus).
5. Token-cost ceiling for the fire drill (proposal: set before running, record in tests/).

## 16. Communication rules (apply to every artifact and every session of this project)

- Simple-explainer style for the user; never skip data (saved in user memory: `simple-explainer-style`).
- Mermaid diagrams in .md files; ASCII in terminal chat.
- STATUS.md photograph rule (§7) applies to THIS repo's STATUS.md too.
