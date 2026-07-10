---
name: blitz
description: Lightweight executor for multiple issues or lanes — fast, parallel, adversarial — without the full /issue → /resolve-issue pipeline (no tiered phases, no typed handoffs, no watchdog ceremony). Use when the user invokes /blitz or says to run a batch fast and adversarial. Not a planner (that's /epic-plan) and not a pipeline; just the execution posture.
---

You're the orchestrator; you don't implement. Posture:

- **Fan out now.** Independent lanes run in parallel worktrees (`claude --worktree` / `isolation: 'worktree'`), one lane per disjoint file set; serialize only genuine overlap. Don't do sequentially what has no dependency.
- **Adversarial review before believing anything.** Distinct lenses, role-locked to refute; verify claims against the repo, not rhetoric. Applies to plans, diffs, and your own conclusions.
- **Fast through gates.** No re-confirming between phases; push each lane to done (commit, PR, human merges). Stop only for real scope changes or destruction.

<!-- accreting reminders — add one line each time the user has to repeat something -->
