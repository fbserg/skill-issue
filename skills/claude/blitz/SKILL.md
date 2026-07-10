---
name: blitz
description: Execution-posture nudge for multi-part work — fast, parallel, adversarial. Use when the user invokes /blitz, says "run this fast and adversarial", or hands over a multi-lane task without a more specific pipeline (/issue, /resolve-issue, /epic-plan) fitting. Not a pipeline; just the standing reminders.
---

You're the orchestrator; you don't implement. Posture:

- **Fan out now.** Independent lanes run in parallel worktrees (`claude --worktree` / `isolation: 'worktree'`), one lane per disjoint file set; serialize only genuine overlap. Don't do sequentially what has no dependency.
- **Adversarial review before believing anything.** Distinct lenses, role-locked to refute; verify claims against the repo, not rhetoric. Applies to plans, diffs, and your own conclusions.
- **Fast through gates.** No re-confirming between phases; push each lane to done (commit, PR, human merges). Stop only for real scope changes or destruction.

<!-- accreting reminders — add one line each time the user has to repeat something -->
