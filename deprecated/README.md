# deprecated/

Archived skills and tools. Kept for history and reference; **not installed**, not maintained.
`scripts/install.sh` and `scripts/check-install.py` ignore this directory.

## What's here and why

### The `epic-run` pipeline → superseded by `/issue` → `/resolve-issue`

The repo started epic-centric: `epic-plan` drafted an epic, `epic-run` orchestrated the child PRs,
and `epic-research`/`epic-retro` bookended it, glued by the `epic-tools` CLI. Execution has since moved
to the leaner, self-scaling `/issue` (front door) → `/resolve-issue` (role-separated subagents,
multi-lens blocker-verified review) path. `epic-plan` survives — rebuilt to hand its child issues to
`/issue` — so the rest of the family retired here:

- `skills/claude/epic-run/` — the orchestrator (dispatch ordering, auto-merge, resume).
- `skills/claude/epic-research/` — pre-plan research; folded into the rebuilt `epic-plan`'s own
  parallel research stage.
- `skills/claude/epic-retro/` — closed-epic retrospective miner.
- `skills/shared/epic-run-contract.md`, `skills/shared/epic-child-template.md` — epic-run-era contracts.
- `tools/epic-tools/` — GitHub CLI used only by `epic-run`/`epic-retro`; the rebuilt `epic-plan` calls
  `gh` directly.

### Codex → the 2026-06-20-era epic pipeline, not Codex itself

What's archived here is the *old* Codex epic pipeline (the `epic-run` family, `quick-research`,
`tidy`) from the 2026-06-20 "full-Claude orchestration" ruling that retired it. The live
`skills/codex/` tree was rebuilt afterward and is a going concern: DECISIONS.md 2026-07-05
reinstated Codex as the default builder inside the Claude-judged `/resolve-issue` pipeline, and
the 2026-07-16 entry separately sanctions `skills/codex/{blitz,issue,epic-plan,resolve-issue}` as
standalone front doors for driving Codex CLI directly, outside Claude Code. Nothing about Codex
itself is deprecated — only this specific pipeline shape.
