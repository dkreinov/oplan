# Experiment design — measuring what oplan actually buys

Status: DRAFT for review. Nothing has been run.

## 1. The question

Does oplan's orchestration make a coding agent better, and at what cost?

"Better" has to be split, because the answers may differ and the field's evidence says they do:

- **Accuracy** — does the produced code pass tests it never saw?
- **Cost** — dollars and tokens per attempt, and per *success*.
- **Speed** — wall-clock.
- **Reliability** — does it succeed *consistently*, which is a different question from
  whether it can succeed at all.

## 2. Why this needs designing rather than just running

Three findings from the research pass make the naive version of this experiment worthless.

**Three trials on one task cannot produce a result.** A perfect 0/3 versus 3/3 split gives Fisher
exact two-sided p = 0.10. The unit of replication is the TASK, not the trial. Paired designs on the
same task set need roughly 28–50 tasks; unpaired binary needs ~300 per arm.

**Binary pass/fail has near-zero discriminating power here.** FeatureBench's own leaderboard shows
one model under two scaffolds scoring 67.2 versus 59.1 on the graded metric and **20.0 versus 20.0**
on binary. Grade with the fraction of held-out tests passing, never with all-or-nothing.

**Published evidence points against the thesis.** METR compared Claude Code (which spawns sub-agents)
against a plain single-agent scaffold on Opus 4.5: Claude Code won in **50.7%** of bootstrap samples,
a coin flip. A separate 36-combination study found higher reasoning effort produced equal or lower
accuracy in 21 of them, which contradicts `oplan/references/model-policy.md` directly. This
experiment must be able to return "orchestration does not help", or it is not an experiment.

The counterweight, and the reason to run it anyway: METR measured Opus 4.6 at p50 = 719 minutes but
**p80 = 70 minutes** — a 10x reliability gap. Reliability, not capability, is the binding constraint,
and verification gates are the intervention that plausibly targets it. That makes **variance
reduction the effect most worth looking for**, and it is invisible to a mean pass rate.

## 3. Arms

| # | Arm | What it isolates |
|---|---|---|
| A | No skill — plain Claude Code | **The control.** Does any scaffolding help at all? |
| B | `careful-change` | Cheapest structure: one agent, one independent review |
| C | oplan @ `457f6b9`, `fast` | Pre-speed-run oplan |
| D | oplan @ `0d04570`, `fast` | Post-speed-run oplan — the A/B for the last run |
| E | oplan @ `0d04570`, `standard` | Depth-profile axis: more review |
| F | oplan @ `0d04570`, `paranoid` | Depth-profile axis: maximum review |

**Arm A is not optional.** Without it, every comparison is between flavours of scaffolding and
cannot answer whether the scaffolding earns its cost. The METR result makes this the single most
likely place to get a surprising answer.

**Arm B will legitimately refuse some tasks.** `careful-change`'s own escalation rules tell it to
stop when work has phases or exceeds one sitting — and the candidate tasks do. A refusal is a valid
outcome and must be recorded as `declined`, distinct from `failed`. An arm that knows its own limits
is not the same as an arm that fails.

**C versus D is a bundle, not a clean axis.** The speed run changed five things at once. C vs D
measures "old oplan vs new oplan" and nothing finer. This must be stated in any result; it cannot be
fixed after the fact.

## 4. Tasks

Primary corpus: **jsonargparse** (MIT, ~10 MB, suite 1m45s on the target host with
`--ignore=jsonargparse_tests/test_shtab.py`).

Seed task: **PR #961**, "Generation of JSON schemas for parsers", merged 2026-08-24.

- 5 source modules changed; `jsonargparse/_completions_jsonschema.py` is new at 547 lines.
- Held-out tests: `jsonargparse_tests/test_completions_jsonschema.py`, new, 1076 lines.
- **88 of 91 tests fail** at `72c4885f58~1` with only the test file restored — verified, not assumed.
- The PR body is a ~400-word behavioural spec that names no file or function. Usable verbatim.

Growth: ~17 further commits of the same shape in jsonargparse during 2026. `lark` PR #1592 is a
verified second instance but that repo has only ~13 qualifying commits in its entire history, so it
seeds a pilot and then dead-ends.

**Task selection rule:** merge date after the model's training cutoff, AND the PR must not have been
authored by a coding agent. The second half is not paranoia — many recent `sqlglot` PRs are titled
`[CLAUDE]` or `[CODEX]` and that repo ships `AGENTS.md` and `CLAUDE.md`. Benchmarking a harness
against a task another agent already solved and published measures the wrong thing.

## 5. Metrics

**Accuracy (primary):** fraction of the held-out F2P tests passing. Graded, never binary. Report the
count, not just the fraction.

**Reliability:** `pass^k` — the probability that *all* k trials succeed. This is the only common
metric that punishes "run it until it works", and it targets the p50/p80 gap directly. Co-primary
with accuracy.

