---
name: epic-plan
description: Scope work that is too large for one issue into a GitHub epic with a tracker issue and right-sized child issues. Use for /epic-plan, multi-deliverable work, or tasks spanning multiple sessions. Materializes the epic on GitHub autonomously once the reviewed decomposition is ready — no approval gate.
---

# Epic Plan

Turn a broad topic into one tracker issue plus child issues that can each be handled by `resolve-issue`. GitHub becomes the sole state store after materialization.

## Re-entry

- For an existing tracker number or URL, read the live tracker and every child. Re-sync the tracker checklist against actual child states before reporting or revising anything.
- A `needs-revision` label or explicit human correction loops back to decomposition review. Reuse the tracker; never duplicate it.
- When the last child lands, verify the composed result against the tracker contract end to end before closing the tracker. Per-child green checks do not prove the epic works as a whole.
- For a new topic, derive a stable kebab-case slug. Pre-materialize research may use `/tmp/epic-plan/<slug>/`; delete it after successful materialization.

## Workflow

1. Inspect the repo first. Answer discoverable questions from code, docs, open issues, and recent PRs.
2. Ask only questions that change the decomposition or acceptance contract.
3. Freeze a short contract:
   - goal
   - success criteria
   - out of scope
   - constraints
4. Decide whether this is actually one issue. If yes, stop and route to `issue`.
5. Decompose vertically by capability. Child 1 should be the thinnest end-to-end walking skeleton; every child must deliver something observable in one reviewable PR.
6. Derive children from the contract's success criteria. Every criterion maps to exactly one proving child; every child proves a criterion.
7. Give each child scope, machine-checkable acceptance criteria, 3–5 relevant repository facts, likely files, risk (`text-only`, `visual`, or `shared-state`), and explicit dependencies.
8. Treat overlapping sibling file sets as a decomposition smell. Re-cut first; serialize only genuine shared-state or migration dependencies.
9. Review once with distinct lenses: completeness, dependency ordering, scope/altitude, feasibility/testability, and premortem. Verify blocker claims against the repository and revise once.
10. **No approval gate: once the reviewed decomposition is ready, materialize it immediately** and present the contract, upheld blockers and resolutions, advisories, child DAG, and exact handoff waves in the same breath. Materialization is idempotent, so a later user revision edits issues in place — a wrong decomposition costs an edit, not a restart. The only thing that still stops for input is a genuine contract ambiguity from step 2/3 that the decomposition can't paper over.

## Materialize (immediately after review)

1. Search stable markers and matching tracker titles first; reuse existing artifacts so reruns never duplicate issues.
2. Create the tracker issue with label `epic`.
3. Create label `epic:<slug>` if needed.
4. Create child issues with idempotency markers in the body:
   `<!-- epic-plan:child slug=<slug> ord=<N> -->`
5. Include each child's repository context, proof requirement, `Part of #<tracker>`, and dependency numbers in its body.
6. Backfill the tracker checklist with real child issue numbers.
7. Report exact `issue` waves using real numbers in dependency order, capped at four independent children per wave.
8. Once the tracker and all children exist and the checklist is backfilled, delete the pre-materialize cache — GitHub is now the sole state store.

## Boundaries

- Do not implement code.
- Do not open PRs.
- Do not create GitHub artifacts that duplicate an existing tracker or child — always search markers first.
- Browse only for information the repo cannot provide and that materially affects the plan.
