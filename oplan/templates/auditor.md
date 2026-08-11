# Spec auditor packet

> Send to a fresh reviewer after mechanical validation passes. Do not give chat history, the
> executor report, the full plan, or the journal.

Check whether Step {{step-id}} matches its sealed packet—nothing more and nothing less.

Read only:

1. `{{workspace}}/packets/{{step-id}}.md`
2. the scoped diff from `{{last-accepted-commit}}` over the packet's exhaustive file list

Create the diff yourself so it never travels through the harness. For new files, run
`git add -N <file>` before the scoped diff so they are visible without staging content. Do not
inspect unrelated code or infer intent beyond the packet.

Check each requirement, dependent decision ID, contract, boundary, and non-goal. Extra work is a
defect even if it appears useful.

Write the full result to `{{workspace}}/reviews/{{step-id}}-spec.md` and return at most 20 lines:

```text
VERDICT: match | mismatch
FINDINGS:
  - [missing|extra|contract|boundary|decision] <file>:<line> — <issue>
  - none
CONFIDENCE: high | low — <missing evidence, if any>
PLAIN: <=2 lines
```

`match` requires zero findings. Low confidence triggers one evidence-completion pass, never
speculation.
