---
name: zero
description: "Zero out a repo — destructive: commits pending work, merges all open PRs, merges all local branches into the default branch, drops worktrees, deletes branches, pushes. Run only at a deliberate cleanup point when no other agents are working."
user-invocable: true
allowed-tools: Bash
---

# /zero skill

Zero out the repo completely. Commit pending changes on `main`, merge open PRs and delete their source branches, commit and merge every non-main worktree into `main`, merge every stray local branch into `main`, drop worktrees, delete local branches, push `main`, and report open issues.

This command is intentionally aggressive. It is only for the user's explicit "zero" cleanup point when no other agents are expected to still be working in the repo.

---

## Execution

### 1. Preamble

```bash
git fetch --prune --all
git worktree prune
```

### 2. Inventory

Collect state in parallel only for read-only commands. Never run Git writers in parallel with any other Git command in the same repo. Git writers include `checkout`, `add`, `commit`, `merge`, `branch -d/-D`, `worktree remove`, `reset`, `stash`, and `push`.

```bash
DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || echo "main")

# worktree list in porcelain form — maps branch refs to paths
git worktree list --porcelain

# all local branches except the default branch, with upstream tracking status
git branch --format='%(refname:short) %(upstream:track)' | grep -v "^$DEFAULT_BRANCH"

# open PRs
gh pr list --state open --json number,title,headRefName

# open issues
gh issue list --limit 50 --state open --json number,title
```

### 3. Checkpoint main

Before merging anything into `main`, make sure `main` itself is clean. From the main worktree:
```bash
git checkout $DEFAULT_BRANCH
git status --short
```
If `.git/index.lock` exists, check for a live Git process before continuing. Use `epic-tools epic-lock-status` if available, or check inline:
```bash
ps -ef | grep '[g]it'
```
Do not remove a lock while a Git process is active. If no Git process is active and the lock is stale, remove it and retry.

If `main` has staged, unstaged, or untracked changes, commit all of them first:
```bash
git add -A
git commit -m "chore: zero checkpoint main"
```
(Repeated for each checkpoint site below — the hook runs on staged files before every commit.)
If pre-commit is configured, run it on the staged files before the first checkpoint commit. If hooks modify files, restage and rerun the relevant hook once before committing.
If there is nothing to commit, continue.

### 4. Open PRs

For each open PR from inventory:

**a. Dirty PR worktree checkpoint:**
If the PR head branch has a local worktree, check it first:
```bash
git -C <path> status --short
```
If dirty, commit all changes in that worktree before merging the PR:
```bash
git -C <path> add -A
git -C <path> commit -m "chore: zero checkpoint <branch-name>"
```
If pre-commit is configured, run it on the staged files before committing (same as Step 3).

**b. Merge PR and delete source branch:**
```bash
gh pr merge <number> --merge --delete-branch
```
- Success: count the PR as merged. Run `git fetch --prune --all`, then delete any matching local branch if it still exists and is now merged into `main`.
  ```bash
  git merge-base --is-ancestor <branch-name> main && git branch -d <branch-name>
  ```
- Failure: report the PR as skipped with the `gh` error reason. Do not close it manually and do not delete its source branch.

Use the repository's configured merge requirements. Do not use `--admin` unless the user explicitly asks.

### 5. Non-main worktrees

For each worktree where `branch != refs/heads/main`:

Extract path and branch name from `--porcelain` output.

**a. Checkpoint uncommitted changes:**
```bash
git -C <path> status --short
```
If dirty, commit all changes in that worktree before merging:
```bash
git -C <path> add -A
git -C <path> commit -m "chore: zero checkpoint <branch-name>"
```
If pre-commit is configured, run it on the staged files before committing (same as Step 3).
If the commit fails, report it and stop. Do not drop the worktree.

**b. Open PR guard:**
```bash
gh pr list --head <branch-name> --state open --json number | jq length
```
If an open PR still exists after step 4: report it ("open PR #N - skipped/failed earlier"). Do not merge or drop.

**c. Merge check:**
```bash
git merge-base --is-ancestor <branch> main
```
- Already merged (exit 0): drop it.
  ```bash
  git worktree remove <path> --force
  git branch -d <branch-name>
  ```
  If `git branch -d` refuses only because the branch is not merged to its upstream, but `git merge-base --is-ancestor <branch-name> HEAD` succeeds, use `git branch -D <branch-name>`. The code is already in `main`; this is local metadata cleanup.

