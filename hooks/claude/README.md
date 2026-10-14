# Claude Code hooks

Standalone hooks that started as copies of the author's live set. The live
versions run from a private config repo and have moved on (the live
`pretool-bash.sh` now calls a shared policy script). These are not synced.

Three hooks. Wire them in `~/.claude/settings.json` with `$HOME` paths so one
settings file serves macOS and Linux:

| Hook | Event (matcher) | What it does |
|---|---|---|
| `pretool-bash.sh` | PreToolUse (`Bash`) | Blocks catastrophic commands (recursive delete of `/` or `~`, force-push to main, dropping tables, …), foreground `sleep N && …`, whole-disk or whole-home `find` (macOS TCC popup storm), Bash writes that escape an isolated worktree into the shared checkout, and bare `git stash` on a dirty tree. `rm` inside `$HOME/projects` is always allowed. |
| `caffeinate.sh` | SessionStart | `caffeinate -i -w <claude pid>`, self-releasing; no-op off macOS. |
| `confetti-gate.sh` | Stop (async) | Raycast confetti once after a successful main push (the push recipe touches `~/.claude/.confetti-pending`). |

```json
"hooks": {
  "PreToolUse": [
    {"matcher": "Bash",           "hooks": [{"type": "command", "command": "$HOME/.claude/hooks/pretool-bash.sh", "timeout": 15}]}
  ],
  "SessionStart": [{"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/caffeinate.sh", "timeout": 10}]}],
  "Stop":         [{"hooks": [{"type": "command", "command": "$HOME/.claude/hooks/confetti-gate.sh", "timeout": 10, "async": true}]}]
}
```

## Removed 2026-10-14

| Removed | Why |
|---|---|
| `effort_spawn_guard.py` | Not wired in the live settings. Named agent types already pin model and effort. |
| `guard-settings-json.sh` | Not wired in the live settings. |

## Removed 2026-09-06 (subtraction pass over 90 days of transcripts)

Deleted for zero or negative value. If you copied any of these, remove the
file and its `settings.json` entry.

| Removed | Why |
|---|---|
| `session_age_reminder.py` | Never reached a transcript; the 8h+ sessions it targeted were intentional fan-outs. |
| `subagent-delivery-gate.sh` | Never fired outside its own tests. |
| `configchange-missing-hooks.sh` | Two fires ever, both against a temp file. |
| `notify-done.sh` | The built-in notification channel setting does the same. |
| `stop-failure.sh` | 700 log lines, nothing read them. |
| `herdr-subagent-count.sh` | Cosmetic sidebar counter, 181 lines and four registrations. |
| `quality/` formatter suite | 900 lines re-implementing lint-staged with state in `/tmp`. A repo `pre-commit` formats commits from Claude and Codex on every machine. |
| Pre-push gate inside `pretool-bash.sh` | 60% of its blocks were "node_modules missing in this worktree". Moved to each JS repo's `.githooks/pre-push`, which also gates Codex. |
| Hold-label merge guard inside `pretool-bash.sh` | 8 real blocks vs 44 "could not read labels, refusing blind". |
| `guard-settings-json.sh` | "Edit it manually" is not a path when every edit goes through an agent. |

## Removed 2026-07-24: expensive_model_edit_guard.py + edit_guard_backstop.py

Across 14,509 transcripts the guard fired 510 times without changing edit
behavior (94% of expensive-model edits happened regardless), so the prose rule
it enforced was deleted with it. Reopen condition: an unreviewed main-thread
edit ships a defect a delegate would have caught.
