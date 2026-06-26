# skill-issue — flat index

Primary audience: LLM agents. Use this file to locate skills, hooks, tools, and docs without traversing the tree.

## Layout

- `skills/codex/` — skills installed into `~/.codex/skills/`
- `skills/claude/` — skills installed into `~/.claude/skills/`
- `skills/shared/` — skills symlinked into `~/.claude/skills/` (Claude-only now)
- `agents/` — named subagent types with pinned model/effort, installed into `~/.claude/agents/`
- `hooks/claude/` — Claude Code hooks (PreToolUse / Stop event handlers)
- `config/CLAUDE.md` — reference `CLAUDE.md` operating rules (sanitized); copy into a project or `~/.claude/`
- `deprecated/` — archived skills/tools (epic-run family, Codex, epic-tools); not installed. See `deprecated/README.md`.
- `scripts/` — repo maintenance scripts
- `docs/` — install guide, env sharing, publication checklist

---

## Claude skills (`skills/claude/`)

| Name | Path | TLDR |
|---|---|---|
| adversary | `skills/claude/adversary/SKILL.md` | Cross-model adversarial review: sends a plan or diff to Codex (GPT) for a red-team pass before committing. |
| deep-research | `skills/claude/deep-research/SKILL.md` | Opus-planned multi-source research with disconfirmation lens, GRADE evidence tiers, and a saturation loop. |
| epic-plan | `skills/claude/epic-plan/SKILL.md` | Research-heavy planner: wide parallel research, multi-lens review of the decomposition, child issues that execute via /issue → /resolve-issue; re-enters from GitHub state. |
| issue | `skills/claude/issue/SKILL.md` | Thin front door: scope a rough idea, or hand one issue (or a batch, ≤4 concurrent) to /resolve-issue, which self-scales by tier. Never writes code, never merges. |
| resolve-issue | `skills/claude/resolve-issue/SKILL.md` | Self-scaling pipeline for one issue: light path for tier-1, full assess→plan→implement→test→review for tier 2-3, bounces a true epic to /epic-plan. The executor behind /issue. Never merges. |
| simplify-sweep | `skills/claude/simplify-sweep/SKILL.md` | Batch-clean a pushed commit range via headless Sonnet /simplify per area; orchestrator reviews and commits. |

---

## Codex skills (`skills/codex/`)

| Name | Path | TLDR |
|---|---|---|
| adversarial-review | `skills/codex/adversarial-review/SKILL.md` | Read-only adversarial review of a plan or diff before risky work lands. |
| epic-plan | `skills/codex/epic-plan/SKILL.md` | Scope broad work into tracker + child issues; no GitHub writes until GO. |
| issue | `skills/codex/issue/SKILL.md` | Front door for GitHub issue work; scope ideas or route issue numbers to resolve-issue. |
| issue-wave | `skills/codex/issue-wave/SKILL.md` | Batch issue dispatch, adversarial review, merge, push, and cleanup methodology. |
| refactor-dupes | `skills/codex/refactor-dupes/SKILL.md` | Detect duplicates, approve an architecture brief, refactor one cluster in a worktree PR. |
| resolve-issue | `skills/codex/resolve-issue/SKILL.md` | One GitHub issue to review-ready PR in an isolated worktree; never merges. |
| ww | `skills/codex/ww/SKILL.md` | Worktree workflow: branch, plan, implement, check, draft PR; main untouched. |
| zero | `skills/codex/zero/SKILL.md` | Explicit destructive cleanup with read-only inventory first; never discards work. |

---

## Shared skills (`skills/shared/`) — installed for Claude

| Name | Path | TLDR |
|---|---|---|
| authentic-writing | `skills/shared/authentic-writing/SKILL.md` | Router: delegates prose audits to authenticity-check and rewrites to humanizer; keeps diagnosis and rewriting separate. |
| authenticity-check | `skills/shared/authenticity-check/SKILL.md` | Score how authentically text reads as human-written; returns band + 0-100 score + span-level flags. Never rewrites. |
| humanizer | `skills/shared/humanizer/SKILL.md` | De-slop AI prose: remove generative tells (delve, em-dash overuse, rule-of-three padding) while preserving meaning. |
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
| claude-spend | `tools/claude-spend/spend.py` | Claude Code per-project spend analyzer (per-session/per-skill token+cost rollup, cache-tier aware); stolen from hong (https://github.com/hyang0129/dot-claude). |
| transcript-archive | `tools/transcript-archive/backup.py` | One-way daily archiver for Claude + Codex JSONL transcripts: strips base64 image blobs, never clobbers a larger copy with a smaller one. Storage-agnostic — point it at any synced folder, git repo, or disk. |
| check-install | `scripts/check-install.py` | Verify local symlinks point at this repo's copies, not stale older versions. |
| check-links | `scripts/check-links.py` | Doc-link drift guard: verify every relative markdown link in tracked .md files resolves on disk. |
| install | `scripts/install.sh` | Symlink all skills into the right runtime dirs. Idempotent. |

---

## Docs

| File | TLDR |
|---|---|
| `docs/install.md` | Full install instructions with symlink commands for Claude, Codex, and hooks. |
| `docs/env-sharing.md` | Encrypt a repo's `.env` for all GitHub collaborators using age + their SSH public keys. |
| `docs/publication-checklist.md` | Checklist for publishing new skills or hooks to this repo. |
| `docs/subagent-model-effort.md` | How to pin model AND effort for subagents via named agent types — built-ins inherit session effort; `model:` alone is not enough. Ships with `agents/`. |
| `docs/multi-claude-remote.md` | Run multiple Claude Code instances on one remote box (SSH + tmux), each on a different account, with a session picker — covers the macOS Keychain-per-config-dir trap, file-vs-Keychain creds, isolation, verification, and starter scripts. |
| `docs/single-serving-site-host.md` | Host a pile of one-off static pages on one Cloudflare Worker + `public/` dir: push-to-deploy, custom domain, an authenticated POST endpoint for posting pages without a commit, and a code-listed index. Full wrangler.toml + Worker skeleton + deploy hook + post/delete CLIs. |

---

## Agents (`agents/`)

| Name | Model / effort | TLDR |
|---|---|---|
| bulk | haiku / low | Mechanical fan-out: bulk reads, summaries, transforms. |
| worker | sonnet / medium | Default delegate for implementation, review, research with writes. |
| explore-mid | sonnet / medium | Read-only research fan-out when depth matters. |
| opus-worker | opus / medium | One Opus call only: escalate a single subtask Sonnet failed on, or run a single convergence step (synthesis, panel verdict). |