**Cost:** dollars via the `ai-cost` skill, which already does message-id dedup and counts sidechain
sub-agents. Report tokens disaggregated — uncached input, cache read, cache write, output — plus the
pricing-snapshot date, so dollars stay recomputable. Note the direction trap: Anthropic reports
`input_tokens` *exclusive* of cache reads; getting this backwards is a silent ~10x error.

**Cost-per-success:** `cost / pass_rate`. Not a standard metric — the field has none — but it is the
number that answers "is this worth it".

**Speed:** wall-clock, and separately the **timeout-vs-genuine-failure split**. In Long-Horizon
Terminal-Bench, 79% of unresolved runs were timeouts rather than self-stops. A harness that is merely
slower will look less accurate unless this is reported.

**Process metrics (from the existing graders):** dispatch count via `grade_dispatch_count`, and
D-005 line well-formedness via `grade_dispatch_timestamps`. **NOT** full-suite-run count —
`grade_full_suite_runs` is disabled as not fit for use; see `tests/smoke-test-v2.md`.

**Scope discipline:** diff size against the reference commit, and files touched outside the expected
set. Catches the failure mode where an arm buys a pass with scope creep.

## 6. Integrity controls

**Scrub git history before every trial.** Poolside raised a model ~20 points on SWE-Bench Pro over
one weekend purely by mining unpruned history. Required: `git log --all ^HEAD` must be empty; remove
remote-tracking branches (they survive `git reset --hard`), tags, the reflog, and the remote itself
so `git pull` fails. Branch names alone can reveal the fix.

**Block network egress during the run**, or the agent can fetch the upstream repo or a released
package containing the reference implementation.

**Audit the revert for leftovers** before scaling: dangling imports, orphaned config keys, docs or
CHANGELOG entries describing the removed feature, type stubs. A SWE-bench issue documents a leaked
`chore(release)` commit whose diff was the CHANGELOG. Hand-audit the first 2–3 tasks.

**Apply the agent's patch first, the test patch second**, and reset all test files after the run.
Score *outside* the agent's sandbox, parsing structured output (junit-xml), never regex over stdout
the agent could forge. A ~10-line `conftest.py` using pytest hooks scores 100% on SWE-bench Verified.

**Expect flawed held-out tests.** OpenAI's audit of 138 SWE-bench Verified problems found 59.4% had
material issues — 35.5% narrow tests enforcing implementation details, 18.8% testing behaviour the
prompt never described. Read the held-out tests of every task before it enters the corpus.

## 7. Staging, because the full matrix is unaffordable

6 arms x 17 tasks x 3 trials = 306 runs. At roughly 1M tokens each that is ~300M tokens. Not viable.

**Stage 0 — plumbing (target: ~5 runs, one task, one trial per arm).**
One task, all six arms, one trial. Purpose is *not* to compare anything: it is to prove the revert
holds, the scrub works, the graders capture what we think, and to get real per-arm cost so stage 1
can be priced. Any comparison drawn from stage 0 is anecdote and must be labelled as such.

**Stage 1 — one axis, powered enough to see a large effect.**
Pick the single most valuable comparison from stage 0's cost data — most likely **A vs D** (no skill
vs current oplan), because the control is where the surprising answer lives. Paired design over
~15–20 tasks, 3 trials each. This detects a large effect, not a subtle one; say so.

**Stage 2 — only if stage 1 shows something.**
Add arms or tasks against the measured effect size. If stage 1's graded difference is under ~3
points, the honest conclusion is that the effect cannot be afforded to measure, and the decision
should be made on cost and wall-clock alone, where the signal is already clean and cheap.

**Kill criteria.** Stop and report if stage 0 exceeds ~10M tokens, if the revert or scrub cannot be
made reliable on the seed task, or if held-out tests prove to be testing implementation details
rather than behaviour.

## 8. Open questions for the human

1. **Does arm A (no skill) go in?** Recommended yes; it is the control and the likeliest source of an
   uncomfortable answer.
2. **Is `careful-change` an arm, or the tool that plans this?** Read here as an arm.
3. **Is a null result acceptable?** If "oplan does not beat plain Claude Code on accuracy" is not an
   acceptable output, this experiment should not be run, because it is a reachable outcome.
4. **Local-only, or scale later?** jsonargparse needs no Docker and no Linux. FeatureBench — 200
   curated tasks of this exact shape — needs both, plus roughly $1.5–3K for a pilot.

## 9. What this design does not cover

- Nothing here is built. There is no adapter, no runner, no scrub script.
- Arm A's prompt shape is undecided: plain Claude Code needs *some* instruction, and how much
  scaffolding that implicitly grants is itself a confound.
- Trial-to-trial variance on this corpus is unmeasured; the 3-trial figure is borrowed from other
  benchmarks, not derived from ours.
- `grade_full_suite_runs` stays disabled. Restoring it is a prerequisite for reporting full-suite-run
  counts as a benchmark metric, and it is a redesign, not a patch.
