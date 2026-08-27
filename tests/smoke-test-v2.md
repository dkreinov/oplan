# Smoke test v2 — machine-graded lifecycle check

This is the machine-checkable companion to `tests/smoke-test.md`. That file's binary checklist
still applies and is not edited here; this file adds a scenario plus a `pytest` grader module so
the same lifecycle proof can be re-run and scored without a human reading a transcript. Nothing
here depends on `claude plugin eval`.

## Scenario

Run the same toy three-stage text pipeline as `tests/smoke-test.md`, under `depth_profile: fast`:

> Build a three-stage text pipeline. Phase 1 writes `input.txt` containing `hello world`.
> Phase 2 writes `upper.txt` by converting it to uppercase. Phase 3 writes `count.txt` containing
> the word count. Run all relevant checks.

Run it in a disposable repository outside the skill source, with `depth_profile: fast` recorded in
`baseline.md`. `tests/smoke-test.md`'s binary checklist grades the lifecycle by eye; this scenario
additionally produces a run workspace that the graders below can score mechanically.

## Running the graders

1. Point `OPLAN_SMOKE_WORKSPACE` at the run's `.oplan/<run>` workspace directory (the folder
   containing `journal.md`, `attempts/`, and `logs/`).
2. Optionally set `OPLAN_SMOKE_DISPATCH_CEILING` (default `40`),
   `OPLAN_SMOKE_SUITE_FLOOR` (default `2`), `OPLAN_SMOKE_SUITE_CEILING` (default `4`) and
   `OPLAN_SMOKE_COST_CEILING_USD` (default `40.0`) to override the defaults. Set the suite FLOOR
   deliberately — see below; leaving it at the default is what lets a missed gate pass unnoticed.
3. Run:

   ```text
   python -m pytest tests/test_smoke_grader.py -q
   ```

With `OPLAN_SMOKE_WORKSPACE` unset, `SmokeGraderLiveTests` skips every test and the suite stays
green — there is no dependency on a real run existing. `SmokeGraderFixtureTests` always runs: it
builds synthetic pass/fail workspaces in a temp directory and proves each grader function both
accepts a good fixture and rejects a bad one, so the graders themselves are proven correct even
with no live run on disk.

## Producing the cost JSON

Use the `ai-cost` skill to compute billing-grade dollars for the run's session logs, and write its
`total_usd` figure to a small JSON file, for example:

```json
{"total_usd": 4.5}
```

Point `OPLAN_SMOKE_COST_JSON` at that file's path before running the graders. If the variable is
unset, `grade_cost_ceiling` is simply skipped by `SmokeGraderLiveTests`; the fixture tests still
exercise `grade_cost_ceiling` directly against synthetic JSON, independent of `ai-cost`.

## Graders

| Grader function | What it asserts | `claude plugin eval` grader type |
|---|---|---|
| `grade_dispatch_count` | The count of `attempts/*.agent` files is at or below a ceiling | `count` |
| `grade_full_suite_runs` | **DISABLED — not fit for use.** See below | `count` |
| `grade_dispatch_timestamps` | Every `journal.md` line claiming to be a metrics line — opening with `dispatch ` followed by a number, or containing a `start=` field — fully matches the exact `dispatch <n> <role> start=<ISO-8601 UTC> end=<ISO-8601 UTC>` form | `regex` |
| `grade_cost_ceiling` | The `total_usd` figure in a JSON cost report is at or below a ceiling | `baseline` |

### `grade_full_suite_runs` is DISABLED — do not score a run with it

Two independent adversarial reviews found it reporting confidently wrong counts, in both
directions. Its live test is skipped, and `test_KNOWN_DEFECT_` tests pin the wrong behaviour so it
cannot be mistaken for correct. The demonstrated defects:

- **Over-counts.** A harness writing both `<gate>-overall.result` and `<gate>-overall-pytest.log` —
  a merge of two conventions already present in the four real workspaces — counts each gate twice.
