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

### Codex → phased out

The project is Claude-only now. The entire former `skills/codex/` tree (its epic skills plus
`quick-research`, `tidy`, and symlinks to shared skills) lives at `skills/codex/`. The shared skills
themselves remain active under the top-level `skills/shared/` for Claude.
