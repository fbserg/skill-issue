---
name: blitz
description: Run a batch of lanes, filed issues or ad-hoc, in parallel worktrees. One filed issue → /resolve-issue. Not a planner.
---

Boundary: one filed issue → `/resolve-issue`. Any batch, filed or ad-hoc, runs
here (DECISIONS.md 2026-08-07). A filed issue's lane card includes the issue
number and its acceptance criteria.

You orchestrate and do not implement.

- **One lane per disjoint file set.** Run independent lanes in parallel
  worktrees. Serialize only real overlap. Put linked items (parent/follow-up,
  "after #N", same surface) in one lane or in sequential waves.
- **Spine files are single-writer.** Check churn (`git log --name-only`) first.
  The repo's most-touched shared files go to at most one lane per wave.
- **Dependent waves stack on an integration branch.** When wave N+1 builds on
  wave N's unmerged PRs, base it on `stack/<epic>-<wave>` (children → wave
  branch → main, merged in order). Land each wave before you open the next.
  GitHub won't retarget PRs on an unmerged rewritten base.
- **Lane cards, not broadcasts.** Each card gives file scope, the acceptance
  gate, and only the rulings that bind it. Every card ends with: "Report only
  in your final message; never SendMessage the lead."
- **Findings return batched, never as issue confetti.** One batched finding
  list per review lane; at most one follow-up issue per surface (measured: 42
  follow-up issues filed in one day from a single wave).
- **3+ detached lanes (`codex exec`, `claude -p`) → arm the watchdog** per
  `~/projects/skill-issue/docs/lane-watchdog.md`. Agent-tool lanes need no
  watchdog.
- **Workflow-based lanes** follow `~/projects/skill-issue/docs/workflow-template.md`.
- **Before any PR opens,** the branch rebases clean against main and every
  sibling already pushed. The human merges.
- **The wave summary names every lane that returned nothing.**
