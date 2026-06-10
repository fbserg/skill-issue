# Claude Code Hooks

Five production-tested hooks for Claude Code. Drop them in, wire up `settings.json`, ship with less foot-shooting.

## Index

| Hook | Event | Matcher | What it does |
|---|---|---|---|
| [`edit-guard`](edit-guard/) | `PreToolUse` | `Edit\|Write\|NotebookEdit` | Warn at 3 / hard-block at 8 direct edits on Fable/Opus. Keeps expensive models as orchestrators. |
| [`git-no-bypass`](git-no-bypass/) | `PreToolUse` | `Bash` | Block `--no-verify` and `core.hooksPath` overrides. Hooks exist for a reason. |
| [`settings-guard`](settings-guard/) | `PreToolUse` | `Edit\|Write` | Block invalid fields (`mcpServers`, `disabledSkills`) in `settings.json`. |
| [`session-context`](session-context/) | `SessionStart` | _(none)_ | Inject current branch + last 5 commits into every session's context. |
| [`confetti`](confetti/) | `Stop` | _(none)_ | Fire Raycast confetti after a successful deploy. macOS + Raycast required. |

## Quick install (all five)

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
      }
    ]
  }
}
```

Replace `/path/to/` with the absolute path to this repo clone.

## Patterns worth stealing

**The proof-gate pattern** — a `Stop` hook that blocks Claude from declaring "done" while the repo has unpushed production code. The idea: on `Stop`, check `git log origin/main..HEAD --oneline` in the project directory; if commits exist and the project has a deploy path, emit a `permissionDecision: "deny"` with a message like "you have N unpushed commits — run push-main or tell me this is intentional." This enforces the "ship the whole feature" norm without relying on Claude remembering to check. The implementation is project-entangled (depends on knowing your deploy command and what counts as "production") so it's not shipped here, but the hook skeleton is identical to `session-context.sh` on the output side and `confetti-gate.sh` on the marker-check side.
