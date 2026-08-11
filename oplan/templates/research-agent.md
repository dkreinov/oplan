# Repository-fact research packet

> Send to a fresh isolated research agent. It may write only the named evidence artifact.

Resolve exactly the repository/documentation question in `{{blocker_path}}`. Inspect authoritative
project files and named documentation. Do not make product or implementation decisions and do not
edit product code, plans, packets, or design records.

Write evidence to `{{workspace}}/research/{{id}}.md` with the question, inspected paths, findings,
direct evidence, remaining uncertainty, and timestamp. Return at most 15 lines:

```text
STATUS: evidence | not-found | authority
EVIDENCE_PATH: <path>
ANSWER: <=5 lines or none
SOURCES: <=5 paths or none
PLAIN: <=2 lines
```

`not-found` receives one fresh retry at the next recorded research tier. A second `not-found`
blocks the run. `authority` routes to the persisted human-decision gate.
