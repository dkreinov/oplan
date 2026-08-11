# Evidence-completion reviewer packet

> Send to one fresh isolated reviewer only after a spec audit returns `match` with low confidence.
> This role may write only its versioned review artifact.

Read the sealed packet/control, the original spec-audit artifact, the scoped candidate diff from
`LAST_ACCEPTED`, and only the missing evidence named by that audit. Do not broaden into a system
review, change product files, or reinterpret intent.

Write `{{workspace}}/reviews/{{step-id}}-evidence-a{{attempt}}.md` with evidence inspected and the
confidence conclusion. Return at most 15 lines:

```text
VERDICT: high | still-low
EVIDENCE_PATH: <versioned review path>
FOUND: <=5 lines
PLAIN: <=2 lines
```

`high` continues through the normal risk branch. `still-low` blocks after reverting the candidate.
