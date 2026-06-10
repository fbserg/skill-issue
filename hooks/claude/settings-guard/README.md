# settings-guard

Blocks writes to `settings.json` / `settings.local.json` that contain invalid fields.

## What it does

Guards `Edit` and `Write` calls targeting Claude Code settings files. Blocks:

- `mcpServers` — this field belongs in `~/.claude.json`, not `settings.json`. The hook prints the correct instructions.
- `disabledSkills` — not a real field; skills use `skillOverrides`.

## Why

Claude occasionally writes these fields into `settings.json` when asked to configure MCP servers or manage skills. They silently do nothing there. The hook catches the mistake and explains the correct location.

## Install

```jsonc
// .claude/settings.json or ~/.claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write",
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/hooks/claude/settings-guard/settings-guard.sh"
          }
        ]
      }
    ]
  }
}
```

## Dependencies

- `jq` on PATH
