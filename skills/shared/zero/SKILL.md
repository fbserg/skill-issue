---
name: zero
description: "Zero out a repo — destructive cleanup of pending work, PRs, local and remote branches, worktrees, and main push. Runs a read-only inventory before writes."
---

# /zero skill

Zero out the repo — every branch, worktree, and PR merged into `main` or
proven already there, then deleted; `main` pushed. Intentionally aggressive,
only for the user's explicit "zero": the request itself authorizes the
cleanup — run the read-only inventory, summarize, continue without a second
confirmation. **The cleanup must never discard work** — checkpoint dirty
trees, merge every real unmerged patch, delete only what is merged or proven
patch-equivalent to `main`.

## Shared procedures

### CHECKPOINT(path) — commit a dirty tree

`git -C <path> status --short`; if dirty: inspect the diff, `add -A`, commit
with a real message describing the actual change — never a generic checkpoint
label. Run pre-commit on staged files if configured (hooks modify files →
restage, rerun once). A stale `.git/index.lock` may be removed only after `ps`
proves no live Git process. A failed commit: report it, don't drop that
worktree/branch, continue with the rest.

### CLASSIFY(ref) — merged / squash-trash / real work

Never treat a local or remote branch as unmerged solely because it isn't an
ancestor of `main` — squash-merges change commit IDs while the patch content
is already in `main`.

```bash
git rev-list --count main..<ref>        # ahead count
git merge-base --is-ancestor <ref> main # exit 0 = ancestor
git cherry main <ref>                   # '+' lines = real unmerged patches
```

- **Merged** (`ahead=0` or ancestor): safe to delete after the deletion rules
  below are satisfied.
- **Squash-trash** (`ahead>0`, no `+` lines): safe to delete only because
  `git cherry` proves no patch content is missing from `main`.
- **Real work** (`+` lines): merge into `main` — via the repo's documented
  integrate recipe (e.g. `just integrate <ref>`) if one exists, else plain
  `git merge --no-edit` — then delete. Conflicts are part of the work: read
  both sides, keep good new behavior, run the narrowest relevant validation,
  commit. Ask the user only on a product decision code/tests can't answer.
  Never delete before the merge commit succeeds.
- Upstream `[gone]` is suspect until proven merged/empty by the checks above.

Deletion rules:

- **Local ref:** use `git branch -d`; `-D` is allowed only for proven
  squash-trash or when `-d` refuses solely because of upstream bookkeeping.
- **Remote ref:** never delete it until all real work is merged, validated, and
  the updated default branch is successfully pushed. Re-run CLASSIFY against
  the pushed default branch, then use `git push <remote> --delete <branch>`.
- Never delete a default branch (local or remote, whatever its name), a
  remote's symbolic `HEAD`, or a branch belonging to an open PR.

## Execution

1. **Inventory.** Don't scan for active agent sessions — unrelated agent
   processes with CWDs in the repo aren't evidence they're writing it. Block
   only on concrete mutation state: an active Git operation, `.git/index.lock`
   held by a live pid, or a repo-specific ship/deploy lock. Then
   `git fetch --prune --all && git worktree prune` and collect: default branch
   (`git symbolic-ref refs/remotes/origin/HEAD`), `git worktree list
   --porcelain`, local branches + tracking, every remote branch for every
   configured remote, `gh pr list`, `gh issue list`. Exclude each remote's
   symbolic `HEAD` and default branch from cleanup. Read-only commands may run
   in parallel; never run Git writers in parallel with any other Git command
   in the same repo. Report counts, continue.
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
6. **Remote branches:** for every non-default remote ref not already deleted
   by a successful PR merge, run the open-PR guard and CLASSIFY it. Merge every
   real patch into the local default branch and validate it. Record merged and
   squash-trash remote branches for deletion, but do not delete any remote ref
   yet.
7. **Push main** via the repo's documented push recipe (e.g. `just
   push-main`), else `git push origin main`. Skips elsewhere don't block the
   push unless it would publish an incomplete merge. The only remote writes
   this skill ever makes: `gh pr merge` effects, this push, and step 8's
   proven-safe deletions — never a force push.
8. **Delete remote branches:** fetch/prune, re-run the open-PR guard and
   CLASSIFY each recorded remote ref against the now-pushed default branch,
   then `git push <remote> --delete <branch>`. A failed delete is reported and
   left alone; it never justifies a force push.
9. **Report:** counts for PRs merged / checkpoints / branches merged /
   worktrees dropped / local branches deleted / remote branches deleted / push
   status; every skip with its reason; conflicts resolved; unmerged branches
   only if blocked; open PRs and open issues (informational — never touched).
