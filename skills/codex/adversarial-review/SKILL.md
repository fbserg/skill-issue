---
name: adversarial-review
description: Run an adversarial review of a plan or diff before risky work lands. Use for "adversary", "adversarial review", "red-team this", risky deletions, migrations, multi-file rewrites, or plans that need a skeptical pass. Read-only by default.
---

# Adversarial Review

Attack a plan or diff before committing to it. The reviewer is skeptical and read-only.

## Inputs

Use the most specific available artifact:

1. User-provided plan or file.
2. Current branch diff: `git diff <base>...HEAD`.
3. Working tree diff: `git diff`.

## Review Lens

Check, in order:

1. Blast radius: callers, imports, scripts, config, cron, dynamic references.
2. Hidden lifecycle state: import-time behavior, persisted files, DB state, caches, first-deploy risk.
3. Rollback cost: what mutates and what would be hard to undo.
4. Verification gaps: what tests or checks do not cover.
5. Plausible failure narrative ending in a revert or production fix.

## Execution

- Prefer local read-only inspection.
- If sub-agents are available and the user asked for delegation or the risk warrants it, spawn one read-only reviewer with a narrow prompt.
- Confirm every finding against repo evidence before presenting it.
- Output findings as `finding -> evidence -> action`, and say "no credible attack found" only after naming what was checked.

## Boundaries

- Do not edit files.
- Do not create commits.
- Do not run destructive commands.
- Do not pad with generic risks; every finding needs concrete evidence.
