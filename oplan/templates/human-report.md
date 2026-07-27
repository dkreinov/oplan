# Human report template — the plain-words side of a run

> **Orchestrator:** this is the only template you do not send to a subagent. You fill it in and
> **print it on screen**, and you append the marked parts to `<workspace>/briefing.md`. The rule
> behind it is `SKILL.md` §14: the human hears everything twice — plain words first, technical
> second — and never has to ask what just happened.
>
> Plain words = a bright twelve-year-old who has never seen this codebase can follow it. It does
> not mean less information. **Every number stays in.** **Bad news stays bad news.**

---

## A. The plan briefing — print before the first dispatch of every phase

Also append to `briefing.md`. Then **wait for the human's go-ahead** (skip the wait only in
continuous mode — print it either way).

```text
=== PLAN IN PLAIN WORDS ===
WHAT WE ARE BUILDING: {{2-3 sentences, no jargon — what will exist at the end that does not exist now}}
HOW MANY PHASES: {{N}}

PHASE 1 — {{plain title}}   [planned in full]
  What we do:  {{one line}}
  Why:         {{one line — what stays broken or missing if we skip it}}
  Done when:   {{one line — the check we agreed on, said in words}}
  Steps:
    1.1 {{what happens}} — because {{why this step exists}}
    1.2 {{...}}

PHASE 2 — {{plain title}}   [rough sketch — planned properly once Phase 1 is done]
  What we do:  {{one line}}
  Why:         {{one line}}
  Done when:   {{one line}}

WHAT WE ARE NOT DOING: {{the non-goals, in plain words — the things a reasonable person would
                        assume are included but are not}}
BIGGEST RISK: {{one line}} — we would notice it because {{one line}}
=== END ===
```

Rules:

- Every step bullet answers **what happens** *and* **why**. The *why* is the half the human cannot
  reconstruct by watching files change, and it is the half that lets them catch a wrong plan.
- Phases that are still skeletons get one line each, labelled as sketches. Never invent detail you
  have not planned — a confident-sounding sketch is a lie to the one person who cannot check it.
- Titles are plain too: not "Phase 2 — persistence layer" but "Phase 2 — remember the answers after
  the app is closed".

## B. The one-liner — print the moment each subagent returns

Screen only; the journal keeps the technical record. Print it as each agent comes back, never in a
batch at the end.

```text
[{{who, in plain words}}] {{what they did}} → {{what they found}}
```

Who, in plain words: **helper** (executor) · **checker** (auditor) · **plan reviewer** ·
**next planner** (next-phase planner) · **the manager (me)** (you).

```text
[helper] Wrote the login screen and the test that checks it → passed on the first try.
[checker] Compared the new code against the written instructions → matches, and nothing extra crept in.
[checker] Compared the new code against the instructions → it also renamed a file nobody asked to rename, so we are redoing the step.
[plan reviewer] Tried to poke holes in the plan → found 2: nobody said what the file is called, and step 3 needs something step 4 makes.
[next planner] Planned the next phase using only the written files → managed it, except it could not find where we decided the date format.
```

Cap: **2 lines per agent.** Say what was *discovered*, not only that it finished: "passed" is a
status, "the database already had that column" is a discovery.

## C. The two reports — print at every phase close

Plain first, technical second, never merged. Append the plain one to `briefing.md`; the technical
one is the §12 `PHASE CLOSED` block, which already lives in `journal.md`.

```text
=== PHASE {{N}} — PLAIN REPORT ===
WHAT WE SET OUT TO DO:   {{one line}}
WHAT WE ACTUALLY DID:    {{one bullet per step, plain words}}
WHAT WE FOUND OUT:       {{the discoveries — surprises, things that were not what we assumed,
                           anything that changes what we should do next}}
WHAT WENT WRONG:         {{failures, retries, what we did about them — or "nothing"}}
WHAT IT COST:            {{money and wall-clock time, in plain numbers}}
WHERE WE ARE NOW:        {{one line}}
WHAT HAPPENS NEXT:       {{one line, and what we need from you — or "nothing"}}
=== END PLAIN REPORT ===

=== PHASE {{N}} — TECHNICAL REPORT ===
{{the PHASE CLOSED metrics block from SKILL.md §12, verbatim:
  steps / first-try passes / escalations / interventions / cost split by model /
  orchestrator context / field guide fullness}}
ACCEPTANCE CRITERIA: {{each criterion — the command run, and pass/fail}}
ACCEPTED STEPS: {{step id — commit hash — validation first try yes/no}}
OPEN RISKS: {{or "none"}}
=== END TECHNICAL REPORT ===
```

`WHAT WE FOUND OUT` is what justifies the plain report existing. Everything else restates the plan;
this line carries information the human will find nowhere else. Build it from the `SURPRISES` and
`DEVIATIONS` lines the executors returned and from what the checkers said. If it is empty two
phases running, you are summarizing instead of reporting.

## D. The word list — rewrite jargon on the way out

When a term truly cannot be avoided (a real filename, a tool, a command), use it and define it
inline, once: `pytest (the tool that runs our tests)`.

| Instead of | Say |
|---|---|
| orchestrator | the manager (me) |
| executor / worker / subagent | a helper |
| auditor / fresh eyes | the checker — a second helper who never saw the work being done |
| plan reviewer | someone whose only job is to poke holes in the plan before we start |
| context / context window | memory — how much an agent can hold in its head at once |
| tokens | leave them out; give money and time instead |
| validation command | the test we agreed on before we started |
| frozen contract | a promise nobody is allowed to change |
| diff | the exact lines that changed |
| commit | a save point we can go back to |
| escalation | hand the same job to a stronger, more expensive helper |
| regression | something that used to work and now doesn't |
| refactor | rearrange the code without changing what it does |
| dependency | one thing has to exist before another can work |
| skeleton / stub | a rough sketch we fill in later |
| idempotent · deterministic · canonical · orthogonal | say what it actually does, in a sentence |

## E. The self-check before you print

1. Would a bright twelve-year-old follow every sentence?
2. Is every number from the technical version still present in the plain version?
3. Does every step say **why**, not just what?
4. Is anything that went wrong stated as plainly as what went right?
5. Did I say what we *found out*, not only what we *finished*?
