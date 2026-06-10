# edit-guard

Prevents expensive models (Fable/Opus) from making too many direct code edits in a session.

## What it does

- Warns (deny-once, re-attemptable) at **3** direct `Edit`/`Write`/`NotebookEdit` calls on an expensive model
- Hard-blocks at **8** direct edits
- Passes silently on Sonnet/Haiku sessions and subagent (sidechain) calls
- Exempts `.md`, `.txt`, config files not under source trees, and `.claude/` paths

## Why

Expensive models are good orchestrators; they're expensive implementors. This hook enforces "dispatch a Sonnet subagent for the bulk work, review the diff" by friction rather than discipline.

## Override

```bash
# env var (current process only)
EDIT_GUARD_OFF=1 claude ...

# per-session file override
touch /tmp/edit-guard-off-<session_id>
# or just say "edit guard off" to Claude — it knows to create the file
```

## Install

```jsonc
// .claude/settings.json or ~/.claude/settings.json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Edit|Write|NotebookEdit",
        "hooks": [
          {
            "type": "command",
            "command": "python3 /path/to/hooks/claude/edit-guard/edit_guard.py"
          }
        ]
      }
    ]
  }
}
```

Replace `/path/to/` with the absolute path to this repo, or symlink the file.