- Not merged (exit 1): merge into main, then drop.
  ```bash
  git checkout $DEFAULT_BRANCH
  git merge <branch-name> --no-edit
  ```
  - Success: drop worktree + branch as above.
  - Conflicts: resolve them. Read both sides, keep all good new behavior from both branches, remove duplicated or obsolete code, run the narrowest relevant validation, then `git add -A && git commit --no-edit`. Only ask the user if the conflict requires a product decision that cannot be inferred from code/tests.

### 6. Stray local branches

For each local branch not associated with a worktree (from step 2 inventory):

Classify before acting:
```bash
git rev-list --count main..<branch-name>   # ahead of main
git rev-list --count <branch-name>..main   # behind main
```
- `ahead=0`: delete only; nothing needs merging.
- `ahead>0` and no open PR: merge into `main`.
- open PR: handle only through `gh pr merge`.
- tracking status `[gone]`: delete; remote branch was already removed.

**a. Open PR guard:**
```bash
gh pr list --head <branch-name> --state open --json number | jq length
```
If an open PR still exists after step 4: report it ("open PR #N - skipped/failed earlier"). Do not merge or delete it outside `gh pr merge`.

**b. Merge or delete:**

If tracking is `[gone]`, treat it as already handled remotely and delete it:
```bash
# %(upstream:track) outputs [gone] when remote ref was deleted (catches squash-merges)
git branch -D <branch>
```

If already merged into `main`, delete it:
```bash
git merge-base --is-ancestor <branch> main
git branch -d <branch>
```
If `git branch -d` refuses only because the branch is not merged to its upstream, but `git merge-base --is-ancestor <branch> HEAD` succeeds, use `git branch -D <branch>`. The code is already in `main`; this is local metadata cleanup.

If not merged, merge it into `main` one branch at a time, then delete it:
```bash
git checkout $DEFAULT_BRANCH
git merge <branch-name> --no-edit
git branch -d <branch-name>
```
- Success: count it as merged and deleted.
- Conflicts: resolve them. Read both sides, keep all good new behavior from both branches, remove duplicated or obsolete code, run the narrowest relevant validation, then `git add -A && git commit --no-edit`. Only ask the user if the conflict requires a product decision that cannot be inferred from code/tests. Do not delete the branch until the merge commit succeeds.

### 7. Push main

After all possible merges, deletions, and conflict resolutions are complete, push `main`.

Prefer the repository's documented push/deploy command from CLAUDE.md or README when one exists. Otherwise use:
```bash
git push origin main
```

If there were skipped PRs, blocked branches, unresolved conflicts, or failed checkpoint commits, still push completed `main` work unless doing so would publish an incomplete merge or broken conflict resolution. Report any push failure with the command output.

### 8. Summary report

```
PRs merged:          N  (or "none")
Checkpoint commits:  N  (or "none")
Branches merged:     N  (or "none")
Worktrees dropped:   N  (or "none")
Branches deleted:    N  (or "none")
Main pushed:         yes/no + command used
Skipped (commit failed): list names + reason
Skipped (PR failed): list "#N branch-name: reason"
Skipped (open PR):   list "#N branch-name" only if still open after PR merge attempt
Conflicts resolved:  list branches + files, if any
Unmerged branches:   list names + commit count, only if blocked by conflict or failed PR
Open PRs remaining:  list "#N title"
Open issues:         list "#N title"  ← informational only, never touched
```

---

## Guardrails

- Never delete `main`.
- Never `git branch -D` (force-delete) unless the upstream track is `[gone]` or the branch is already an ancestor of `HEAD` and `git branch -d` only refused due upstream bookkeeping.
- Open PR branches are handled only through `gh pr merge <number> --merge --delete-branch`; if that fails, leave the PR and branch alone.
- Dirty `main` and dirty non-main worktrees are checkpointed with `git add -A && git commit` before merging.
- Merge all local branches into `main` one by one unless blocked by a failed checkpoint commit, failed PR merge, or a conflict that requires a product decision.
- Conflicts are part of the work: with `--auto-resolve`, inspect both sides, preserve the good new code, resolve, validate, commit, then continue. Without `--auto-resolve`, stop and ask the user.
- Remote pushes are limited to the explicit PR merge/source-branch deletion performed by `gh pr merge --delete-branch` and the final `main` push in step 7.
