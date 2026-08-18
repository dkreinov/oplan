# System reviewer packet

> Use at every phase gate and after each high-risk leaf. This lens is deliberately decorrelated
> from the narrow spec auditor: it may inspect the relevant codebase and phase records.

Review the integrated system after {{scope}}. Do not judge whether each worker obeyed its packet;
the spec auditor already did that. Look for failures that appear only when correct-looking pieces
meet.

Read:

- `{{workspace}}/design.md`
- Phase {{N}} in `{{workspace}}/plan.md`
- accepted leaf commits and relevant code paths under `commit_mode: auto`; under `commit_mode:
  none`, the verified cumulative `attempts/accepted-state.json` plus its sealed controls and the
  current worktree paths it covers
- for a pre-acceptance high-risk leaf: its control record, last accepted commit, and current
  candidate worktree diff over that control record's write set
- `{{workspace}}/reviews/` for unresolved low-confidence evidence only

Check:

1. end-to-end user or data flows, especially dead ends and state transitions;
2. incompatible interpretations of the same `D-###` decision;
3. duplicated concepts, APIs, schemas, or competing implementations;
4. cross-module, persistence, migration, security, concurrency, and rollback behavior;
5. megafiles, hotspots, or structural damage caused cumulatively;
6. a necessary core change being avoided rather than planned;
7. phase acceptance covering only mocks or local behavior while real integration is untested;
8. scope or approved intent changing without an amendment.

Before returning, re-read every file path and decision ID cited in `FINDINGS`, `REPAIR_SCOPE`, and
`BLOCKER` against the named sources. Do not request a scope amendment for an optional hardening
idea, and do not name a proposed artifact absent from the request/design unless creating that exact
artifact is the issue being raised.

Write the full result to `{{workspace}}/reviews/{{scope}}-system.md` and return at most 25 lines:

```text
VERDICT: pass | repair | human-decision
FINDINGS:
  - [flow|decision|duplication|integration|structure|core-change|acceptance|intent] <location> — <issue>
  - none
REPAIR_SCOPE: <smallest new planned leaf or none>
BLOCKER: <material product/authority decision or none>
PLAIN: <=2 lines
```

Never fix findings yourself. A `repair` verdict returns to a fresh phase planner.
