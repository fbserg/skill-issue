# skill-issue — flat index

Primary audience: LLM agents. Use this file to locate skills, hooks, tools, and docs without traversing the tree.

## Layout

- `skills/claude/` — skills installed into `~/.claude/skills/`
- `skills/codex/` — skills installed into `~/.codex/skills/`
- `skills/shared/` — skills symlinked into both `~/.claude/skills/` and `~/.codex/skills/`
- `agents/` — named subagent types with pinned model/effort, installed into `~/.claude/agents/`
- `hooks/claude/` — Claude Code hooks (PreToolUse / Stop event handlers)
- `tools/epic-tools/` — CLI used by epic-run and epic-retro for GitHub operations
- `scripts/` — repo maintenance scripts
- `docs/` — install guide, env sharing, publication checklist

---

## Claude skills (`skills/claude/`)

| Name | Path | TLDR |
|---|---|---|
| adversary | `skills/claude/adversary/SKILL.md` | Cross-model adversarial review: sends a plan or diff to Codex (GPT) for a red-team pass before committing. |
| deep-research | `skills/claude/deep-research/SKILL.md` | Opus-planned multi-source research with disconfirmation lens, GRADE evidence tiers, and a saturation loop. |
| epic-plan | `skills/claude/epic-plan/SKILL.md` | Scope a topic into a GitHub epic + child issues, with staged research and one-at-a-time clarifying questions. |
| epic-research | `skills/claude/epic-research/SKILL.md` | Pre-plan research: three parallel agents on competitors, tech peers, and GitHub code; output feeds epic-plan. |
| epic-retro | `skills/claude/epic-retro/SKILL.md` | Mine closed epic PRs and followup issues for ranked improvements to epic-plan/epic-run. |
| epic-run | `skills/claude/epic-run/SKILL.md` | Execute a planned epic: fan children into isolated worktrees, verify PRs, merge in dependency order. |
| resolve-issue | `skills/claude/resolve-issue/SKILL.md` | Heavyweight pipeline for tier 2-3 GitHub issues: assess → plan → implement → test → review → PR. Never merges. |
| simplify-sweep | `skills/claude/simplify-sweep/SKILL.md` | Batch-clean a pushed commit range via headless Sonnet /simplify per area; orchestrator reviews and commits. |

---

## Codex skills (`skills/codex/`)

| Name | Path | TLDR |
|---|---|---|
| epic-plan | `skills/codex/epic-plan/SKILL.md` | Same 7-stage epic-plan flow adapted for Codex workers. |
| epic-research | `skills/codex/epic-research/SKILL.md` | Parity copy of the Claude epic-research skill for Codex sessions. |
| epic-run | `skills/codex/epic-run/SKILL.md` | Codex adapter for the epic-run orchestrator; dependency-ordered workers, isolated workspaces, orchestrator merges. |
| quick-research | `skills/codex/quick-research/SKILL.md` | Lightweight multi-agent fan-out research for practical tradeoff and comparison questions. |
| tidy | `skills/codex/tidy/SKILL.md` | Anti-slop pass on changed code: delete phantom abstractions, flatten ceremony, reuse existing utilities. |

---

## Shared skills (`skills/shared/`) — installed for both Claude and Codex

| Name | Path | TLDR |
|---|---|---|
| authentic-writing | `skills/shared/authentic-writing/SKILL.md` | Router: delegates prose audits to authenticity-check and rewrites to humanizer; keeps diagnosis and rewriting separate. |
| authenticity-check | `skills/shared/authenticity-check/SKILL.md` | Score how authentically text reads as human-written; returns band + 0-100 score + span-level flags. Never rewrites. |
| humanizer | `skills/shared/humanizer/SKILL.md` | De-slop AI prose: remove generative tells (delve, em-dash overuse, rule-of-three padding) while preserving meaning. |
| issue-sweep | `skills/shared/issue-sweep/SKILL.md` | Claim oldest eligible GitHub issues, fix each in an isolated worktree, prove locally, open PRs. Never merges. |
| zero | `skills/shared/zero/SKILL.md` | Destructive repo reset: checkpoint, merge all branches/worktrees into main, push. Read before use. |

---

## Hooks (`hooks/claude/`)

| Name | Path | Event | TLDR |
|---|---|---|---|
| confetti | `hooks/claude/confetti/confetti-gate.sh` | Stop | Fire Raycast confetti after a successful deploy/push. macOS + Raycast only. |
| edit-guard | `hooks/claude/edit-guard/edit_guard.py` | PreToolUse | Warn at 3 / hard-block at 8 direct edits per session on Fable/Opus models. |
| git-no-bypass | `hooks/claude/git-no-bypass/git-no-bypass.sh` | PreToolUse | Block `--no-verify` and `core.hooksPath` overrides in git commands. |
| rtk-rewrite | `hooks/claude/rtk-rewrite/rtk-rewrite.sh` | PreToolUse | Rewrite verbose Bash commands through `rtk` to compress tool output. Needs `brew install rtk`. |
| proof-gate | `hooks/claude/proof-gate/proof-gate.sh` | Stop | Block "done" sign-offs while uncommitted code or unpushed commits exist. |
| session-context | `hooks/claude/session-context/session-context.sh` | Start | Inject current branch + recent commits into every session automatically. |
| settings-guard | `hooks/claude/settings-guard/settings-guard.sh` | PreToolUse | Block writes to settings.json that contain invalid fields. |

Combined `settings.json` snippet: `hooks/claude/README.md`

---

## Tools / Scripts

| Name | Path | TLDR |
|---|---|---|
| epic-tools | `tools/epic-tools/bin/epic-tools` | CLI for GitHub operations used by epic-run and epic-retro (PR verification, issue claiming, plan-to-epic). |
| claude-spend | `tools/claude-spend/spend.py` | Claude Code per-project spend analyzer (per-session/per-skill token+cost rollup, cache-tier aware); stolen from hong (https://github.com/hyang0129/dot-claude). |
| check-install | `scripts/check-install.py` | Verify local symlinks point at this repo's copies, not stale older versions. |
| check-links | `scripts/check-links.py` | Doc-link drift guard: verify every relative markdown link in tracked .md files resolves on disk. |
| install | `scripts/install.sh` | Symlink all skills and epic-tools into the right runtime dirs. Idempotent. |

---

## Docs

| File | TLDR |
|---|---|
| `docs/install.md` | Full install instructions with symlink commands for Claude, Codex, and hooks. |
| `docs/env-sharing.md` | How to share environment config across Claude and Codex installs. |
| `docs/publication-checklist.md` | Checklist for publishing new skills or hooks to this repo. |
| `docs/subagent-model-effort.md` | How to pin model AND effort for subagents via named agent types — built-ins inherit session effort; `model:` alone is not enough. Ships with `agents/`. |

---

## Agents (`agents/`)

| Name | Model / effort | TLDR |
|---|---|---|
| bulk | haiku / low | Mechanical fan-out: bulk reads, summaries, transforms. |
| worker | sonnet / medium | Default delegate for implementation, review, research with writes. |
| explore-mid | sonnet / medium | Read-only research fan-out when depth matters. |
| opus-worker | opus / medium | One Opus call only: escalate a single subtask Sonnet failed on, or run a single convergence step (synthesis, panel verdict). |
