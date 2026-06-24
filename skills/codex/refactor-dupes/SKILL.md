---
name: refactor-dupes
description: Find and refactor meaningful duplicate code in a pointed directory. Use for /refactor-dupes <dir>, "DRY this up", "find duplicated code", or "collapse the copy-paste in X". Detects first, asks for approval before edits, then works in a worktree and PR.
---

# Refactor Dupes

Use this for duplication-driven cleanup when the target directory is explicit.

## Workflow

1. Confirm the target directory exists.
2. Run detection tools before reading broadly:
   - `npx --yes jscpd --reporters json --min-tokens 50 --min-lines 5 --silent <target>`
   - `lizard <target>` when available
3. Triage the output. Prefer clusters with three or more real call sites, meaningful logic duplication, and low behavioral ambiguity.
4. Produce an architecture brief before editing:
   - duplicate cluster
   - proposed abstraction or consolidation
   - call sites to change
   - tests/checks
   - explicit `LEAVE` recommendation when the duplication is clearer than the abstraction
5. Wait for user approval of the brief before edits.
6. After approval, create branch `refactor/dupes-<short-slug>` in a git worktree.
7. Refactor only the approved cluster.
8. Add or update tests only where they prove the consolidated behavior.
9. Run relevant checks, commit, push, and open a draft PR.
10. Report PR URL, checks, and any intentionally left duplication.

## Boundaries

- Do not scan the whole repository unless the user asks.
- Do not refactor multiple unrelated clusters in one PR.
- Do not introduce generic frameworks or speculative extension points.
- Do not merge the PR.
