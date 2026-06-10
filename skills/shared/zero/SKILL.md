---
name: zero
description: "Zero out a repo — destructive cleanup of pending work, PRs, branches, worktrees, and main push. Runs a read-only inventory before writes."
---

# /zero skill

Zero out the repo completely: commit pending changes on `main`, merge open PRs and delete their source branches, commit and merge every non-main worktree and stray local branch into `main`, drop worktrees, delete branches, push `main`, report open issues.

This is intentionally aggressive and only for the user's explicit "zero" cleanup point when no other agents are still working in the repo. The request itself authorizes the destructive cleanup: run the read-only inventory, summarize what will be merged/deleted, then continue without a second confirmation. The cleanup must never discard work — checkpoint dirty trees, merge every real unmerged patch, delete only what is merged or proven patch-equivalent to `main`.

---

## Shared procedures

### CHECKPOINT(path) — commit a dirty tree

Used on `main` and on any dirty worktree before merging it.

```bash
git -C <path> status --short
```
If clean, done. If dirty:
```bash
git -C <path> diff --stat HEAD     # inspect; also: git -C <path> log --oneline -3
git -C <path> add -A
git -C <path> commit -m "<real message based on diff>"
```
- Use a real message describing the actual change, never a generic checkpoint label.
- If pre-commit is configured, run it on the staged files before the commit. If hooks modify files, restage and rerun the relevant hook once.
- If `.git/index.lock` exists, check `ps -ef | grep '[g]it'` first; remove the lock only if no Git process is live, then retry.
- If the commit fails: report it, do not drop that worktree/branch, continue with the rest.

### CLASSIFY(branch) — merged / squash-trash / real work

Never treat a branch as unmerged solely because it is not an ancestor of `main`; squash-merges change commit IDs while the patch content is already in `main`.

```bash
git rev-list --count main..<branch>        # ahead count
git merge-base --is-ancestor <branch> main # exit 0 = ancestor
git cherry main <branch>                   # '+' lines = real unmerged patches
```
- **Merged** (`ahead=0` or ancestor): delete with `git branch -d`. If `-d` refuses only due to upstream bookkeeping but the ancestor check succeeds, `git branch -D` is allowed — it's metadata cleanup.
- **Squash-trash** (`ahead>0` but no `+` lines in `git cherry`): `git branch -D`. Force-delete is allowed only because `git cherry` proves no patch content is missing from `main`.
- **Real work** (one or more `+` lines): merge into `main`, then delete. If the repo documents an integrate recipe (e.g. `just integrate <branch>` in CLAUDE.md), use it instead of raw merge — repos that hook-block raw merges on main require it. Otherwise:
  ```bash
  git checkout $DEFAULT_BRANCH
  git merge <branch> --no-edit
  git branch -d <branch>
  ```
  On conflicts: resolve them — read both sides, keep all good new behavior, drop duplicated/obsolete code, run the narrowest relevant validation, then `git add -A && git commit --no-edit`. Ask the user only if the conflict needs a product decision that cannot be inferred from code/tests. Do not delete the branch until the merge commit succeeds.
- Upstream `[gone]` is suspect until proven merged/empty by the checks above.

---

## Execution

### 1. Preamble + inventory

Do not scan for active Codex/Claude sessions before zeroing. There are often unrelated
agent processes with CWDs inside the repo, and their presence alone is not evidence
that they are writing the checkout being zeroed. Instead, block only on concrete
repo mutation state: an active Git operation in any worktree, `.git/index.lock`
owned by a live Git process, or a repo-specific ship/deploy lock (e.g.
`~/.heartwood/main-ship.lockdir`) held by a live pid. Report those blockers before
discovering them later through phantom git state.

Then:

```bash
git fetch --prune --all && git worktree prune
```
Then collect state. Read-only commands may run in parallel; never run Git writers (`checkout`, `add`, `commit`, `merge`, `branch -d/-D`, `worktree remove`, `reset`, `stash`, `push`) in parallel with any other Git command in the same repo.

```bash
DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD 2>/dev/null | sed 's|^origin/||' || echo "main")
git worktree list --porcelain
git branch --format='%(refname:short) %(upstream:track)' | grep -v "^$DEFAULT_BRANCH"
gh pr list --state open --json number,title,headRefName
gh issue list --limit 50 --state open --json number,title
```

Briefly report the counts and continue. Stop and ask only on a blocker this workflow can't handle safely (active Git operation, unresolvable product conflict, missing GitHub credentials with open PRs).

### 2. Checkpoint main

`git checkout $DEFAULT_BRANCH`, then CHECKPOINT(main worktree).

### 3. Open PRs

For each open PR:
1. If its head branch has a local worktree, CHECKPOINT it first.
2. `gh pr merge <number> --merge --delete-branch`
   - Success: `git fetch --prune --all`, then delete any matching local branch via CLASSIFY (it should now be merged).
   - Failure: report as skipped with the `gh` error. Do not close it manually or delete its source branch.

Use the repo's configured merge requirements; no `--admin` unless the user explicitly asks.

### 4. Non-main worktrees

For each worktree where `branch != refs/heads/main` (path + branch from `--porcelain` output):
1. CHECKPOINT(path). If the checkpoint commit fails, report and skip this worktree.
2. Open-PR guard: `gh pr list --head <branch> --state open --json number | jq length` — if a PR is still open after step 3, report "open PR #N — skipped/failed earlier" and do not merge or drop.
3. CLASSIFY(branch). Once the branch is merged or proven trash:
   ```bash
   git worktree remove <path> --force
   ```
   then delete the branch per CLASSIFY rules.

### 5. Stray local branches

For each local branch with no worktree: apply the same open-PR guard, then CLASSIFY(branch), one branch at a time.

### 6. Push main

Prefer the repository's documented push/deploy command from CLAUDE.md or README (e.g. `just push-main`); otherwise `git push origin main`.

If there were skips or failures, still push completed `main` work unless that would publish an incomplete merge or broken conflict resolution. Report any push failure with the command output.

### 7. Summary report

```
PRs merged:          N  (or "none")
Checkpoint commits:  N  (or "none")
Branches merged:     N  (or "none")
Worktrees dropped:   N  (or "none")
Branches deleted:    N  (or "none")
Main pushed:         yes/no + command used
Skipped (commit failed): names + reason
Skipped (PR failed): "#N branch: reason"
Skipped (open PR):   "#N branch" only if still open after merge attempt
Conflicts resolved:  branches + files, if any
Unmerged branches:   names + commit count, only if blocked
Open PRs remaining:  "#N title"
Open issues:         "#N title"  ← informational only, never touched
```

---

## Guardrails

- Never delete `main`.
- `git branch -D` only when CLASSIFY proves merged/empty (ahead=0, ancestor, or clean `git cherry`).
- Open PR branches are touched only via `gh pr merge --delete-branch`; if that fails, leave PR and branch alone.
- Every dirty tree is CHECKPOINTed (inspected diff, real message) before any merge.
- Conflicts are part of the work — resolve, validate, commit, continue; ask only on product decisions.
- Remote pushes are limited to `gh pr merge --delete-branch` effects and the final `main` push.
