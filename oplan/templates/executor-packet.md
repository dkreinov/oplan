# Executor packet

> The phase planner fills every slot and writes the result to `packets/<step-id>.md`. After plan
> review ships it, the harness seals and dispatches it unchanged to a new isolated inexpensive worker.

You are executing one leaf of a larger task tree. Do not plan beyond this packet.

## Leaf

**Step:** {{step-id}} — {{title}}

**Goal:** {{what must be true}}

**Files you may create or modify — exhaustive:**

```text
{{paths}}
```

**Commands:** {{commands or none}}

**Frozen validation:**

```text
{{exact mechanical command}}
```

**Dependent decisions:** {{D-### list with exact relevant statements}}

**Contracts:** {{names, schemas, formats, APIs, invariants}}

**Non-goals:** {{reasonable adjacent work that is excluded}}

**Risk:** {{low|high}} — {{reason}}

**Structural warning threshold:** flag a touched file that becomes difficult to transport,
understand, test, or merge; do not refactor it unless this packet explicitly asks.

## Boundaries

- Touch only the listed files.
- Resolve all listed paths and run every command from the Git worktree root.
- Do not alter validation or pre-existing tests unless this leaf explicitly owns those tests.
- Do not refactor, fix adjacent problems, add speculative flexibility, or implement unrequested
  core changes.
- If a necessary value, name, format, default, behavior, or file is not decided, stop.
- If a dependent decision conflicts with code reality, stop.

> If you hit a question the packet does not answer, STOP and return the question. Never decide it yourself.

You may propose structural or core work without implementing it. This protects the project from
both megafiles and fear of necessary core changes.

## Local field guide

```text
{{field-guide/index.md verbatim}}
```

## Budgets

- Retry cycles: {{N}}
- Wall-time bound: {{wall_time_minutes}} minutes — the harness enforces this as a cancellation
  boundary. It is not a deadline you must estimate or meet; do not rush, cut corners, or
  self-abort because of it.
- Read only the listed files, direct dependencies needed to edit them, and named decisions.

## Return exactly — maximum 32 lines

```text
STATUS: done | failed | stopped-with-question
DID: <=5 lines — changes by file
VALIDATION: exact command + observed result
FAILURE_CAUSE: <=3 lines when failed, otherwise none
SURPRISES: <=3 lines or none
STRUCTURAL_FLAGS: megafile|core-change|duplication|none — <=3 lines
CHANGE_PROPOSAL: <=3 lines or none; not implemented outside the packet
DEVIATIONS: <=3 mechanical differences or none
QUESTION: only when stopped — exact missing decision
PLAIN: <=2 lines for a non-technical human
METRICS: retries=N, validation_first_try=yes|no
```

Leave no partial edits when stopping with a question.
