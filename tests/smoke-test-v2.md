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
2. Optionally set `OPLAN_SMOKE_DISPATCH_CEILING` (default `40`) and
   `OPLAN_SMOKE_COST_CEILING_USD` (default `40.0`) to override the default ceilings.
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
| `grade_full_suite_runs` | The full-suite command appears in `logs/` files exactly the expected number of times (2) | `regex`/`count` |
| `grade_dispatch_timestamps` | Every `journal.md` line starting with `dispatch ` fully matches the exact `dispatch <n> <role> start=<ISO-8601 UTC> end=<ISO-8601 UTC>` form | `regex` |
| `grade_cost_ceiling` | The `total_usd` figure in a JSON cost report is at or below a ceiling | `baseline` |

`claude plugin eval` is early access and is not enabled on this account. Nothing in this
repository, including this test file and its grader module, depends on `claude plugin eval`; the
grader type column above is documentation only, recording how each pure grader function would port
to a future `claude plugin eval` suite.

## What this does not replace

`tests/fire-drill.md` and `tests/paper-test.md` are not edited or superseded by this file. The fire
drill still proves escalation, resume, and cost discipline under adversarial conditions; the paper
test still proves the skill text is followable. This file only makes the smoke test's lifecycle
proof machine-gradeable.
