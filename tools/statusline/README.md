# statusline

Claude Code status line: repo, branch, diff and drift, model and effort, context bar, prompt-cache timer, 5h/7d rate limits.

```
skill-issue main* +42-7 ⇡2  opu·h [  64%] 🌿4m  5h[  48%] ↻2h  7d[  31%] ↑4
```

## What it shows

- **Repo and branch.** Cyan repo, green branch (yellow with `*` when dirty), then `+ins-del` against HEAD. Long branch names are middle-truncated. Detached HEAD shows the short SHA.
- **Drift.** `⇡N` commits ahead of trunk, `⇣N` behind. Trunk is `origin/HEAD`, else `origin/main`, `origin/master`, `main` or `master`.
- **Model and effort.** First three letters of the model (`opu`, `son`, `fab`), then one effort letter: `l` low, `m` medium, `h` high, `X` xhigh, `x` max.
- **Context bar.** Fills toward the point where auto-compaction actually fires, not the raw window: `min(effective · pct/100, effective − 13000)`, where `effective = window − min(maxOutputTokens, 20000)`. A 500k window compacts at 467k. Respects `CLAUDE_CODE_AUTO_COMPACT_WINDOW` and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`. It ignores stdin's `used_percentage`, which is computed against the raw window.
- **Prompt-cache leaf.** Minutes until the prompt cache goes cold, from Claude Code's `prompt_cache.expires_at`. The leaf shows the cache-miss share of the last request: 🌿 under 20%, 🍂 under 50%, 🔥 above. 🥀 means the cache has expired.
- **5h and 7d rate limits.** Usage bars with time to reset. The 7d bar adds a pace delta: usage % minus elapsed-week %. It is red at 10 or more points ahead of schedule.

Bars use eighth-block characters for sub-cell resolution. Color shifts green, orange, yellow, red at 50, 70 and 90%.

## Rate-limit cache

Readings are account-wide, so the script keeps one file per account at `~/.config/burn/statusline-ratelimits/<account-uuid>.json`. A live reading on stdin always wins. The cache only fills a bucket missing from this render. Writes are atomic, so concurrent sessions cannot clobber each other. Other tools can read these files instead of spending an API call on the same numbers.

## Install

`install.sh` does not install it. Point at it in `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "bash /path/to/skill-issue/tools/statusline/statusline.sh",
  "refreshInterval": 30
}
```

Requires `jq`. Works with GNU and BSD `date`. Each render writes its stdin to `/tmp/claude/statusline-last.json` for debugging.
