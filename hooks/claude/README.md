# Claude Code Hooks

Seven production-tested hooks for Claude Code. Drop them in, wire up `settings.json`, ship with less foot-shooting.

## Index

| Hook | Event | Matcher | What it does |
|---|---|---|---|
| [`edit-guard`](edit-guard/) | `PreToolUse` | `Edit\|Write\|NotebookEdit` | Warn at 3 / hard-block at 8 direct edits on Fable/Opus. Keeps expensive models as orchestrators. |
| [`git-no-bypass`](git-no-bypass/) | `PreToolUse` | `Bash` | Block `--no-verify` and `core.hooksPath` overrides. Hooks exist for a reason. |
| [`rtk-rewrite`](rtk-rewrite/) | `PreToolUse` | `Bash` | Rewrite verbose commands through `rtk` to compress tool output before it hits context. Needs `brew install rtk`. |
| [`settings-guard`](settings-guard/) | `PreToolUse` | `Edit\|Write` | Block invalid fields (`mcpServers`, `disabledSkills`) in `settings.json`. |
| [`session-context`](session-context/) | `SessionStart` | _(none)_ | Inject current branch + last 5 commits into every session's context. |
| [`confetti`](confetti/) | `Stop` | _(none)_ | Fire Raycast confetti after a successful deploy. macOS + Raycast required. |
| [`proof-gate`](proof-gate/) | `Stop` | _(none)_ | Block "done" sign-offs while the repo has uncommitted code or unpushed commits. |

## Quick install (all seven)

```jsonc
// .claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [{ "type": "command", "command": "python3 /path/to/hooks/claude/edit-guard/edit_guard.py" }]
      },
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "/path/to/hooks/claude/git-no-bypass/git-no-bypass.sh" }]
      },
      {
        "matcher": "Bash",
        "hooks": [{ "type": "command", "command": "/path/to/hooks/claude/rtk-rewrite/rtk-rewrite.sh" }]
      },
      {
        "matcher": "Edit|Write",
        "hooks": [{ "type": "command", "command": "/path/to/hooks/claude/settings-guard/settings-guard.sh" }]
      }
    ],
    "SessionStart": [
      {
        "hooks": [{ "type": "command", "command": "/path/to/hooks/claude/session-context/session-context.sh" }]
      }
    ],
    "Stop": [
      {
        "hooks": [{ "type": "command", "command": "/path/to/hooks/claude/confetti/confetti-gate.sh" }]
      },
      {
        "hooks": [{ "type": "command", "command": "/path/to/hooks/claude/proof-gate/proof-gate.sh" }]
      }
    ]
  }
}
```

Replace `/path/to/` with the absolute path to this repo clone.
