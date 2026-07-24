# skill-issue — flat index

Primary audience: LLM agents. Use this file to locate skills, hooks, tools, and docs without traversing the tree.

## Layout

- `skills/codex/` — skills installed into `~/.codex/skills/`
- `skills/claude/` — skills installed into `~/.claude/skills/`
- `skills/shared/` — skills symlinked into `~/.claude/skills/`; `zero` is also symlinked into `~/.codex/skills/`
- `agents/` — named subagent types with pinned model/effort, installed into `~/.claude/agents/`
- `hooks/claude/` — Claude Code hooks (PreToolUse / Stop event handlers)
- `config/CLAUDE.md` — stale fork, not deployed; pointer to the live operating rules. Do not copy into a project or `~/.claude/`.
- `deprecated/` — archived skills/tools (epic-run family, Codex, epic-tools); not installed. See `deprecated/README.md`.
- `scripts/` — repo maintenance scripts
- `docs/` — install guide, env sharing, publication checklist
- `vale/` — `AItells` vale style (canonical merged AI-tells prose linter, three severity tiers) plus `build.sh` and the built `AItells.zip` package consumers `Packages =` at. See `vale/README.md`.

---

## Claude skills (`skills/claude/`)

| Name | Path | TLDR |
|---|---|---|
| adversary | `skills/claude/adversary/SKILL.md` | Cross-model adversarial review: sends a plan or diff to Codex (GPT) for a red-team pass before committing. |
| blitz | `skills/claude/blitz/SKILL.md` | Lightweight executor for ad-hoc lanes: parallel worktrees + adversarial review, no pipeline ceremony. The fast alternative to /issue batch. |
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
| blitz | `skills/codex/blitz/SKILL.md` | Fast execution of ad-hoc lanes in parallel worktrees with adversarial review. |
| epic-plan | `skills/codex/epic-plan/SKILL.md` | Scope broad work into tracker + child issues; no GitHub writes until GO. |
| issue | `skills/codex/issue/SKILL.md` | Front door for GitHub issue work; scope ideas or route issue numbers to resolve-issue. |
| refactor-dupes | `skills/codex/refactor-dupes/SKILL.md` | Detect duplicates, approve an architecture brief, refactor one cluster in a worktree PR. |
| resolve-issue | `skills/codex/resolve-issue/SKILL.md` | One GitHub issue to review-ready PR in an isolated worktree; never merges. |
| ww | `skills/codex/ww/SKILL.md` | Worktree workflow: branch, plan, implement, check, draft PR; main untouched. |
| zero | `skills/shared/zero/SKILL.md` | Shared destructive cleanup with proof-before-delete classification. |

---

## Shared skills (`skills/shared/`) — installed for Claude; `zero` also for Codex

| Name | Path | TLDR |
|---|---|---|
| authentic-writing | `skills/shared/authentic-writing/SKILL.md` | Router: delegates prose audits to authenticity-check and rewrites to humanizer; keeps diagnosis and rewriting separate. |
| authenticity-check | `skills/shared/authenticity-check/SKILL.md` | Score how authentically text reads as human-written; returns band + 0-100 score + span-level flags. Never rewrites. |
| humanizer | `skills/shared/humanizer/SKILL.md` | De-slop AI prose: remove generative tells (delve, em-dash overuse, rule-of-three padding) while preserving meaning. |
| zero | `skills/shared/zero/SKILL.md` | Destructive repo reset: checkpoint, merge all branches/worktrees into main, push. Read before use. |

---

## Hooks (`hooks/claude/`)

Published mirror of the live hook set; canonical copies run from a private config repo.

| Name | Path | Event | TLDR |
|---|---|---|---|
| expensive_model_edit_guard | `hooks/claude/expensive_model_edit_guard.py` | PreToolUse | Warn at 3 / hard-block at 8 direct edits per session on Fable/Opus models. |
| edit_guard_backstop | `hooks/claude/edit_guard_backstop.py` | Stop | Catches the edit guard silently failing to fire (e.g. bypassPermissions regression). |
| effort_spawn_guard | `hooks/claude/effort_spawn_guard.py` | PreToolUse | Block `Agent`/`Workflow` spawns that omit a custom agent type / `agentType`. |
| guard-settings-json | `hooks/claude/guard-settings-json.sh` | PreToolUse | Block invalid fields in settings.json; protect `~/.claude/CLAUDE.md`. |
| pretool-bash | `hooks/claude/pretool-bash.sh` | PreToolUse | Block destructive Bash, filter verbose test output, RTK rewrite, pre-push build gate. |
| sessionstart-context | `hooks/claude/sessionstart-context.sh` | SessionStart | Inject current branch + recent commits into every session automatically. |
| notify-done | `hooks/claude/notify-done.sh` | Stop | Ring the terminal bell when Claude's last message is actually a question. |
| confetti-gate | `hooks/claude/confetti-gate.sh` | Stop | Fire Raycast confetti after a successful deploy/push. macOS + Raycast only. |
| stop-failure | `hooks/claude/stop-failure.sh` | StopFailure | Log API-error turn ends to a JSONL watchdog trail + terminal bell. |
| quality/ (4 hooks + shared lib) | `hooks/claude/quality/` | PreToolUse/PostToolUse/PostToolBatch/PostToolUseFailure/Stop | Format-on-write + unresolved-failure Stop gate. |

