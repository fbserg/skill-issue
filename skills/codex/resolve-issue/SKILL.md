---
name: resolve-issue
description: Resolve one GitHub issue in Codex from issue to review-ready PR. Uses an isolated worktree, plan comment, implementation, tests, review, and final PR body. Never merges. Supports --resume for an existing draft PR or plan comment.
---

# Resolve Issue

Take one GitHub issue to a review-ready PR. Keep the work durable in GitHub and isolated from the main checkout.

## Hard Rules

- One issue per branch.
- Work in a git worktree, not the primary checkout.
- Never merge.
- Run real checks before marking the PR ready.
- If acceptance criteria cannot be verified in the worktree, call that out in the PR body.
- Respect existing user changes. Do not reset or revert unrelated work.

## Preflight

1. Resolve repo and issue number.
2. Read issue title/body/comments/labels/assignee.
3. Search existing PRs for the issue number and branch names like `issue-<N>`.
4. If a ready PR exists, report it and stop.
5. If a draft PR or plan comment exists, resume from that state.
6. Assign yourself only when the repository convention supports it.

## Plan

1. Inspect the repo enough to identify the likely files, tests, and risks.
2. If the issue is too broad for one PR, stop and route to `epic-plan`.
3. If product intent is missing, ask the smallest blocking question.
4. Post a plan comment on the issue before opening the branch. Include:
   - intended behavior change
   - likely touched areas
   - acceptance criteria mapping
   - planned checks

## Implement

1. Create branch `fix/issue-<N>-<short-slug>` in a worktree.
2. Open a stub draft PR early so the lane is visible.
3. Implement the change in the worktree.
4. Add or update tests that exercise the behavior change.
5. Commit and push.

## Review and Finalize

1. Review the PR diff for correctness, missing tests, accidental scope growth, and unnecessary complexity.
2. Fix confirmed issues with additional commits.
3. Run the repo's documented gates verbatim. If none are documented, run the narrowest credible checks for the touched stack.
4. Update the PR body with:
   - summary
   - tests/checks run with pass/fail result
   - acceptance criteria status
   - deferred operator-only verification, if any
5. Mark the PR ready only after checks pass.

## Resume

For `--resume <N>`:

1. Re-read the issue, plan comment, branch, and draft PR.
2. Recreate the worktree from the existing branch if needed.
3. Continue from the first incomplete step.
4. Do not start a fresh branch unless the existing branch is missing and GitHub state proves no implementation exists.

## Completion Report

Report issue number, branch, PR URL, checks, and any residual risk. Do not call the work done if checks are red or unrun.
