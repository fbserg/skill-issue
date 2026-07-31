---
name: zero
description: "Zero out a repo — destructive cleanup of pending work, PRs, branches, worktrees, and main push. Runs a read-only inventory before writes."
---

# /zero skill

Zero out the repo: commit pending changes on `main`, merge open PRs and delete
their branches, merge every non-main worktree and stray branch into `main`,
drop worktrees, delete branches, push `main`, report open issues.

Intentionally aggressive, only for the user's explicit "zero" point. The
request itself authorizes the cleanup: run the read-only inventory, summarize,
then continue without a second confirmation. **The cleanup must never discard
work** — checkpoint dirty trees, merge every real unmerged patch, delete only
what is merged or proven patch-equivalent to `main`.

## Shared procedures

### CHECKPOINT(path) — commit a dirty tree

`git -C <path> status --short`; if dirty: inspect the diff, `add -A`, commit
with a real message describing the actual change — never a generic checkpoint
label. Run pre-commit on staged files if configured (hooks modify files →
restage, rerun once). A stale `.git/index.lock` may be removed only after `ps`
proves no live Git process. A failed commit: report it, don't drop that
worktree/branch, continue with the rest.

### CLASSIFY(branch) — merged / squash-trash / real work

Never treat a branch as unmerged solely because it isn't an ancestor of
`main` — squash-merges change commit IDs while the patch content is already
in `main`.

```bash
git rev-list --count main..<branch>        # ahead count
git merge-base --is-ancestor <branch> main # exit 0 = ancestor
git cherry main <branch>                   # '+' lines = real unmerged patches
```

- **Merged** (`ahead=0` or ancestor): `git branch -d` (`-D` allowed if `-d`
  refuses only on upstream bookkeeping — it's metadata cleanup).
- **Squash-trash** (`ahead>0`, no `+` lines): `git branch -D` — allowed only
  because `git cherry` proves no patch content is missing from `main`.
- **Real work** (`+` lines): merge into `main` — via the repo's documented
  integrate recipe (e.g. `just integrate <branch>`) if one exists, else plain
  `git merge --no-edit` — then delete. Conflicts are part of the work: read
  both sides, keep good new behavior, run the narrowest relevant validation,
  commit. Ask the user only on a product decision code/tests can't answer.
  Never delete before the merge commit succeeds.
- Upstream `[gone]` is suspect until proven merged/empty by the checks above.

## Execution

1. **Inventory.** Don't scan for active agent sessions — unrelated agent
   processes with CWDs in the repo aren't evidence they're writing it. Block
   only on concrete mutation state: an active Git operation, `.git/index.lock`
   held by a live pid, or a repo-specific ship/deploy lock. Then
   `git fetch --prune --all && git worktree prune` and collect: default branch
   (`git symbolic-ref refs/remotes/origin/HEAD`), `git worktree list
   --porcelain`, local branches + tracking, `gh pr list`, `gh issue list`.
   Read-only commands may run in parallel; never run Git writers in parallel
   with any other Git command in the same repo. Report counts, continue.
2. **Checkpoint main:** `git checkout $DEFAULT_BRANCH`, CHECKPOINT it.
3. **Open PRs:** checkpoint any local worktree on the PR's head branch, then
   `gh pr merge <n> --merge --delete-branch`. Success → fetch/prune, CLASSIFY
   any matching local branch. Failure → report as skipped; never close
   manually or delete its source branch. No `--admin` unless the user asks.
4. **Non-main worktrees:** CHECKPOINT → open-PR guard (`gh pr list --head
   <branch>` — still open means skipped/failed earlier: report, don't touch)
   → CLASSIFY → `git worktree remove <path> --force` → delete branch per
   CLASSIFY.
5. **Stray local branches:** same guard + CLASSIFY, one at a time.
6. **Push main** via the repo's documented push recipe (e.g. `just
   push-main`), else `git push origin main`. Skips elsewhere don't block the
   push unless it would publish an incomplete merge.
7. **Report:** counts for PRs merged / checkpoints / branches merged /
   worktrees dropped / branches deleted / push status; every skip with its
   reason; conflicts resolved; unmerged branches only if blocked; open PRs
   and open issues (informational — never touched).

## Guardrails

- Never delete `main`.
- `git branch -D` only when CLASSIFY proves merged/empty (ahead=0, ancestor,
  or clean `git cherry`).
- Open PR branches are touched only via `gh pr merge --delete-branch`; if that
  fails, leave PR and branch alone.
- Every dirty tree is CHECKPOINTed (inspected diff, real message) before any
  merge.
- Conflicts are resolved, validated, committed — ask only on product
  decisions.
- Remote pushes are limited to `gh pr merge` effects and the final `main`
  push.
