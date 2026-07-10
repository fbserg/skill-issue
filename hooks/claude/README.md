# Claude Code hooks

Published mirror of the hooks the author actually runs. **The canonical live
copies run from a private config repo** (`~/.claude/hooks` is a symlink into
it); this directory is synced here manually, so it can lag the live set.
Treat it as reference/install material, not a live-editable source.

Nine hooks, wired via `~/.claude/settings.json`. Paths below assume you drop
these files under `~/.claude/hooks/` (adjust if you install elsewhere).

## expensive_model_edit_guard.py

Blocks an expensive model (Fable/Opus) from doing its own implementation
work: warns once at 3 direct `Edit`/`Write`/`NotebookEdit` calls in a
session, hard-denies at 8+. Sonnet/Haiku sessions and subagent (sidechain)
calls pass through untouched. `.md`/`.txt`/config files and anything under
`~/.claude/` are exempt. Override with `EDIT_GUARD_OFF=1` or by touching
`/tmp/edit-guard-off-<session_id>`.

```json
"PreToolUse": [
  {
    "matcher": "Edit|Write|NotebookEdit",
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/expensive_model_edit_guard.py"}
    ]
  }
]
```

## edit_guard_backstop.py

Stop-event backstop for the guard above. If a session blew past the hard
cap of direct edits with zero `PreToolUse:Edit/Write` hook executions
recorded in the transcript, the primary guard silently failed to fire (e.g.
a `bypassPermissions`-mode regression) — this hook detects that and blocks
the stop so the break gets investigated instead of going unnoticed.

```json
"Stop": [
  {
    "hooks": [
      {"type": "command", "command": "/opt/homebrew/bin/python3 ~/.claude/hooks/edit_guard_backstop.py"}
    ]
  }
]
```

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
gate per-invocation with `SKIP_PREPUSH_GATE=1`.

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

## sessionstart-context.sh

On `SessionStart`, injects the current git branch and last 5 commits as
additional context, so a fresh session opens already oriented instead of
needing a `git log`/`git status` round trip.

```json
"SessionStart": [
  {
    "matcher": "",
    "hooks": [
      {"type": "command", "command": "~/.claude/hooks/sessionstart-context.sh"}
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

## quality/ — format-on-write + unresolved-failure gate

Four-stage suite sharing `quality/claude_quality_lib.py`:

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
(Warp terminal integration), `advisor-opus-block.sh` and
`advisor-track.sh` (usage tracking for a private `advisor` tool),
`epic-tally-subagent.sh` (attributes background-agent token spend to a
private epic-cost-tracking file keyed to this author's directory layout).
`rtk hook claude` is a separate installed binary (the RTK CLI), not a
script in this tree.

`anxiety-panel.py` exists in the source hooks directory but is wired
nowhere — not in `settings.json`, not referenced by any other hook or the
statusline script. Vestigial; not shipped.
