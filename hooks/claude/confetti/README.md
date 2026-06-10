# confetti

Fires Raycast confetti once after a successful deploy or push.

## What it does

On `Stop`, checks for a marker file at `~/.claude/.confetti-pending`. If present, opens `raycast://confetti` (Raycast's confetti animation) and removes the marker.

The trigger side is up to you — your deploy script or push wrapper should `touch ~/.claude/.confetti-pending` on success.

## Why

Purely motivational. Shipping deserves a celebration, however small.

## Requirements

- **macOS** (uses `open` to invoke a URL scheme)
- **[Raycast](https://raycast.com/)** installed

Safe no-op on Linux or without Raycast — the marker file just sits there until you clear it.

## Example trigger

```bash
# In your push/deploy script, on success:
touch ~/.claude/.confetti-pending
```

## Install

```jsonc
// .claude/settings.json or ~/.claude/settings.json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/hooks/claude/confetti/confetti-gate.sh"
          }
        ]
      }
    ]
  }
}
```
