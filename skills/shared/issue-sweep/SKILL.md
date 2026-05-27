---
name: issue-sweep
description: Run GitHub issues end-to-end by repeatedly picking the oldest eligible issue, fixing it directly, pushing to the default branch, and closing the issue. Use when the user invokes $issue-sweep, asks to do the oldest issues, or wants Codex/Claude to keep going down the issue queue without PR review.
---

# Issue Sweep

Pick the oldest eligible issue, launch workers in isolated worktrees, land their
commits serially on the default branch, close issues, continue. No PRs.

Keep this boring. The skill owns queue selection, worktree creation, landing,
push, and issue close. Workers only fix and commit.

## Defaults

- Order: oldest open issue first.
- Agent: Codex by default; pass `--agent claude` for Claude Code workers.
- Limit: 10 issues unless the user gives a limit.
- Endless mode: explicit `--forever`, sleeping 60 seconds when no eligible issue
  is available.
- Concurrency: 3 by default. Use `--parallel N` to tune parallel worktrees.
- Claim label: `assigned-to-me`.
- Assignee: `@me`.
- Skip labels: `blocked`, `wontfix`, `duplicate`, `needs-info`.
- Push target: default branch.
- PRs: no.
- Skip issues with existing PRs mentioning `Closes #N`, `Fixes #N`, or an
  `issue-N` branch, because someone else is already handling it.

## Hard Stops

Stop the sweep when:

- `gh auth status` fails.
- The repo has local changes the worker could accidentally absorb.
- A worker command exits non-zero.
- A worker asks for human input instead of fixing or reporting a blocker.
- No eligible issue remains.

## Workflow

1. Run the loop.

   ```bash
   scripts/run_issue_sweep.sh --limit 10
   ```

2. To use Claude instead of Codex:

   ```bash
   scripts/run_issue_sweep.sh --agent claude --limit 10
   ```

3. To keep going until stopped:

   ```bash
   scripts/run_issue_sweep.sh --forever
   ```

4. The runner repeats:

   ```bash
  issue = next_issue.sh
  claim up to 3 issues: assign to me and add assigned-to-me label
  workers fix issues in isolated worktrees and commit
  wait for workers
  cherry-pick worker commits onto the default branch one at a time
  push and close each issue
  record result
  remove claim label if the worker failed
  continue
   ```

## Worker Prompt

Each worker receives:

```text
Handle GitHub issue #N end-to-end without opening a PR.

You are one worker in an automated issue sweep. You are not alone in the
codebase; do not revert or overwrite changes made by others.

You are already inside an isolated git worktree. Fix only this issue. Run the
narrowest useful validation. Commit the fix on the current branch. Do not push,
do not open a PR, and do not close the issue; the orchestrator lands and closes.

Return only a concise result: issue number, commit hash, tests run, and any
blocker.
```

## Commands

```bash
scripts/next_issue.sh
scripts/claim_issue.sh <issue-number>
scripts/run_issue_sweep.sh --limit 5
scripts/run_issue_sweep.sh --parallel 3 --limit 10
scripts/run_issue_sweep.sh --agent claude --limit 5
scripts/run_issue_sweep.sh --forever --sleep 60
```

## Final Report

- Issues attempted
- Commits pushed
- Issues closed
- Worker failures or blockers
- Whether eligible issues remain
