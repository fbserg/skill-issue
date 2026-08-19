# Launch guard

`scripts/launch-guard.sh` refuses a live CLI-agent launch when another launch
in the same working directory began with the same normalized prompt prefix.
It addresses a measured incident where byte-identical Codex prompts launched
16 minutes apart in one checkout and both completed, wasting about $14 and
risking concurrent writes.

```bash
scripts/launch-guard.sh [--force] [--window-min N] [--prompt-file F | --prompt "text"] -- <command> [args...]
scripts/launch-guard.sh -- codex exec -s workspace-write -C <wt> -o <out> "$PROMPT"
scripts/launch-guard.sh -- claude -p "$PROMPT"
```

Without `--prompt` or `--prompt-file`, the last command argument is treated as
the prompt. Whitespace is collapsed and trimmed; only its first 200 characters
join the current working directory in the SHA-256 launch key. The duplicate
window defaults to 30 minutes. `--force` warns and launches anyway.

State lives in `${LAUNCH_GUARD_DIR:-$HOME/.claude/launch-guard}` as one atomic
JSON entry per key. Exit 2 means invalid usage and exit 3 means a duplicate was
refused; otherwise `exec` makes the guarded command's exit status the result.

The script records its own PID and then uses `exec`, so the real command keeps
that PID and no wrapper remains. An exit trap therefore cannot clean state;
each invocation prunes entries with a dead PID or an age greater than 24 hours.
