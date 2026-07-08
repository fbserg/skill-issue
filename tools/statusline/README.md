# statusline

Claude Code status line: `repo@branch* +ins -del | model·effort | context bar | 5h/7d rate limits`.

```
skill-issue@main* +42 -7 | fable·high | ████▌    212k/287k | 5h ███    48% in 2h13m | 7d ██     31% +4%
```

## What it shows

- **repo@branch** — cyan repo, green branch (yellow + `*` when dirty), plus `+added -deleted` line counts against HEAD. Detached HEAD shows the short SHA.
- **model·effort** — shortened model name (`Opus 4.8 (1M context)` → `opus1m`), effort level colored by tier (low=green … max=red).
- **Context bar** — fills toward the point where auto-compaction *actually* fires, not the raw window. Claude Code's real trigger is `min(window · pct/100, window − 13000)` — the fixed 13k output reserve is why a 300k window compacts at 287k. Respects `CLAUDE_CODE_AUTO_COMPACT_WINDOW` and `CLAUDE_AUTOCOMPACT_PCT_OVERRIDE`. Deliberately ignores stdin's `used_percentage`, which is computed against the raw window and reads ~29% at the moment compaction fires.
- **5h / 7d rate limits** — usage bars with time-to-reset. Readings are account-global, so a shared cache (`/tmp/claude/statusline-ratelimits.json`) fills in a bucket missing from this render's stdin — live readings always win, the cache never overrides them, so the bar recovers in both directions. The 7d bar adds a **pace delta**: usage % minus elapsed-week %, red when burning ≥10% ahead of schedule, green when ≥10% under.

Bars use eighth-block characters (`▏▎▍…█`) for sub-cell resolution and shift green → orange → yellow → red at 50/70/90%.

## Install

Not symlinked by `install.sh` — copy or point at it directly in `~/.claude/settings.json`:

```json
"statusLine": {
  "type": "command",
  "command": "bash /path/to/skill-issue/tools/statusline/statusline.sh",
  "refreshInterval": 30
}
```

Requires `jq`. Handles both GNU and BSD `date` (macOS works out of the box). Each render also dumps its stdin to `/tmp/claude/statusline-last.json` — handy for debugging what Claude Code actually feeds the status line.