- **Over-counts.** A leg running a *subset* of the suite (`2 passed, 77 deselected in 4.07s`) counts
  identically to an 18-minute full-suite run; the content check never verifies which command
  produced the output.
- **Under-counts, silently.** A gate log truncated by a wall-time kill, or carrying a single
  non-UTF-8 byte, is skipped with no signal at all.
- **The floor cannot be set correctly.** The formula below gives 8 for `.oplan/depth-profiles`,
  where the function counts 3.
- **The `.result` branch is dead** against three of four real workspaces, whose gates run
  `python -m pytest tests/ -q -p no:cacheprovider`, not the hardcoded command.

Root cause: it reverse-engineers run structure from filenames while the workspace already records
it. `control/phase-*.json` holds each gate's own `acceptance` and `overall_acceptance` command lists
plus the revision history. The replacement should derive the expected count from those records; a
benchmark harness under our own control should simply emit a machine-readable gate record. Both are
a redesign, deliberately not attempted as a third patch on a function that has already been wrong
twice.

The rest of this section describes what the disabled function currently does, not what it should do.

### How a full-suite run is counted, and why the floor matters more than the ceiling

Searching every `logs/` file for the command text cannot see a phase gate at all: phase-acceptance
logs hold pytest **output only**, and the harness never echoes the command into them. That was this
grader's original defect.

`grade_full_suite_runs` instead counts distinct gate runs, deduplicated by log stem so a gate that
wrote both `<stem>.log` and `<stem>.result` counts once. A gate is recognised two ways:

- a `.result` line `"<exit code>  <command>"` whose command matches. This is the only shape any
  contract pins, and only for the final gate (`state-and-records.md` section 5).
- a `.log` whose **stem** carries an acceptance or overall marker **and** whose **content** reports
  a suite result. Both are required: the name alone would count a gate's `validate_run.py` and
  contract-validator legs, which are not suite runs, and the content alone would count leaf
  validation logs, which are also not suite runs.

**No contract pins a phase-acceptance log path.** The four real workspaces under `.oplan/` use four
different schemes — `phase-1-acceptance.log`, `phase-1-acceptance2-pytest.log`, `acc-pytest.log`,
`overall-pytest.log`. The stem pattern is the empirical union of those, and a fifth scheme would
defeat it.

That is why there is a **floor**, and it is the more important of the two bounds. A ceiling alone
forgives a missed gate silently — an unrecognised run is always "at or below" the ceiling, so one
recognised run would excuse any number of missed ones and the grader would report a confidently
wrong benchmark metric. The floor turns under-detection into a loud failure. Set
`OPLAN_SMOKE_SUITE_FLOOR` to the number of gate runs the run actually spent: one per phase-control
revision that reached acceptance, plus one for the final gate.

A nonzero exit code still counts. A failed gate run consumed the same wall-clock and dollars, and
filtering on success would bias the benchmark toward whichever harness version fails more.

The count is graded against a range rather than an exact number, because no exact number is right
for more than one task shape: a run of N phases spends N phase-gate runs plus one final-gate run,
and a repaired phase re-runs its own gate. Read the reported count as the metric.

### Grading a workspace that predates a rule

A grader fails when the run genuinely lacks what it grades, and that is correct rather than a
grader defect. `grade_dispatch_timestamps` fails on any workspace produced by a harness that does
not yet emit D-005 dispatch lines — including `.oplan/speed-run`, the run that introduced the rule,
whose own harness ran the frozen previous contract. Do not treat that failure as a grader bug and
do not soften the grader to hide it.

`claude plugin eval` is early access and is not enabled on this account. Nothing in this
repository, including this test file and its grader module, depends on `claude plugin eval`; the
grader type column above is documentation only, recording how each pure grader function would port
to a future `claude plugin eval` suite.

## What this does not replace

`tests/fire-drill.md` and `tests/paper-test.md` are not edited or superseded by this file. The fire
drill still proves escalation, resume, and cost discipline under adversarial conditions; the paper
test still proves the skill text is followable. This file only makes the smoke test's lifecycle
proof machine-gradeable.
