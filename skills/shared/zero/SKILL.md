---
name: zero
description: "Integrate active repo work, resolve draft PRs, and clean merged branches and worktrees. Preserve explicitly parked work. Runs a read-only inventory before writes."
---

# /zero skill

Zero out active work — branches, worktrees, and PRs merged into `main` or
proven already there, then deleted; `main` pushed. Parked work stays untouched.
Intentionally aggressive,
only for the user's explicit "zero": the request itself authorizes the
cleanup — run the read-only inventory, summarize, continue without a second
confirmation. **The cleanup must never discard work** — checkpoint dirty
trees, merge every real unmerged patch, delete only what is merged or proven
patch-equivalent to `main`.

## Shared procedures

### PARKED(ref, PR) — explicit deferral, not draft status

Before any write, read the relevant PR body, labels, owner comments, and repo
decisions. An explicit owner decision to park, defer, or keep the work out of
integration excludes its PR, branch, and worktree from zero. Do not checkpoint, ready, merge, close,
or delete them. Report the evidence and leave them intact. A generic zero does
not resume parked work; the user must explicitly resume that work.

`isDraft` alone is never evidence of parking.
Readiness conditions such as "do not merge until tests pass" are gates to resolve,
not parking. Review active drafts, resolve
conflicts and review findings within their agreed scope, run the repo's checks,
then mark ready and merge. A rejected review is work to resolve, not permission
to bypass checks or a reason to treat an active draft as parked. If a missing
product decision or failing gate cannot be resolved, retain the PR and branch
and report the exact blocker. Do not revive a closed, superseded proposal merely
because its patch differs from main.

### CHECKPOINT(path) — commit a dirty tree

`git -C <path> status --short`; if dirty: inspect the diff, `add -A`, commit
with a real message describing the actual change — never a generic checkpoint
label. Run pre-commit on staged files if configured (hooks modify files →
restage, rerun once). A stale `.git/index.lock` may be removed only after `ps`
proves no live Git process. A failed commit: report it, don't drop that
worktree/branch, continue with the rest.

### PROTECTED(ref) — pointer branches zero never owns

A pointer branch marks a deployed or approved commit (`prod`, `staging`,
`release/1.4`). It is an ancestor of `main` by design, so CLASSIFY would call
it merged and delete it. Resolve the protected set once, in the inventory,
and print it:

- **Built-in names**, on every remote and locally: `prod`, `production`,
  `staging`, `stable`, `release`, `release/*`, `deploy/*`.
- **Per-repo additions:** `git config --get-all zero.protect` (one branch name
  or glob per entry; set with `git config --add zero.protect <name>`).

A protected ref is excluded from every write, like the default branch and the
remote's symbolic `HEAD`: never checked out, merged from, deleted, or force
pushed. A remote ref that is an ancestor of `main`, is not protected, and does
not look like a work branch (no `lane/`, `feature/`, `fix/`, `codex/`, `dependabot/`
or similar prefix, and no PR ever pointed at it) is reported as
"pointer branch, left alone", not deleted — name a new pointer convention
with `zero.protect` rather than widening the built-in list.

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
  remote's symbolic `HEAD`, a PROTECTED ref, or a branch belonging to an
  open PR.

## Execution

1. **Inventory.** Don't scan for active agent sessions — unrelated agent
   processes with CWDs in the repo aren't evidence they're writing it. Block
   only on concrete mutation state: an active Git operation, `.git/index.lock`
   held by a live pid, or a repo-specific ship/deploy lock. Then
   `git fetch --prune --all && git worktree prune` and collect: default branch
   (`git symbolic-ref refs/remotes/origin/HEAD`), `git worktree list
   --porcelain`, local branches + tracking, every remote branch for every
   configured remote, `gh pr list`, `gh issue list`. Exclude each remote's
   symbolic `HEAD`, default branch, every PROTECTED ref, and PARKED work from cleanup;
   distinguish active drafts from parked work and print their evidence and the
   resolved protected set. Read-only commands may run
   in parallel; never run Git writers in parallel with any other Git command
   in the same repo. Report counts, continue.
2. **Checkpoint main:** `git checkout $DEFAULT_BRANCH`, CHECKPOINT it.
3. **Open PRs:** skip PARKED work. Checkpoint any active local worktree on the
   PR's head branch. Resolve drafts as above, including normal review and test
   gates; use `gh pr ready <n>` once ready, then
   `gh pr merge <n> --merge --delete-branch`. Success → fetch/prune, CLASSIFY
   any matching local branch. Failure → report as skipped; never close
   manually or delete its source branch. No `--admin` unless the user asks.
4. **Non-main worktrees:** PARKED guard → CHECKPOINT → open-PR guard (`gh pr list --head
   <branch>` — still open means skipped/failed earlier: report, don't touch)
   → CLASSIFY → `git worktree remove <path> --force` → delete branch per
   CLASSIFY.
5. **Stray local branches:** PARKED and open-PR guards + CLASSIFY, one at a time.
6. **Remote branches:** for every non-default remote ref not already deleted
   by a successful PR merge, skip it if PROTECTED or PARKED (report it), apply the
   pointer-branch guard, then run the open-PR guard and CLASSIFY it. Merge every
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
   status; every skip with its reason, including preserved parked work; the protected set and any pointer branches
   left alone; conflicts resolved; unmerged branches only if blocked; open
   PRs and open issues (informational — never touched).
