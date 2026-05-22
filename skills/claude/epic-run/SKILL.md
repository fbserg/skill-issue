---
name: epic-run
description: "Execute a planned GitHub epic end-to-end — fetch issues, fan children out as parallel subagents in isolated worktrees, and merge verified PRs from the orchestrator. **Have a local plan file? Run `epic-tools plan-to-epic <path>` first to materialize the epic + children, then `/epic-run <N>`.** Automatically uses manual-merge mode when Actions are disabled. Use when user invokes `/loop /epic-run <epic-issue-number>`, \"run this epic\", \"epic run it\", \"ship this plan\"."
---

**Requires:** subagent dispatch with worktree isolation. **Optional:** scheduled wakeups via `ScheduleWakeup` (available in Claude Code's loop/cron harness). Without scheduled wakeups, run one tick at a time manually.

Run a `/epic-plan` epic to merged child PRs. The orchestrator handles dependency
math, dispatch, verification, and merging. Children work in isolated worktrees,
open verified PRs, and return `STATUS=`. Disabled Actions automatically switch
to `manual-merge`: the orchestrator merges verified PRs via REST.

Use `/loop /epic-run <N>` for unattended runs. Each tick re-reads GitHub state,
dispatches newly-ready children, collects replies, then either wakes later or
closes. A plain `/epic-run <N>` does one tick only.

Claude-only control surface and child procedure live here and in `dispatch.md`;
the orchestrator passes the path to `dispatch.md` but does not read it.

## Hard rails

- Orchestrator may use `gh`, `epic-tools`, child `STATUS=` replies, and
  `ScheduleWakeup`. Must not inspect repo source/tests/config, review child
  diffs, debug tool internals, implement child work, or second-guess verifier
  subagents.
- **Isolation**: orchestration runs from an isolated checkout. The user's launch
  checkout is the starting point only — never mutated or used as a work
  workspace.
- **Resume**: skip any child whose remote branch `epic-<N>-<child>-*` already
  exists, regardless of PR state. GitHub labels, PRs, and branch names are the
  source of truth; no local ledger or state table is maintained.
- **Disposability**: unmerged orch/child state is disposable — stop the run,
  remove workspace/branch, resume from GitHub state. Merged PRs need
  `epic-tools revert <N>` or a manual revert PR; the orchestrator never
  invokes revert automatically.

## Tick model

```
§0 pre-flight  -> lock, parse
§1 read state  -> epic-tools epic-status <N> --json
§2 bucket      -> merged | in-flight | failed | ready | deferred | dep-failed
§3 dispatch    -> up to 7 total in-flight; collect this tick's STATUS=
§4 exit        -> pending>0 wake/stop, pending=0 verify children closed + close
```

Ticks are idempotent. GitHub labels, PRs, and branch names are truth; cached
strings like `RUN_ID_SUFFIX` and `PARSE` are convenience only.

## §0  Pre-flight

```bash
LOCK="epic-<N>-running"
REPO=$(git remote get-url origin | sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\.git)?#\1#')
DEFAULT_BRANCH=$(git symbolic-ref --short refs/remotes/origin/HEAD | sed 's|^origin/||')
git fetch origin
GH_USER=$(gh api /user --jq .login)
ACTIONS_ENABLED=$(gh api repos/$REPO/actions/permissions --jq .enabled 2>/dev/null || echo unknown)
MODE=normal
[[ "$ACTIONS_ENABLED" == "false" ]] && MODE=manual-merge
```

First tick:

```bash
epic-tools lock-status <N> || { echo "epic #<N> already running (active in last 6h)"; exit 1; }
PARSE=$(epic-tools parse-epic <N>)
gh issue edit <N> --add-label "$LOCK"
RUN_ID_SUFFIX=$(openssl rand -hex 4)
```

`parse-epic` returns the epic and children. Abort if the epic is closed or has
more than 20 children. Later ticks re-add the lock idempotently and reuse cached
values; if memory was lost while the lock remains, generate a new suffix and
re-parse the epic. Lock removal happens only in §4a or Abort.

Sizing guidance: a normal runnable epic should have 3-5 implementation children;
6-7 is acceptable with clear ordering. If the issue is a parent/program epic
whose checklist items are other epics, do not dispatch those as workers. Surface
the ready child epics and run each one through this same lifecycle in dependency
order.

## §1  Read GitHub state

```bash
PRS=$(epic-tools epic-status <N> --json)
FAILED=$(gh api "repos/$REPO/issues?labels=epic-<N>-failed&state=all&per_page=100" --jq '.[].number')
```

Use branch names `epic-<N>-<child>-*` to join children to PRs.

## §2  Bucket children

- `merged`: matching PR has `mergedAt`.
- `in-flight`: open PR, no failed label, no red CI, not dirty.
- `ci-failed`: open PR, completed check-run conclusion=failure.
- `ci-flake`: cancelled/timed_out check-run and no real failure.
- `conflicted`: open PR with dirty merge state.
- `failed`: child has `epic-<N>-failed`.
- `ready`: no PR/failed label and all deps merged.
- `deferred`: no PR/failed label and some dep still active.
- `dep-failed`: no PR/failed label and a dep failed.

Immediately label every `dep-failed` or real `ci-failed` child with
`epic-<N>-failed`. For `ci-flake`, rerun failed jobs once and label the PR
`epic-<N>-ci-retried`; if that label is already present, mark failed.
`conflicted` stays in-flight and gets a rebase subagent in §3.

In `manual-merge` mode, do not treat missing CI as pending or green. Children
still stop at verified PRs; the orchestrator merges those PRs directly via REST.

CI check source: REST check-runs
`gh api repos/$REPO/commits/<head_sha>/check-runs --jq '.check_runs[] | {status, conclusion}'`.
`epic-tools epic-status <N>` also surfaces red CI and dirty PRs.

## §3  Dispatch + collect

Slots = `7 - count(in-flight)`. (7 = practical concurrency cap; avoids shared-helper conflicts.) Dispatch up to that many `ready` children in one
message as parallel `Agent` calls with worktree isolation, background mode, and
bypass permissions. Each child bootstraps its worktree (uv/poetry/npm/yarn +
pre-commit) as Step 0 before any work; see `dispatch.md`. Pass only a short
prompt:

```
Read the adjacent `dispatch.md` in this `epic-run` skill directory and follow it.
Substitutions:
  N=<epic> child=<n> slug=<slug> RUN_ID_SUFFIX=<suffix>
  DEFAULT_BRANCH=<branch> TIDY=<yes|no> GH_USER=<login>
  EPIC_TOOLS=<absolute path to bin/epic-tools> MODE=<normal|manual-merge>
```

Set `TIDY=yes` to run a tidy pass (3+ likely-touched files, new logic, refactor, or feature work). Default no.

Each child must print:

```
STATUS=ok PR=<n> SHA=<full-sha>
```

or `STATUS=fail REASON=<short>`.

Collect every child dispatched this tick. Missing status counts as fail. On
fail, label the child `epic-<N>-failed`; no auto-retry. On ok, run
`epic-tools verify-pr` against the reported PR/SHA, then merge. In normal mode,
merge only when current REST check-runs for the reported head SHA are all
successful; stale, failed, missing, or queued checks are not green. If GraphQL is
throttled, use REST check-runs and squash-merge only after the same green check.
In `manual-merge` mode, squash-merge the verified PR directly via REST:
`PUT /repos/$REPO/pulls/<n>/merge` with `merge_method=squash`. After any merge
attempt, read back the PR once — `gh api repos/$REPO/pulls/<n> --jq .merged` —
before acting on the result. If `.merged == true`, mark it merged and continue.
If `.merged == false` despite a 200 response, treat as transient: skip this PR
for the current tick and do not re-fire the merge call. Never re-attempt a
merge without first confirming `.merged == false` via a fresh GET; this prevents
duplicate squash commits from repeated merge calls on the same PR.

Pending CI in normal mode stays in-flight; failed CI labels the child failed.

For conflicted PRs, dispatch one rebase subagent per PR per tick. It rebases the
existing head branch onto `origin/<DEFAULT_BRANCH>`, resolves conflicts so all
changes survive, force-pushes with lease, waits for green CI on the new SHA, and
merges via the same CI-green REST fallback if needed.

## §4  Tick exit

`pending = in-flight + ready + deferred`.

If `pending > 0` and any subagent dispatched this tick is still running, end the
turn and let completion notifications wake the loop. If only external signals
remain, call:

```
ScheduleWakeup(
  delaySeconds: 1200,
  prompt: "/epic-run <N>",
  reason: "epic <N>: <m>/<total> merged, <k> in flight, <r> ready, <d> deferred"
)
```

Use 60-270s only when a state change is imminent; 1200s by default; 1800s+ for long-running work. If `pending == 0`, go to §4a and do not schedule a wakeup.

## §4a  Close (final tick only)

Run in order:

1. **Drop run lock first** so failure below leaves the epic re-runnable:
   `gh issue edit <N> --remove-label "$LOCK"`.
2. Race guard: confirm `epic-tools epic-status <N>` still shows `pending == 0`.
   If not, exit without closing.
3. Child issue guard: re-run `epic-tools parse-epic <N>` and refuse to close
   unless every child issue is closed. Do not close just because every visible
   PR is merged.
4. Closing audit: walk every child in `PARSE` and every epic-labelled PR,
   classify each row, post one epic comment, and refuse to close on anomalies:
   merged child closed, failed label, stuck queued PR, orphan PR, no PR/no fail,
   merged PR with open issue, or unexpected epic PR. If any anomaly exists, skip
   closing and cleanup and print the final line.
5. Close the epic only when all children are closed:
   `gh issue edit <N> --state closed`.
6. If the audit was clean and the epic closed, run `epic-tools cleanup <N>` to
   drop orch and child agent worktrees on epic-N branches, run
   `git worktree prune`, and delete merged/squash-merged `epic-<N>-*` and
   `worktree-agent-*` branches. Then explicitly sweep any remaining remote refs:
   ```bash
   gh api repos/$REPO/git/refs/heads --jq '.[].ref' \
     | grep 'refs/heads/epic-<N>-' \
     | while read ref; do gh api repos/$REPO/git/$ref -X DELETE; done
   ```
   One pass, post-close, only after audit confirms full success.
7. Final line:
   `epic #<N> | <m>/<total> merged | done`. Append open children and audit
   anomaly count when present. Do not call `ScheduleWakeup`.

No extra orchestrator gate runs here. If a regression slipped through PR CI, the
user can run `epic-tools revert <N>` manually.

## Abort

On "abort" / "kill the epic": `TaskStop` agents spawned this tick, remove
`$LOCK` with `gh issue edit <N> --remove-label "$LOCK"`, report stopped agents
and open PRs, and do not schedule a wakeup. "Stop the loop" does the same minus
stopping children.

## Self-improvement

- `dispatch.md`: child prompt, scope, tests, PR, verifier, merge, and bail rules.
- `SKILL.md`: orchestrator lifecycle, dispatch mechanics, resume, and close flow.
