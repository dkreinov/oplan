# oplan — orchestrated planning & execution skill for Claude Code

One strong "manager" agent plans and decides everything; cheap workers execute one
clearly-written job each in a fresh context; separate fresh-eyed agents review the plan and
audit every result; all memory lives in files, so any agent — including the manager — can be
killed mid-run and replaced without losing the thread.

**Proven, not promised:** built in one day against a frozen evidence-based design, then pushed
through a four-rung test ladder — paper test (29 findings), smoke test, an automated fire drill
(process kills mid-step, injected scope-change "poison", cost ceiling), and a real production
run that shipped a live app in 5 autonomous phases with zero model escalations.

| Read this | To get |
|---|---|
| [`oplan/SKILL.md`](oplan/SKILL.md) | The skill itself — roles, hard rules, files, verification layers, metrics |
| [`oplan/templates/`](oplan/templates/) | The three packets: executor, auditor, next-phase planner |
| [`PROCESS.md`](PROCESS.md) | How it was planned, built, and audited — the reusable method |
| [`DESIGN.md`](DESIGN.md) | The frozen design + evidence base (Cursor, Anthropic, Cognition, AgentCARD) |
| [`STATUS.md`](STATUS.md) | Photograph of the project's current state |
| [`tests/`](tests/) | The test ladder: paper test, smoke test, fire drill — with real run records |

Install: copy `oplan/` to `~/.claude/skills/oplan/`.

The two lines the whole design orbits around:

> If you hit a question the spec doesn't answer, STOP and return the question. Never decide it yourself.

> Executors return a fixed report, max 30 lines. The orchestrator never reads a worker's transcript.
