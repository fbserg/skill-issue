---
name: epic-run
description: Execute planned GitHub epics with dependency-ordered Codex workers, isolated workspaces, and orchestrator-owned merges. Use for $epic-run or requests to run an epic with workers/subagents/parallel agents.
---

# Epic Run

Codex adapter for the shared epic-run method. This public copy is standalone.

## Shared Contract

# Epic Run Shared Contract

Agent-neutral rules shared by Claude and Codex adapters. Runtime-specific
control tools live in adapters, not here.

## Invariants

- Child branches: `epic-<epic>-<child>-<slug>-<run-suffix>`.
- Orchestration runs from an isolated checkout/workspace. The user's checkout
  is only the launch point, never a mutable git/test workspace.
- Children run only in isolated worktrees/forked workspaces from
  `origin/<DEFAULT_BRANCH>`. If isolation is not implicit, the orchestrator
  creates/passes a child worktree. Children enter it before edits and fail if
  cwd is the launch checkout or the assigned worktree is unavailable.
- Child Git is non-interactive: `GIT_EDITOR=true`, commits use `git commit
  -m/-F`, and rebase/cherry-pick continuations use `--no-edit`.
- The orchestrator reads metadata, dispatches, and reports. It does not edit
  source, review child diffs, or implement children.
- Concurrent child cap: 7.
- Refuse epics with more than 20 children.
- Runnable epics should normally have 3-5 implementation children. Six or seven
  children is acceptable with clear dependency ordering. If work needs 8+
  children or multiple independent themes, plan it as a shallow parent/program
  epic whose children are smaller runnable epics.
- Parent/program epics are coordination checklists only. Do not dispatch their
  child epics as implementation workers; run each child epic through this same
  lifecycle in dependency order.
- Use run lock label `epic-<N>-running` when the adapter can mutate labels.
- Every child PR gets the `epic-<N>` label at creation.
- GitHub PR labels and branch names are the source of truth for resume. No
  ledger or local state table.
- Resume skips any child with a PR branch matching `epic-<N>-<child>-*`,
  regardless of PR state.
- Children bootstrap before work: auto-detect package manager + pre-commit, or
  use the repo's documented worktree bootstrap block. Two failures →
  `STATUS=fail REASON=bootstrap-failed`.
- Children run focused tests only. Per-PR CI is the normal-mode merge gate; the
  orchestrator runs no aggregate suite/demo. Disabled Actions → `manual-merge`.
- The orchestrator owns all merging. Children create verified PRs; they never
  queue auto-merge, merge directly, or ask the user to merge.
- Child PRs must pass `epic-tools verify-pr` before any orchestrator merge.
- Child PR bodies use `Closes #<child>` so GitHub closes child issues on merge.
- Child status line is exactly `STATUS=ok PR=<n> SHA=<sha>` or
  `STATUS=fail REASON=<short>`.
- The child completion audit file (`usage.jsonl`) is written to a runtime-specific state directory. For Claude: `~/.claude/state/epic-run/usage.jsonl`. For Codex: use a path appropriate for your runtime, or omit if no persistent state directory is available. Not run state — token fields are optional best-effort extras; Codex rows may be marker-only with zero token counts.
- Child PR bodies may include `## Notes` for non-blocking adjacent observations.
  Anything required for the child acceptance criteria must be fixed or returned
  as `STATUS=fail`, never hidden in notes.
- When `pending == 0`: close the epic only after `epic-tools epic-status <N>` is
  clean and `epic-tools parse-epic <N>` shows every child issue closed.
- Final line is `done` only when no open child issue, branch, or worktree remains.
- Unmerged orch/child state is disposable: stop, remove its workspace/branch,
  and resume from GitHub. Merged PRs need `epic-tools revert` or a revert PR.
- Any optional simplification, test-integrity, or acceptance-criteria verifier
  must use the current runtime's agent/control surface.

## Disabled Actions

When repo Actions are disabled, the adapter sets `MODE=manual-merge` in
preflight and continues without asking the user to re-run.

In `manual-merge` mode:

- workers create branches, run focused tests, commit, push, open PRs, and run
  `epic-tools verify-pr`;
- the orchestrator merges verified PRs directly via REST (no auto-merge queue,
  no CI gate);
- dependency ordering, wakeup scheduling, and epic close proceed unchanged.

## Tool Surface

