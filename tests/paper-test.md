# Paper test — read the skill as if you had to obey it

**Rung 2 of the test ladder.** Costs almost nothing, catches the defects that would otherwise cost
a whole drill run to discover. Run it after any change to `oplan/SKILL.md` or the templates.

**What it proves:** that the text can actually be followed — by each role, with only what that
role is given. It cannot prove the machinery works (that is the smoke test) or that the rules hold
under pressure (that is the fire drill).

---

## Procedure

Use fresh eyes: a subagent, or a session that did not write the text. The author cannot see his
own two-way-readable sentence — he knows which way he meant it.

Read `oplan/SKILL.md`, every directly linked template/reference, and the contract validator. Then
walk through the text **playing each role in turn**, writing down what you could and could not do:

1. **Harness** — can you follow only `phase-state.md` and capped reports without planning,
   implementing, or reading full artifacts? Does every nonterminal state have one next action?
2. **Phase planner** — can you plan Phase 1 and later phases from files, resolve implementation
   choices, classify true blockers, and write complete sealed packets?
3. **Plan reviewer** — can you detect decision overlap, coarse decomposition, intent drift, and
   weak phase acceptance from artifacts alone?
4. **Executor** — read the packet as if it were your entire world. What would you be forced to
   guess? Which instruction reads two ways? Do any two rules in the same packet conflict?
5. **Spec auditor** — with only packet + scoped diff, can you always produce a legal verdict?
6. **System reviewer** — can you inspect integrated behavior without duplicating the spec lens?
7. **Grill gate** — does it invoke the human only for material product/authority decisions and
   then force a clean replan?
8. **Researcher and curator** — can each act from named artifacts, write only owned records, and
   return a verdict with one deterministic transition?

Then hunt these five defect classes across every file:

| Class | What it looks like |
|---|---|
| CONTRADICTION | Two statements that cannot both be obeyed |
| GAP | A role needs information no rule delivers; or a file is read but nothing is specified to write it |
| TWO-WAY | An instruction a careful reader could reasonably read two different ways |
| CONTRACT DRIFT | The report format, escalation sentence, field-guide budget, or tier ladder stated differently in different places |
| DEAD RULE | A rule that is never actionable, or a metric nobody is told to produce |

A second, independent pass is worth its cost: check the built files against the frozen design
document section by section, and report both the gaps **and** the sections that are faithfully
implemented — visible coverage is what makes "no findings" believable.

## Output format

For each finding: **severity** (blocker / should-fix / nit) · **class** · **file + section** ·
**what is wrong** (one sentence, quoting the offending text) · **suggested fix** (one minimal
wording change). Most severe first. Roles that walked through cleanly get one line each saying so
— do not invent findings to look thorough, and do not comment on style unless it creates
ambiguity.

## Pass criteria

- [ ] Every role walkthrough completed, with its outcome written down
- [ ] Zero unresolved blockers
- [ ] Every should-fix either applied or explicitly accepted with a reason
- [ ] The frozen contracts (report format, escalation sentence, budget, ladder) are identical everywhere they appear
- [ ] A finding that is really a **design-level** contradiction is escalated to the human, not patched silently — `DESIGN.md` is frozen
- [ ] A successful phase cannot produce a final response while a later phase exists
- [ ] Phase 1 and later phases use the same clean-planner path
- [ ] `python3 oplan/scripts/validate_skill_contracts.py` passes

## Runs

### 2026-07-23 — first paper test (build of v0.1)

Two fresh-context Opus subagents: one role-play walkthrough, one conformance check against
`DESIGN.md`. **21 + 8 findings; 6 blockers.** All applied. The load-bearing ones:

| Finding | Fix applied |
|---|---|
| The plan itself lived only in the orchestrator's context — violating the crash-only rule and making mid-phase resume impossible | Added `plan.md` as a fifth workspace file |
| The plan reviewer had no packet and no output format anywhere | Defined inline in `SKILL.md` §10 (not a fourth template — `DESIGN.md` §14.2 freezes the count at three) |
| The journal recorded metrics but never *what was built* — so the next-phase planner had no account of the work | Added `did` / `surprises` / `deviations` to the per-step journal block |
| "Field guide injected into EVERY agent packet" contradicted the auditor's diff-and-spec-only isolation | Excluded the auditor explicitly, in both places |
| No terminal failure state — re-dispatch and escalation loops had no end | Added four stop conditions (§7) and a `STOP the run` node in the flowchart |
| "The diff for this step" was not obtainable — an unscoped diff includes the orchestrator's own writes | Commit on accept; audited diff scoped by the step's file list |
| Rejected work was never reverted before re-dispatch, so an `extra` finding could never be cleared | Revert-to-last-accepted-commit before every re-dispatch |
| Token/cost/context metrics had no producer, but both test files grade on them | Added a sourcing rule: read the harness readout, else write `unavailable` — never estimate |

Smaller fixes: escalation timing ambiguity in the flowchart, "clean state" defined, `phase-state.md`
given a schema, `match` + `CONFIDENCE: low` handling, escalation defined on the model ladder rather
than the tier list, planning checklist extended to every packet slot plus phase acceptance
criteria, `BLOCKERS`/`RECORD GAPS` given a consumer, `DEVIATIONS` narrowed to mechanical-only,
retry limit separated from free validation runs, workspace path defined, STATUS.md line budget.
