---
name: zero
description: Destructive repository cleanup for an explicit "zero" request only. Inventories dirty work, branches, worktrees, and PRs before merging, deleting, or pushing. Never discards unmerged work.
---

# Zero

Zero out a repository only when the user explicitly asks for `zero` cleanup.

## Read-Only Inventory First

Run and summarize:

```bash
git status --short
git worktree list --porcelain
git branch --format='%(refname:short) %(upstream:track)'
gh pr list --state open --json number,title,headRefName,isDraft
gh issue list --limit 50 --state open --json number,title
```

Report what will be committed, merged, deleted, removed, and pushed before doing write operations.

## Cleanup Rules

- Never discard work.
- Checkpoint dirty trees with real commit messages before merging.
- Merge open PRs only through repository-approved `gh pr merge` behavior.
- Delete branches only when merged, ancestor of main, or patch-equivalent by `git cherry`.
- Merge real unmerged branch work into the default branch before deleting.
- Remove worktrees only after their branch work is merged or proven empty.
- Push the default branch at the end.

## Stop Conditions

Stop and report blockers for:

- active git operations or live index locks
- merge conflicts needing a product decision
- failing required checks that the repo requires before merge or push
- unclear default branch

## Final Report

Include commits made, PRs merged, branches deleted, worktrees removed, main push status, remaining open PRs/issues, and any blockers.
