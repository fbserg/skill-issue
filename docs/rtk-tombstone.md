# rtk — tombstone (2026-07-30)

rtk ("Rust Token Killer", homebrew `rtk`, v0.44.1 at death) was a CLI proxy that
filtered command output before it hit model context. Ran here ~13 months.
Removed everywhere 2026-07-30. This doc is the setup record and the autopsy, so
nobody re-adopts it (or a successor) without clearing the same evidence bar.

## How it was wired

| surface | mechanism |
|---|---|
| Claude Code | `~/.claude/hooks/pretool-bash.sh` Phase 3: piped every Bash command through `rtk rewrite`; on exit 0/3 substituted the rewritten command via `updatedInput` + auto-allow |
| Codex | `~/.codex/RTK.md` (symlink into etc `configs/codex/RTK.md`) + AGENTS.md bullet instructing the model to call `rtk <cmd>` directly for bulk output |
| custom filters | `~/Library/Application Support/rtk/` config: `exclude_commands` curation, `rtk:toml` per-command filters (`ps`, ssh) |
| escape hatch | `rtk proxy <cmd>` ran unfiltered; global CLAUDE.md documented it |
| stats | `history.db` (sqlite) logged input/output/saved tokens per command; `rtk gain` reported them |

## Why it was cut

`rtk gain` claimed **92.3% savings** (766M tokens lifetime, 305M/30d). Audit
2026-07-30 (this repo's decision bar: measure against the real counterfactual):

- **94% of claimed savings were phantom.** Claude Code truncates Bash output at
  30k chars (~7.5k tokens). Capping each command's saving at what the model
  would actually have seen: 305M/30d claimed → **18.2M real**, of which only
  ~9–11M was Claude-side (rest Codex direct calls).
- **47% of invocations saved zero.** Median saving 1.6%. Real wins concentrated
  in three buckets: gradle build filtering (5M/30d), a custom `ps` filter
  (3.4M), `cat`→`rtk read` on the Codex path (7.5M — see next bullet).
- **The Codex path was lossy.** `rtk read`-style calls returned 76 tokens for a
  21,646-token doc, 2 tokens for a 182k-token log, 4 tokens for whole CSVs —
  booked as "100% saved". Agents silently proceeded without the content.
- **Friction tax, from 30d of transcripts:** 290 `rtk proxy` bypasses (~10/day,
  each a wasted filtered run + rerun), 11 in-session complaints (`rtk find`
  mangling flags, swallowing results, corrupting `find | wc` counts, hiding
  stderr), 2,279 parse failures (benign fallbacks), one full debugging session
  ("rtk rewrite has two owners, and they disagree").
- **"Zero maintenance" was false.** The `exclude_commands` list, the hook's
  compound-`find` carve-out, and CLAUDE.md workaround lines were all scar
  tissue from rtk incidents. Upstream also changed behavior under us (v0.44
  silently flipped `read` from aggressive-filtering to passthrough).
- **Folklore generator.** "rtk suppresses the post-push deploy hook" was
  codified in three repos' AGENTS.md/CLAUDE.md and parroted by every session.
  False: git has no post-push hook type; nothing ever auto-ran
  `.githooks/post-push`, rtk or not. Wrong blame survived ~13 months because it
  shipped with a working workaround.

Net: ~1–2% of monthly token throughput in real savings, against a daily
friction tax, a lossy read path, ongoing config curation, and misdiagnosis
debt. The gradle/ps wins are reproducible with a 3-line `tail`/`grep` filter if
ever missed (pretool-bash.sh Phase 2 is the rtk-free template).

## What removal touched (2026-07-30)

- `pretool-bash.sh` Phase 3 + find carve-out deleted (Phases 0–2 remain: pre-push
  gate, destructive-command blocks, worktree escape guard, test-output filter)
- Global CLAUDE.md RTK bullet; etc/booze/booze-waterloo-links deploy-line rtk
  blame corrected; `configs/codex/RTK.md` + `~/.codex/RTK.md` symlink;
  codex AGENTS.md bullet
- `brew uninstall rtk`; `~/Library/Application Support/rtk/` and
  `~/.config/rtk/` data dirs

## Reopen condition

A single command class demonstrably dominating context bloat (measured with the
truncation-capped method above, not a tool's self-reported gross savings) AND a
filter for it that fails loudly instead of returning stubs. Any candidate tool
must be audited against: (1) the truncation counterfactual, (2) bypass rate in
real transcripts, (3) near-zero-output rows (`output < input/100`) treated as
data loss, not savings.