- `epic-tools parse-epic <N>` fetches epic/child metadata.
- `epic-tools pr-create` creates child PRs and applies `epic-<N>`.
- `epic-tools verify-pr` checks ownership, branch, title, author, and SHA.
- `epic-tools epic-status <N>` reports merged, pending, red, and open-green PRs.
- `epic-tools revert <N>` opens a revert PR over all merged epic-<N> children.
  Manual use only — orchestrator no longer invokes it.
- `epic-tools cleanup <N>` is auto-invoked at epic close (§4a step 6); also runnable manually for stale runs.

## Codex Adapter

- Use `spawn_agent(agent_type: "worker")`; leave `model` unset unless requested.
- Workers use isolated forked workspaces from `origin/<DEFAULT_BRANCH>`, or a
  child `git worktree` path if isolation is not implicit.
- Child prompts must verify workspace/branch, preserve unrelated changes, and
  fail if cwd is the launch checkout or the worktree is unavailable.
- The user's checkout is launch-only: do not switch branches, test, or mutate it.
- Use `wait_agent` for worker unblocks, `send_input` for small corrections, and
  `close_agent` for aborts.

## Preflight

Collect:

```bash
LOCK=epic-<epic>-running
REPO=$(git remote get-url origin | sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\.git)?#\1#')
gh api repos/$REPO/issues/<epic>
DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||')
git fetch origin
PLAN=$(epic-tools parse-epic <epic>)
GH_USER=$(gh api /user --jq .login)
RUN_ID_SUFFIX=$(openssl rand -hex 4)
ACTIONS_ENABLED=$(gh api repos/$REPO/actions/permissions --jq .enabled 2>/dev/null || echo unknown)
EXISTING=$(epic-tools epic-status <epic> --json)
```

Refuse closed epics. `ACTIONS_ENABLED=false` means `MODE=manual-merge`.
If the lock exists, surface it and stop. Otherwise add it before dispatch and
remove it on every exit. On resume, reuse `RUN_ID_SUFFIX` and re-run
`parse-epic`; if memory was lost while locked, stop and surface stale state.

## Dispatch

Parse `PLAN.children`/`deps`; build ready, deferred, in-flight, and
failed-dependency sets. Dispatch ready children up to the cap. After
`STATUS=ok`, read `epic-tools epic-status <epic> --json` once on the next pass
and promote dependents only after deps merge.

Worker prompts include:

- epic number, child number, title, body, deps, and likely touched files;
- branch target `epic-<epic>-<child>-<slug>-<RUN_ID_SUFFIX>`;
- base `origin/<DEFAULT_BRANCH>`;
- explicit filesystem context: isolated forked workspace or child worktree path;
- `GH_USER` resolved by the orchestrator;
- absolute path to `epic-tools` if available;
- instruction to enter/verify the workspace, create/verify the branch,
  implement only the child, run focused tests, commit non-interactively with
  `(#<child>)`, push, create the PR, run `epic-tools verify-pr`, and return
  exactly one status line;
- instruction that children never merge, queue auto-merge, or ask the user to merge;
- instruction that optional PR `## Notes` are only for non-blocking adjacent
  observations, never unfinished acceptance criteria;
- instruction not to deploy, restart daemons, push to main, create unrelated
  commits, close issues manually, or touch another child's branch.

Do not dispatch dependents early; promote them only after parent PRs merge.

After `STATUS=ok`, run `epic-tools verify-pr` against reported PR/SHA. Normal
mode merges only when current REST check-runs for that SHA are successful;
stale, failed, missing, or queued checks are not green. GraphQL throttling falls
back to the same REST check-run gate. In `manual-merge`, squash-merge the
verified PR via REST immediately.

## Close

When `pending == 0`:

1. Drop the run lock: `gh issue edit <epic> --remove-label "$LOCK"`.
2. Confirm `epic-tools epic-status <epic>` still shows `pending == 0`.
3. Re-run `epic-tools parse-epic <epic>` and confirm every child issue is
   closed. Do not close just because every visible PR is merged.
4. If all children are closed, close the epic:
   `gh issue edit <epic> --state closed`; otherwise surface open child numbers.
5. If the epic closed, run `epic-tools cleanup <epic>`.
6. Final line: `epic #<epic> | <m>/<total> merged | done`.

Do not call `ScheduleWakeup`. The run ends here.

`epic-tools revert <epic>` is manual; the orchestrator never calls it automatically.
