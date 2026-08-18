# Evidence-completion reviewer packet

> Send to one fresh isolated reviewer only after a spec audit returns `match` with low confidence.
> This role may write only its versioned review artifact.

Read the sealed packet/control, the original spec-audit artifact, and only the missing evidence
named by that audit. Source the diff by mode:

- under `commit_mode: auto`, inspect the scoped candidate diff from `LAST_ACCEPTED` over the
  control record's write set. This branch names `LAST_ACCEPTED` as its only diff base and must not
  mention a snapshot;
- under `commit_mode: none`, inspect the same source the spec auditor used — the pre-attempt snapshot-to-worktree diff between the sidecar copies at `{{attempt-snapshot}}.files/` and the current worktree — plus the verified cumulative `attempts/accepted-state.json`, never a commit diff that cannot represent uncommitted accepted work.

Do not broaden into a system review, change product files, or reinterpret intent.

Write `{{workspace}}/reviews/{{step-id}}-evidence-a{{attempt}}.md` with evidence inspected and the
confidence conclusion. Return at most 15 lines:

```text
VERDICT: high | still-low
EVIDENCE_PATH: <versioned review path>
FOUND: <=5 lines
PLAIN: <=2 lines
```

`high` continues through the normal risk branch. `still-low` blocks after reverting the candidate.
