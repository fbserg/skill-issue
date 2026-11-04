---
name: epic-plan
description: Scope work that is too large for one issue into a GitHub epic with a tracker issue and right-sized child issues. Use for /epic-plan, multi-deliverable work, or tasks spanning multiple sessions. Materializes on GitHub autonomously, with no approval gate.
---

# Epic Plan

Turn a topic into one tracker issue plus child issues, each sized for one `resolve-issue` run. GitHub is the only state store.

- **Existing tracker:** re-sync the checklist with live child states and report. Revise in place on a human correction. When the last child lands, check the whole result against the tracker contract, then close it.
- **Really one issue:** route to `issue`.
- **New topic:** research the repo as much as it needs. Ask only questions that change the contract. Write a contract (done, out of scope, constraints) and vertical child slices, each one PR, each mapping to a done item, with real dependencies marked.
- **Materialize** with no approval gate. Search for the marker `<!-- epic-plan:child slug=<slug> ord=<N> -->` (and the tracker title) before each create so reruns never duplicate. Labels `epic` and `epic:<slug>`. Children say `Part of #<tracker>`.
- **Handoff:** report the contract, the children, and `issue` waves in dependency order with real numbers.

## Boundaries

- Do not implement code.

<!-- gate:dont-invent-scope carried from skills/claude/epic-plan/SKILL.md -->
- **Don't invent scope.** "Audit backups" means backups — the Out-of-scope line is the fence.
- Do not open PRs.