Per-hook `settings.json` snippets and excluded personal plumbing: `hooks/claude/README.md`

---

## Tools / Scripts

| Name | Path | TLDR |
|---|---|---|
| claude-spend | `tools/claude-spend/spend.py` | Claude Code per-project spend analyzer (per-session/per-skill token+cost rollup, cache-tier aware); stolen from hong (https://github.com/hyang0129/dot-claude). Not symlinked by `install.sh` — run in place: `python3 tools/claude-spend/spend.py`. |
| statusline | `tools/statusline/statusline.sh` | Claude Code status line: repo@branch +/- diff, model·effort, context bar calibrated to the real auto-compact trigger (window − 13k reserve), 5h/7d rate-limit bars with reset ETA and weekly pace delta. Not symlinked — point `statusLine.command` in settings.json at it. |
| transcript-archive | `tools/transcript-archive/backup.py` | One-way, machine-namespaced, multi-machine archiver for Claude + Codex JSONL transcripts: JSON-aware image tombstoning (replaced the v1 base64 regex, which was corrupting thinking signatures/JWTs/PDFs), never clobbers a larger copy with a smaller one, optional gzip compression, atomic writes, an identity handshake guarding against machine-id collisions and unmounted/wrong destinations, symlinked source dirs followed (cycle-safe). Storage-agnostic — point it at any synced folder, git repo, or disk. `install.sh` + `/transcript-backup` skill for one-command setup. |
| gmail-tools | `tools/gmail-tools/bin/gmail-tools` | Draft-only Gmail CLI (search, read threads, labels, attachments, compose) — every `send` endpoint is proxied to raise, so a message can only leave the mailbox via a human clicking send in Gmail. Symlinked to `~/.local/bin` by `install.sh`. |
| secrets | `tools/secrets/secrets` | Encrypt a repo's `.env` to every collaborator's GitHub SSH public key with `age` — no shared passwords, no out-of-band exchange. Full docs: `docs/env-sharing.md`. |
| check-install | `scripts/check-install.py` | Verify local symlinks point at this repo's copies, not stale older versions. |
| check-links | `scripts/check-links.py` | Doc-link drift guard: verify every relative markdown link in tracked .md files resolves on disk. |
| install | `scripts/install.sh` | Symlink all skills and delegate agents into the right runtime dirs. Idempotent. |

---

## Docs

| File | TLDR |
|---|---|
| `docs/install.md` | Full install instructions with symlink commands for Claude, Codex, and hooks. |
| `docs/env-sharing.md` | Encrypt a repo's `.env` for all GitHub collaborators using age + their SSH public keys. |
| `docs/publication-checklist.md` | Checklist for publishing new skills or hooks to this repo. |
| `docs/subagent-model-effort.md` | How to pin model AND effort for subagents via named agent types — built-ins inherit session effort; `model:` alone is not enough. Ships with `agents/`. |
| `docs/codex-subagent-model-routing.md` | Codex custom-agent model routing with live-catalog selection and rollout-based verification; records current cold-discovery failures instead of trusting self-reports. |
| `docs/multi-claude-remote.md` | Run multiple Claude Code instances on one remote box (SSH + tmux), each on a different account, with a session picker — covers the macOS Keychain-per-config-dir trap, file-vs-Keychain creds, isolation, verification, and starter scripts. |
| `docs/single-serving-site-host.md` | Host a pile of one-off static pages on one Cloudflare Worker + `public/` dir: push-to-deploy, custom domain, an authenticated POST endpoint for posting pages without a commit, and a code-listed index. Full wrangler.toml + Worker skeleton + deploy hook + post/delete CLIs. |

---

## Agents (`agents/`)

| Name | Model / effort | TLDR |
|---|---|---|
| bulk | haiku / low | Mechanical fan-out: bulk reads, summaries, transforms. |
| worker | sonnet / medium | Default delegate for implementation, review, research with writes. |
| explore-mid | sonnet / medium | Read-only research fan-out when depth matters. |
| opus-worker | opus / high | One Opus call only: escalate a single subtask Sonnet failed on, or run a single convergence step (synthesis, panel verdict). |
