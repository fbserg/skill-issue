# git-no-bypass

Blocks agent git commands that skip pre-commit or pre-push hooks.

## What it does

Intercepts `Bash` tool calls and exits 2 (block) if the command contains:

- `git commit --no-verify` or `git commit -n`
- `git push --no-verify`
- `git -c core.hooksPath=...` (hooks directory override)

## Why

Hooks exist for a reason — lint, tests, type checks, generated-file parity. An agent that bypasses them to avoid a failure has hidden the failure, not fixed it. If a hook is genuinely broken, the user should decide to bypass deliberately from their terminal, not have Claude do it silently.

## Caveats

- Fail-open: parse errors pass through rather than block
- Does not inspect compound commands exhaustively — aggressive enough for common patterns, not a security boundary

## Install

```jsonc
// .claude/settings.json or ~/.claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/hooks/claude/git-no-bypass/git-no-bypass.sh"
          }
        ]
      }
    ]
  }
}
```
