# Repair-lane drill — seeded-defect micro-drill for the cheap repair lane

**What this proves (that the smoke test cannot):** that a bounded-mechanical defect in an accepted
leaf's candidate is fixed through the cheap repair lane — one fresh executor against the already
sealed packet and control — rather than through a full repair planner, a new phase-control
revision, or a new seal.

Run this after the smoke-test-v2 scenario (`tests/smoke-test-v2.md`) has produced an accepted leaf.

## Setup

1. Run the smoke-test-v2 scenario through at least one accepted leaf.
2. Seed exactly one bounded-mechanical defect into that leaf's accepted candidate: a single wrong
   sentence, or a single wrong literal, whose correct form the sealed packet already determines.
   For example, if the packet's frozen validation names an exact expected file content, replace one
   character of that content in the candidate file.
3. Trigger the normal review path (spec auditor, or the leaf reviewer pair at high risk) over the
   seeded candidate.

## Pass/fail checklist

- [ ] The reviewer returns a blocking verdict with `FINDING_CLASS: bounded-mechanical` for the
      seeded defect.
- [ ] The reviewer's `FIX_CONTROL` names exactly one already-sealed leaf control — the same leaf
      whose candidate was seeded.
- [ ] The defect is resolved within three dispatches total, counted from the seeded review onward.
- [ ] No repair planner was spawned.
- [ ] No new phase-control revision was written.
- [ ] No new seal was written.
- [ ] The resolving dispatch was a fresh executor against the original sealed packet and control,
      with the review artifact path given as its fix source.

Any failed line means the cheap repair lane did not behave as designed, even if the defect was
eventually fixed some other way.

## When a line fails

A failed line here means the repair-lane behavior in `oplan/references/state-and-records.md` needs
a wording fix, not that the drill should be made easier. Fix the wording, re-seed a fresh defect of
the same kind, and re-run.
