---
name: epic-plan
description: Scope work that is too large for one issue into a GitHub epic with a tracker issue and right-sized child issues. Use for /epic-plan, multi-deliverable work, or tasks spanning multiple sessions. Creates nothing on GitHub until the user explicitly says GO.
---

# Epic Plan

Turn a broad topic into one tracker issue plus child issues that can each be handled by `resolve-issue`.

## Workflow

1. Inspect the repo first. Answer discoverable questions from code, docs, open issues, and recent PRs.
2. Ask only questions that change the decomposition or acceptance contract.
3. Freeze a short contract:
   - goal
   - success criteria
   - out of scope
   - constraints
4. Decide whether this is actually one issue. If yes, stop and route to `issue`.
5. Decompose into child issues. Each child must be one reviewable PR with clear acceptance criteria.
6. Identify dependencies between children. File-overlapping or migration-dependent children must serialize.
7. Review the decomposition once for missing prerequisites, over-splitting, hidden shared state, and verification gaps.
8. Present the tracker and child list to the user. Create nothing until the user says `GO`.

## Materialize After GO

1. Create the tracker issue with label `epic`.
2. Create label `epic:<slug>` if needed.
3. Create child issues with idempotency markers in the body:
   `<!-- epic-plan:child slug=<slug> ord=<N> -->`
4. Backfill the tracker checklist with real child issue numbers.
5. Report the exact execution waves, using real issue numbers in dependency order.

## Boundaries

- Do not implement code.
- Do not open PRs.
- Do not create GitHub artifacts before explicit `GO`.
- Browse only for information the repo cannot provide and that materially affects the plan.
