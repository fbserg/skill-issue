# skill-issue

Reusable agent skills and workflow helpers for Claude and Codex.

Agents: see [INDEX.md](INDEX.md) for a flat map of everything.

## Quickstart

```bash
# 1. Prerequisites
gh auth login   # GitHub CLI, authenticated

# 2. Clone and install
git clone https://github.com/fbserg/skill-issue
cd skill-issue
# Follow docs/install.md, or run the symlink commands in the Install section below.

# 3. Use
# In Claude Code, type:
/epic-plan "add dark mode to the settings page"
# Claude researches, drafts a GitHub epic with child issues.
# Execute children via:
/issue label:epic:<slug>
```

## Skills

### Claude (`skills/claude/`)

| Skill | Description |
|---|---|
| [`adversary`](skills/claude/adversary/SKILL.md) | Cross-model red-team: sends a plan or diff to Codex (GPT) for an adversarial pass before committing. |
| [`deep-research`](skills/claude/deep-research/SKILL.md) | Opus-planned multi-source research with disconfirmation lens, GRADE evidence tiers, and a saturation loop. |
| [`epic-plan`](skills/claude/epic-plan/SKILL.md) | Research-heavy planner: wide parallel research, multi-lens review of the decomposition, child issues that execute via /issue → /resolve-issue; re-enters from GitHub state. |
| [`issue`](skills/claude/issue/SKILL.md) | Thin front door: scope a rough idea, or hand one issue (or a batch, ≤4 concurrent) to /resolve-issue, which self-scales by tier. Never writes code, never merges. |
| [`resolve-issue`](skills/claude/resolve-issue/SKILL.md) | Self-scaling pipeline for one issue: light path for tier-1, full assess→plan→implement→test→review for tier 2-3, bounces a true epic to /epic-plan. The executor behind /issue. Never merges. |
| [`simplify-sweep`](skills/claude/simplify-sweep/SKILL.md) | Batch-clean a pushed commit range via headless Sonnet /simplify per area; orchestrator reviews and commits. |

### Shared (`skills/shared/`) — installed for Claude

| Skill | Description |
|---|---|
| [`authentic-writing`](skills/shared/authentic-writing/SKILL.md) | Router: delegates prose audits to authenticity-check and rewrites to humanizer. |
| [`authenticity-check`](skills/shared/authenticity-check/SKILL.md) | Score human authenticity and flag AI-sounding spans without rewriting. |
| [`humanizer`](skills/shared/humanizer/SKILL.md) | De-slop AI prose: remove generative tells while preserving meaning. |
| [`zero`](skills/shared/zero/SKILL.md) | Destructive repo reset: checkpoint, merge all branches/worktrees into main, push. Read before use. |

## Routing an issue

| You have | Use |
|---|---|
| An issue number | `/issue <N>` — hands it to `/resolve-issue`, which self-scales by tier |
| A rough idea (no issue yet) | `/issue <free text>` — scopes it, files the issue, then dispatches |
| Multiple issues | `/issue last 5` or `/issue 42 43 44` — fans out ≤4 concurrent `/resolve-issue` lanes |
| A true epic (multi-session, multiple deliverables) | `/epic-plan <topic>` → `/issue label:epic:<slug>` |

Claiming (assign yourself), plan-comment-before-branch, and PR-only delivery are built in — you never merge your own PR.

## Requirements

- Git
- GitHub CLI (`gh`) authenticated: `gh auth login`
- [`uv`](https://docs.astral.sh/uv/) for `gmail-tools` (auto-installs its Google deps on first run)
- Claude Code with local skill directory support

### Optional

- `advisorModel` set in Claude Code settings — enables `advisor()` calls in `dispatch.md`

## Install

See [docs/install.md](docs/install.md) for full instructions.

`skill-issue` is the canonical source for these skills. Edit the files in this
checkout, then run `python3 scripts/check-install.py` to catch any local install
that points at an older copy. Run `python3 scripts/check-links.py` to verify that
all relative markdown links in the repo resolve on disk.

```bash
# Quick install (symlinks — edits to the repo are immediately live)
./scripts/install.sh
```

## gmail-tools

A deliberately **draft-only** Gmail CLI at `tools/gmail-tools/bin/gmail-tools`:
search, read threads, manage labels, download attachments, and compose drafts —
but **never send**. A no-send proxy makes the send endpoint structurally
impossible to call, so it's safe to hand to an agent: the worst it can do is queue
a draft for your review. Needs [`uv`](https://docs.astral.sh/uv/) (Google
dependencies install on first run via inline script metadata) and a Google Cloud
OAuth client.

```
gmail-tools auth
gmail-tools search "is:unread in:inbox" --max 10
```

See [`tools/gmail-tools/README.md`](tools/gmail-tools/README.md) for OAuth setup and the full subcommand list.

## Hooks

Six production-tested Claude Code hooks live in [`hooks/claude/`](hooks/claude/).

| Hook | What it does |
|---|---|
| [`edit-guard`](hooks/claude/edit-guard/) | Warn/block Fable/Opus from piling up direct code edits — keeps expensive models as orchestrators. |
| [`git-no-bypass`](hooks/claude/git-no-bypass/) | Block `--no-verify` and `core.hooksPath` overrides so pre-commit/push hooks can't be skipped silently. |
| [`settings-guard`](hooks/claude/settings-guard/) | Block invalid fields (`mcpServers`, `disabledSkills`) from landing in `settings.json`. |
| [`session-context`](hooks/claude/session-context/) | Inject current branch + last 5 commits into every session automatically. |
| [`confetti`](hooks/claude/confetti/) | Fire Raycast confetti after a successful deploy. macOS + Raycast only. |
| [`proof-gate`](hooks/claude/proof-gate/) | Block "done" sign-offs while the repo has uncommitted code or unpushed commits. |

See [`hooks/claude/README.md`](hooks/claude/README.md) for the combined `settings.json` snippet.

## Credits

The `authenticity-check` and `humanizer` skills (and the `authentic-writing` wrapper)
are vendored from [aihxp](https://github.com/aihxp)'s Scriveno project
([authenticity-check](https://github.com/aihxp/authenticity-check),
[humanizer](https://github.com/aihxp/humanizer)) and used under the MIT License.
Each vendored skill keeps its original `LICENSE` (copyright preserved as required);
everything else here is MIT under [`LICENSE`](LICENSE).

## Status

Experimental. Read each skill before using it on an important repository.

`zero` is intentionally destructive — it merges everything into the default branch and pushes. Use only at a deliberate cleanup point.

The `epic-run` family (epic-run, epic-research, epic-retro) and `epic-tools` are deprecated and archived under `deprecated/` (see `deprecated/README.md`). The project is Claude-only; child issues from `epic-plan` execute via `/issue` → `/resolve-issue`.
