# Claude Code hooks

Published mirror of the hooks the author actually runs. **The canonical live
copies run from a private config repo** (`~/.claude/hooks` is a symlink into
it); this directory is synced here manually, so it can lag the live set.
Treat it as reference/install material, not a live-editable source.

Seven hooks, wired via `~/.claude/settings.json`. Paths below assume you drop
these files under `~/.claude/hooks/` (adjust if you install elsewhere).

## Removed: expensive_model_edit_guard.py + edit_guard_backstop.py (tombstone)

Deleted from the live hook set 2026-07-24 per the DECISIONS.md subtraction-pass
ruling (`docs/DECISIONS.md`, "2026-07-24 — Subtraction pass"): across 14,509
transcripts the guard fired 510 times without changing edit behavior — the
warn tier allowed retry by design, the hard cap was lifted whenever it bound,
and 94% of expensive-model edits happened regardless — so the prose rule it
enforced ("expensive model never edits") was deleted along with it rather than
re-asserted. Reopen condition (an unreviewed main-thread edit ships a defect a
delegate would have caught) is recorded there, unmet as of this mirror sync.
Migration: if you copied these two files under `~/.claude/hooks/` and wired
them in `settings.json`, remove both files and their `PreToolUse`/`Stop`
entries.

## effort_spawn_guard.py

Blocks `Agent`/`Workflow` spawns that would silently inherit the main
thread's effort level: `Agent` calls must name a custom `subagent_type`
(built-ins like `general-purpose`/`claude`/`Plan` are rejected; `Explore`
stays allowed for cheap lookups), and `Workflow` scripts must pass
`agentType` on every `agent()` call. Override with
`CLAUDE_EFFORT_GUARD_OFF=1`.

```json
"PreToolUse": [
  {
    "matcher": "Agent|Workflow",
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/effort_spawn_guard.py"}
    ]
  }
]
```

## guard-settings-json.sh

Guards sensitive config files on `Edit`/`Write`: blocks all edits to
`~/.claude/CLAUDE.md` outright, and blocks writes to
`settings.json`/`settings.local.json` that contain fields that don't belong
there (`mcpServers`, `disabledSkills`), pointing at where they actually go.

```json
"PreToolUse": [
  {
    "matcher": "Edit|Write",
    "hooks": [
      {"type": "command", "command": "~/.claude/hooks/guard-settings-json.sh"}
    ]
  }
]
```

## pretool-bash.sh

Consolidated `PreToolUse` hook for `Bash` commands, three checks in one
pass so there's a single JSON output path: blocks catastrophic/destructive
commands outright, filters verbose test output down to failures, and
applies RTK's token-saving command rewrite. Also runs a pre-push gate
(tsc/build/test) before `git push` — that phase is tuned to this author's
JS/TS project conventions; adjust or strip it for other stacks. Skip the
gate per-invocation with `SKIP_PREPUSH_GATE=1`. Project-specific command
rewrites (e.g. per-project VM ssh routing) were stripped from this
published mirror and live only in the private config repo.

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {"type": "command", "command": "~/.claude/hooks/pretool-bash.sh"}
    ]
  }
]
```

## notify-done.sh

On `Stop`, rings the terminal bell (`\a`) when Claude's last message ends
in a question — i.e. it's actually waiting on the user, not just finishing
a turn. Skips CI and non-interactive (`-p`/`--print`) invocations.

```json
"Stop": [
  {
    "hooks": [
      {"type": "command", "command": "~/.claude/hooks/notify-done.sh", "async": true}
    ]
  }
]
```

## confetti-gate.sh

On `Stop`, fires a Raycast confetti animation once after a successful
`just push-main` (or equivalent) — the push recipe touches
`~/.claude/.confetti-pending` on success, and this hook clears the flag and
celebrates. A no-op without a push recipe that sets the marker.

```json
"Stop": [
  {
    "hooks": [
      {"type": "command", "command": "~/.claude/hooks/confetti-gate.sh", "async": true}
    ]
  }
]
```

## stop-failure.sh

On `StopFailure` (turn ended due to an API error — rate limit, overload,
server error, …), appends the event payload as a JSONL line to
`~/.claude/logs/stop-failures.jsonl` and rings the terminal bell. Completion
notifications already exist; this is the missing half — a durable trace when
a session (especially a background fleet lane) dies silently instead of
finishing. The harness ignores this hook's output and exit code, so it's a
pure observer.

```json
"StopFailure": [
  {
    "hooks": [
      {"type": "command", "command": "~/.claude/hooks/stop-failure.sh", "async": true}
    ]
  }
]
```

## quality/ — format-on-write + unresolved-failure gate

Five-stage suite sharing `quality/claude_quality_lib.py`:

- **`claude_quality_pre_tool.py`** (`PreToolUse`, matcher `Bash`) — records
  pre-command state so failures can be attributed correctly.
- **`claude_quality_post_tool.py`** (`PostToolUse`, matcher
  `Bash|Edit|Write|MultiEdit`) — stages touched paths for the batch stage;
  does no formatting itself.
- **`claude_quality_post_batch.py`** (`PostToolBatch`) — drains staged
  paths, runs formatters once per batch (not once per edit, to keep
  system-reminder noise down), and surfaces a single batch-level context
  message on failures.
- **`claude_quality_post_failure.py`** (`PostToolUseFailure`, matcher
  `Edit|Write|MultiEdit|Bash`) — same staging as post_tool, so a
  partial-write-then-fail still gets picked up.
- **`claude_quality_stop.py`** (`Stop`) — blocks the stop if unresolved
  quality failures remain, re-verifying against the linter (not just a
  cached hash) before blocking, and dropping entries whose files changed
  since the failure was recorded.

```json
"PreToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/quality/claude_quality_pre_tool.py"}
    ]
  }
],
"PostToolUse": [
  {
    "matcher": "Bash",
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/quality/claude_quality_post_tool.py"}
    ]
  },
  {
    "matcher": "Edit|Write|MultiEdit",
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/quality/claude_quality_post_tool.py"}
    ]
  }
],
"PostToolBatch": [
  {
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/quality/claude_quality_post_batch.py"}
    ]
  }
],
"PostToolUseFailure": [
  {
    "matcher": "Edit|Write|MultiEdit|Bash",
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/quality/claude_quality_post_failure.py"}
    ]
  }
],
"Stop": [
  {
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/quality/claude_quality_stop.py"}
    ]
  }
]
```

## Not shipped here

Personal plumbing kept in the private config repo, excluded because it's
either machine-specific or has no reuse value outside the author's setup:
`caffeinate.sh` (Mac sleep prevention), `idle-stamp.sh` and `warp-status.sh`
(Warp terminal integration), `epic-tally-subagent.sh` (attributes
background-agent token spend to a private epic-cost-tracking file keyed to
this author's directory layout). RTK's command rewriting runs inside
`pretool-bash.sh` (Phase 3 shells out to `rtk rewrite`); the RTK CLI's own
`rtk hook claude` does the same job, but wire exactly one of the two — the
author ran both for a while and the duplicate rewrite pass corrupted
compound-predicate `find` commands that Phase 3 deliberately passes through.

`anxiety-panel.py` (advisory Stop-hook review panel: untested edits,
destructive commands, possible secrets, leftover debug noise, scope creep)
lives in the source hooks directory but is deliberately wired per-project
via a repo's `.claude/settings.local.json`, not globally. Not shipped.
