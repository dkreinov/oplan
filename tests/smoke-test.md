# Smoke test — autonomous three-phase lifecycle

This test proves the v0.2 control loop, not code difficulty. Run it in a disposable repository
outside the skill source. Capture agent/task IDs and the main-thread transcript.

## Task

Invoke `oplan` without special “continuous mode” wording:

> Build a three-stage text pipeline. Phase 1 writes `input.txt` containing `hello world`.
> Phase 2 writes `upper.txt` by converting it to uppercase. Phase 3 writes `count.txt` containing
> the word count. Run all relevant checks.

## Binary pass checklist

### Thin harness and fresh roles

- [ ] Phase 1 was planned by a fresh phase planner, not the main thread.
- [ ] Phases 2 and 3 each used a different fresh phase planner.
- [ ] Every leaf used a new executor with no inherited chat.
- [ ] A fresh plan reviewer ran for every phase.
- [ ] A spec auditor ran after every leaf; a system reviewer ran at every phase gate.
- [ ] A fresh phase curator reconciled records before every close, including Phase 3.
- [ ] The main thread modified no product file and never emitted a feature-plan artifact itself.
- [ ] The main thread received no full transcript, plan, journal, code file, or diff.

### Autonomous continuation

- [ ] No final response or phase-boundary approval wait occurred between phases.
- [ ] Before every non-final phase report, `phase-state.md` already said
      `NEXT_ACTION: SPAWN_PHASE_PLANNER phase=<next> mode=new source=none`.
- [ ] At that transition `PHASE_CONTROL: none`; each new planner then installed a fresh versioned
      phase control before plan review.
- [ ] The only terminal state was `COMPLETE` after Phase 3 acceptance passed.
- [ ] Phase 3's sealed control had `next_phase: null`; held-out overall acceptance passed before `COMPLETE`.
- [ ] Every phase briefing and report was printed and appended to `briefing.md`.

### Packets and decisions

- [ ] Every executor received one sealed packet path, not a main-thread reconstruction.
- [ ] The harness read only the corresponding small control JSON and verified its packet/control seal.
- [ ] A pre/post worktree guard proved every executor changed only its declared write set.
- [ ] Each packet had an exhaustive write set, frozen validation, risk, non-goals, and decision IDs.
- [ ] Phase acceptance commands were absent from leaf packets.
- [ ] `grill-me` was not invoked because no material product decision was unresolved.

### Records and outcome

- [ ] All workspace artifacts and directories from `references/state-and-records.md` exist.
- [ ] `LAST_ACCEPTED` was always a verified full commit SHA; the initial Git baseline was valid.
- [ ] `phase-state.md` remained under 30 lines and always identified one executable `NEXT_ACTION`.
- [ ] `STATUS.md` contained only current state; `journal.md` and `briefing.md` were append-only.
- [ ] Every capped role return and executor question was persisted as a versioned artifact before state advanced.
- [ ] `input.txt`, `upper.txt`, and `count.txt` contain the exact expected values.
- [ ] `<python> oplan/scripts/validate_skill_contracts.py` passes in the skill source, resolving
      `<python>` as defined in `oplan/SKILL.md`.
- [ ] `validate_run.py <workspace> --phase <N> --seal` passes after plan-review `ship`.
- [ ] `validate_run.py <workspace> --phase <N> --require-sealed` passes before every dispatch,
      retry, audit, validation, and commit.

Any failed line means the lifecycle contract failed even if the three tiny output files are right.

## Additional decision-gate probe

Repeat with Phase 2 saying only “transform the text appropriately.” Pass when:

1. the planner inspects existing records and cannot resolve the intended transformation;
2. it classifies the blocker as `product`;
3. the installed `grill-me` skill, or the fallback, asks one question with a recommendation;
4. the answer becomes a `D-###` decision;
5. the blocked planner is discarded and a new clean planner writes the phase;
6. the answer is never handed directly to an executor.
