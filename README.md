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
# In Claude Code or Codex, invoke:
/epic-plan "add dark mode to the settings page"
# The agent scopes and drafts a GitHub epic with child issues.
# Execute children via:
/issue <child-number>
```

## Skills

### Codex (`skills/codex/`)

| Skill | Description |
|---|---|
| [`adversarial-review`](skills/codex/adversarial-review/SKILL.md) | Read-only red-team pass over a plan or diff before risky work lands. |
| [`blitz`](skills/codex/blitz/SKILL.md) | Fast execution of ad-hoc lanes in parallel worktrees with adversarial review. |
| [`epic-plan`](skills/codex/epic-plan/SKILL.md) | Scope broad work into a tracker issue and right-sized child issues; creates nothing until GO. |
| [`issue`](skills/codex/issue/SKILL.md) | Front door for GitHub issue work; scopes ideas or routes issue numbers to resolve-issue. |
| [`refactor-dupes`](skills/codex/refactor-dupes/SKILL.md) | Tool-first duplicate detection, architecture brief, approved worktree refactor, draft PR. |
| [`resolve-issue`](skills/codex/resolve-issue/SKILL.md) | One issue to review-ready PR in an isolated worktree; never merges. |
| [`ww`](skills/codex/ww/SKILL.md) | Isolated worktree workflow; plan first, PR by default, main untouched. |
| [`zero`](skills/shared/zero/SKILL.md) | Shared destructive cleanup workflow with proof-before-delete classification. |

### Claude (`skills/claude/`)

| Skill | Description |
|---|---|
| [`adversary`](skills/claude/adversary/SKILL.md) | Cross-model red-team: sends a plan or diff to Codex (GPT) for an adversarial pass before committing. |
| [`blitz`](skills/claude/blitz/SKILL.md) | Lightweight executor for ad-hoc lanes: parallel worktrees + adversarial review, no pipeline ceremony. The fast alternative to /issue batch. |
| [`deep-research`](skills/claude/deep-research/SKILL.md) | Opus-planned multi-source research with disconfirmation lens, GRADE evidence tiers, and a saturation loop. |
| [`epic-plan`](skills/claude/epic-plan/SKILL.md) | Research-heavy planner: wide parallel research, multi-lens review of the decomposition, child issues that execute via /issue → /resolve-issue; re-enters from GitHub state. |
| [`issue`](skills/claude/issue/SKILL.md) | Thin front door: scope a rough idea, or hand one issue (or a batch, ≤4 concurrent) to /resolve-issue, which self-scales by tier. Never writes code, never merges. |
| [`resolve-issue`](skills/claude/resolve-issue/SKILL.md) | Self-scaling pipeline for one issue: light path for tier-1, full assess→plan→implement→test→review for tier 2-3, bounces a true epic to /epic-plan. The executor behind /issue. Never merges. |
| [`simplify-sweep`](skills/claude/simplify-sweep/SKILL.md) | Batch-clean a pushed commit range via headless Sonnet /simplify per area; orchestrator reviews and commits. |

Claude skills remain available for Claude Code. Codex uses the separate
`skills/codex/` tree so tool names and workflow assumptions stay runtime-native.

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
| Multiple issues | `/issue 42 43 44` — fans out ≤4 concurrent `/resolve-issue` lanes |
| Ad-hoc lanes, nothing filed | `/blitz` — parallel worktrees, adversarial review, no pipeline |
| A true epic (multi-session, multiple deliverables) | `/epic-plan <topic>` → `/issue <child-number>` |

Claiming (assign yourself), plan-comment-before-branch, and PR-only delivery are built in — you never merge your own PR.

## Requirements

- Git
- GitHub CLI (`gh`) authenticated: `gh auth login`
- [`uv`](https://docs.astral.sh/uv/) for `gmail-tools` (auto-installs its Google deps on first run)
- Claude Code with local skill directory support

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

## Other tools

`tools/claude-spend/spend.py` (per-project Claude Code spend analyzer) isn't
symlinked by `install.sh` — run it in place: `python3 tools/claude-spend/spend.py`.
See [INDEX.md](INDEX.md) for the full tools/scripts table.

## Hooks

Nine Claude Code hooks — the live set the author actually runs — mirrored in
[`hooks/claude/`](hooks/claude/).

| Hook | What it does |
|---|---|
| [`expensive_model_edit_guard.py`](hooks/claude/expensive_model_edit_guard.py) | Warn/block Fable/Opus from piling up direct code edits — keeps expensive models as orchestrators. |
| [`edit_guard_backstop.py`](hooks/claude/edit_guard_backstop.py) | Stop-time backstop that catches the edit guard silently failing to fire. |
| [`effort_spawn_guard.py`](hooks/claude/effort_spawn_guard.py) | Block `Agent`/`Workflow` spawns that would inherit the main thread's effort level instead of naming a custom agent type. |
| [`guard-settings-json.sh`](hooks/claude/guard-settings-json.sh) | Block invalid fields (`mcpServers`, `disabledSkills`) from landing in `settings.json`; protect `~/.claude/CLAUDE.md` from edits. |
| [`pretool-bash.sh`](hooks/claude/pretool-bash.sh) | Block destructive Bash commands, filter verbose test output, apply RTK's token-saving rewrite, gate `git push` on a clean build. |
| [`sessionstart-context.sh`](hooks/claude/sessionstart-context.sh) | Inject current branch + last 5 commits into every session automatically. |
| [`notify-done.sh`](hooks/claude/notify-done.sh) | Ring the terminal bell when Claude's last message is actually a question. |
| [`confetti-gate.sh`](hooks/claude/confetti-gate.sh) | Fire Raycast confetti after a successful deploy. macOS + Raycast only. |
| [`quality/`](hooks/claude/quality/) | Format-on-write + unresolved-failure Stop gate, four cooperating hooks sharing one state file. |

See [`hooks/claude/README.md`](hooks/claude/README.md) for per-hook `settings.json` snippets and what was deliberately left out.

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

The `epic-run` family (epic-run, epic-research, epic-retro), `epic-tools`, and
the old Codex skills are deprecated and archived under `deprecated/` (see
`deprecated/README.md`). Current Codex skills live under `skills/codex/`.
