# Lane watchdog — shared contract

One contract for detecting and recovering a silently-wedged background lane.
Referenced by `/blitz` and `/simplify-sweep` parallel batches
(all Agent-dispatched lanes), and `/codex-go` multi-task dispatch (bash-PID
lanes, see the variant at the bottom). Edit this file when the contract
changes — the callers point here instead of restating it, so it can't drift
out of sync with itself again.

## Cadence (the numbers, picked once)

- **Pulse:** each lane appends a timestamped status line at every phase
  transition, and at least every **5 minutes** of activity, to its own pulse
  file.
- **Poll:** one persistent `Monitor` loops every **60s** over the batch's
  pulse files.
- **Stale threshold: 20 minutes** since the last pulse line, with no
  `TERMINAL` line yet. Raised from an earlier 12-minute threshold, which
  measured a ~44% false-positive rate (13+ annotated false positives against
  3 true wedges) — a watchdog that cries wolf gets ignored, which defeats it.

## Seed at dispatch — do not let a lane write its own first line

Create `$PULSE/lane-<id>.pulse` yourself, with one initial line, **in the same
message that spawns the lane** — before the lane has run at all. A lane that
dies between dispatch and its first self-written pulse has no file yet under
the old scheme, so the monitor can't see it: the highest-probability wedge
(dead on arrival) was also the one with zero detection. Seeding at dispatch
closes that gap — the file exists, and its age starts climbing toward the
stale threshold, the moment the lane is launched.

## Namespace per batch

```
PULSE=<scratchpad>/issue-lanes-<batch-id>
mkdir -p "$PULSE"
```

`<batch-id>` is a timestamp, tracker number, or issue-set — something that
distinguishes this batch from any other running concurrently. A bare
`issue-lanes/` shared across e.g. a `/issue` batch and a `/blitz` batch
running at the same time collides: each monitor sees the other's lane files
and reports on lanes it has no authority over.

## Remediation on a `STALE` event

1. **Detect for real.**
   `claude agents --json --cwd <lane-worktree>` (add `--all` to include
   completed sessions) returns `{pid, cwd, kind, sessionId, name, status:
   busy|idle, startedAt}` for the lane's session. `Read` the lane's own pulse
   file for its last self-reported line. **Do not call `TaskOutput`** — it is
   deprecated and unavailable to subagents, and even where it resolves it
   returns a symlink to the full subagent transcript, which can overflow the
   caller's context on read. `claude agents --json` plus the pulse file gives
   the same signal without that cost. **A `TERMINAL` claim is verified, not
   trusted** — grep the lane's own pulse file for the literal line before
   treating it as done; a lane has been caught claiming a `TERMINAL` line it
   never actually wrote.
2. **Kill before restart.** A wedged-but-alive lane still holds its branch
   (`fix/issue-<N>-<slug>` or the batch's equivalent). Restarting without
   stopping it first means two live writers on the same branch, and both can
   push. `TaskStop` the wedged lane (accepts the teammate agent id or a named
   background agent) **before** dispatching any replacement — never restart
   first and clean up after.
3. **Restart via the idempotent resume path**, from the lane's existing
   worktree / GitHub state — never discard uncommitted lane work.
4. **Alive and merely slow** (status `busy`, pulse just past the threshold,
   no sign of a wedge) → log `false-positive`, take no action.
5. **Log every event.** Append to `~/.claude/logs/lane-watchdog.log`:
   timestamp, batch id, lane, age, and the action taken
   (`reported` / `killed+restarted` / `false-positive`). This log is the
   evidence for whether the watchdog earns its keep.

## Teardown

`TaskStop` the monitor itself once every lane in the batch is terminal
(landed or held) — a batch is not done while its own watchdog is still armed.

## `/codex-go` variant

`/codex-go` lanes are `codex exec` background *bash processes*, not
Agent-dispatched subagents — there is no `claude agents --json` entry for
them, and the kill primitive is `kill -TERM $(cat /tmp/codex-pid-$RUN-<n>)`,
not `TaskStop`. The cadence and process rules above still apply in spirit:
seed the PID file at launch (not after), namespace it per `$RUN`, poll every
60s, log to the same `~/.claude/logs/lane-watchdog.log`. See `codex-go.md`
step 4.5 for the bash-specific mechanics — the pattern is one contract split
across two primitives (`TaskStop` for Agent lanes, `kill -TERM` for bash
lanes), not two contracts.
