# Smoke test — does the plumbing move?

**What this proves:** every role spawns, every role receives its packet, every role returns its
fixed-format output, and all four files get written. **Nothing else.** There are no traps here and
no hard thinking — a smoke test that a healthy run can fail is a bad smoke test. Traps live in
`fire-drill.md`.

**Cost:** small (a handful of cheap dispatches). No preset ceiling.
**Run it:** in a scratch folder outside this repo, e.g. `~/scratch/oplan-smoke/`. Delete it after.

---

## Setup

```bash
mkdir -p ~/scratch/oplan-smoke && cd ~/scratch/oplan-smoke && git init
```

Start a fresh session in that folder and invoke the skill with the task brief below. The
orchestrator's workspace files (`journal.md`, `STATUS.md`, `phase-state.md`,
`field-guide/index.md`) go in that folder too.

## The task brief (paste this to the orchestrator)

> Run this with the oplan skill. Two phases, deliberately trivial — I am testing the machinery,
> not the work.
>
> **Phase 1 — "greeting":** create `greeting.txt` containing exactly one line: `hello world`.
> Then create `count.txt` containing exactly the number of words in `greeting.txt`.
>
> **Phase 2 — "shout":** create `shout.txt` containing the contents of `greeting.txt` in
> upper case.
>
> There is no `design.md`. Nothing here is a trick — if a step seems ambiguous, that is a real
> finding worth telling me about, but I do not expect one.

Suggested frozen validation commands (the orchestrator may write its own, but they must be this
mechanical):

```bash
# step 1.1
[ "$(cat greeting.txt)" = "hello world" ]
# step 1.2
[ "$(cat count.txt)" = "2" ]
# step 2.1
[ "$(cat shout.txt)" = "HELLO WORLD" ]
```

## Pass checklist

Every line is binary. Any `no` = smoke test failed; fix the skill text before moving to the fire
drill.

### Roles spawned and answered

- [ ] A **plan reviewer** subagent ran on the Phase 1 plan before any execution, and returned findings (or an explicit "no findings")
- [ ] Each step was executed by an **executor** subagent in a fresh context — one at a time, never two at once
- [ ] Every executor returned the report format from `SKILL.md` §9: STATUS / DID / VALIDATION / SURPRISES / DEVIATIONS / METRICS present, ≤30 lines
- [ ] An **auditor** subagent ran after every step and returned VERDICT + FINDINGS + CONFIDENCE
- [ ] A **next-phase planner** subagent planned Phase 2, and the orchestrator reviewed its plan

### Packets were well-formed

- [ ] Each executor packet contained all 7 elements (§9), including the field guide and the escalation rule verbatim
- [ ] The auditor packet contained ONLY the diff and the step spec — no journal, no plan, no executor report
- [ ] The next-phase planner packet contained file paths, not pasted file contents

### Files exist and follow their rules

- [ ] `journal.md` exists, is append-only (earlier entries unmodified), and has one metrics block per accepted step
- [ ] `journal.md` has a `PHASE 1 CLOSED` block with cost, orchestrator context size, and field-guide fullness
- [ ] `STATUS.md` exists, is written in plain language, and contains a mermaid diagram
- [ ] `STATUS.md` was **rewritten** at each update — no appended history, no stale line (e.g. no "not started" for a finished step)
- [ ] `phase-state.md` was updated after every step acceptance, not just at the end
- [ ] `field-guide/index.md` exists (may be nearly empty — a trivial task teaches few lessons) and is ≤40 lines

### The orchestrator did its own job

- [ ] The orchestrator re-ran each frozen validation command itself, in a clean state — not just trusted the executor's VALIDATION line
- [ ] Executors ran on the WORKER tier; the orchestrator stayed on PLANNER (check the journal's per-step `tier:` field)
- [ ] Zero design decisions were made by an executor (no DEVIATIONS entries that pick an unspecified value)
- [ ] The run paused at the Phase 1 → Phase 2 boundary and printed the handoff prompt (unless the human explicitly chose all-phases-autonomous)

### The actual (trivial) work

- [ ] `greeting.txt`, `count.txt`, `shout.txt` all exist with the exact expected contents
- [ ] All three validation commands pass when run by hand afterwards

## Recording the result

Append to this file under a `## Runs` heading: date, pass/fail, and any checklist line that
failed with a one-line note on what was fixed. A failed smoke test means the skill text is wrong —
fix `oplan/SKILL.md` or the templates, note the lesson, and re-run. Re-running is cheap; that is
the point of a trivial task.

## Runs

_(none yet — this file was written before the first run)_
