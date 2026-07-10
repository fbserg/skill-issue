---
name: ww
description: Use when the user invokes /ww or asks to do work in an isolated worktree. Creates a git worktree, plans first, implements only inside that worktree, opens a PR by default, and keeps the main checkout clean.
---

# Worktree Workflow

Run the requested task in an isolated git worktree. Never edit the primary checkout for this workflow.

## Workflow

1. Resolve the repository root and current branch.
2. Check primary checkout status. If unrelated dirty changes exist, leave them alone and create the worktree from `HEAD`.
3. Create a branch named `ww/<short-slug>` and worktree under `../<repo>-worktrees/<short-slug>` or `~/projects/<repo>-worktrees/<short-slug>`.
4. Inspect the repo inside the worktree and write a short implementation plan in the conversation before editing.
5. Implement only inside the worktree.
6. Run the relevant checks from repo docs or the touched stack.
7. Commit the worktree changes and push the branch.
8. Open a draft PR unless the user explicitly asked for local-only work.
9. Report the worktree path, branch, PR URL, and checks run.

## Hard Rules

- Main checkout stays untouched.
- Do not use `git stash`.
- Do not merge the PR.
- Do not delete the worktree until the PR branch is pushed or the user asks for cleanup.
- If the change cannot be isolated cleanly, stop and explain the blocker.
- This workflow is exactly one lane with a plan/approval gate. Route multiple ad-hoc lanes to `blitz` and filed issue work to `issue`.
