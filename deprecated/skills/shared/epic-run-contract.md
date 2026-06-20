# Epic-run shared contract

Agent-neutral rules shared by both Claude and Codex epic-run adapters.
Platform-specific control surface (ScheduleWakeup, spawn_agent, etc.) lives in
the adapter SKILL.md, not here.

## Invariants

- Child branches: `epic-<epic>-<child>-<slug>-<run-suffix>`.
- Orchestration runs from an isolated checkout/workspace. The user's checkout is only the launch point.
- Children run only in isolated worktrees/forked workspaces from `origin/<DEFAULT_BRANCH>`.
- Child Git is non-interactive: `GIT_EDITOR=true`, `git commit -m/-F`, `--no-edit` for rebase/cherry-pick.
- The orchestrator reads metadata, dispatches, and reports. It does not edit source, review diffs, or implement children.
- Concurrent child cap: configurable, default 7.
- Refuse epics with more than 20 children.
- Runnable epics: normally 3–5 children; 6–7 acceptable with clear ordering; 8+ → parent epic.
- Parent/program epics are coordination checklists only. Do not dispatch their child epics as implementation workers.
- Run lock label: `epic-<N>-running` (when the adapter can mutate labels).
- Every child PR gets the `epic-<N>` label at creation.
- GitHub PR labels and branch names are the source of truth for resume. No ledger or local state table.
- Resume skips any child with a PR branch matching `epic-<N>-<child>-*`, regardless of PR state.
- Children bootstrap before work: auto-detect package manager + pre-commit, or use repo's documented bootstrap block. Two failures → `STATUS=fail REASON=bootstrap-failed`.
- Children run focused tests only. Per-PR CI is the normal-mode merge gate; the orchestrator runs no aggregate suite.
- The orchestrator owns all merging. Children create verified PRs; they never queue auto-merge, merge directly, or ask the user to merge.
- Child PRs must pass `epic-tools verify-pr` before any orchestrator merge.
- Child PR bodies use `Closes #<child>` so GitHub closes child issues on merge.
- Child status line is exactly `STATUS=ok PR=<n> SHA=<sha>` or `STATUS=fail REASON=<short>`.
- Child PR bodies may include `## Notes` for non-blocking adjacent observations only.
- When `pending == 0`: close the epic only after `epic-tools epic-status <N>` is clean and every child issue is closed.
- Final line is `done` only when no open child issue, branch, or worktree remains.
- Unmerged orch/child state is disposable: stop, remove workspace/branch, resume from GitHub. Merged PRs need `epic-tools revert` or a revert PR.
