# session-context

Injects current branch and recent commits into Claude's context at session start.

## What it does

On `SessionStart`, runs `git branch --show-current` and `git log --oneline -5` in the project directory and emits them as `additionalContext`. Claude sees the branch name and last 5 commits at the top of every session without you having to paste them.

## Why

Saves the "what branch are we on / what did we last ship" question at the start of every session. Particularly useful when you switch branches frequently or have multiple worktrees.

## Caveats

- Requires `CLAUDE_PROJECT_DIR` to be set — Claude Code sets this automatically when you open a project. No-ops silently if unset (e.g. plain `claude` invocation outside a project).
- Only shows the project's git state, not worktree-specific state if you're in a worktree at a different path.

## Install

```jsonc
// .claude/settings.json or ~/.claude/settings.json
{
  "hooks": {
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/hooks/claude/session-context/session-context.sh"
          }
        ]
      }
    ]
  }
}
```
