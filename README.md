# skill-issue

Reusable agent skills and workflow helpers for Claude and Codex.

A curated public bundle focused on GitHub epic/issue workflows plus practical
agent operating skills.

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
# Claude asks questions, researches competitors, drafts a GitHub epic.
# When done, run it:
/epic-run <epic-number>
```

## Skills

### Claude

| Skill | Description |
|---|---|
| [`authentic-writing`](skills/claude/authentic-writing/SKILL.md) | Route prose audits and de-slop rewrites through authenticity-check and humanizer without detector-gaming loops. |
| [`authenticity-check`](skills/claude/authenticity-check/SKILL.md) | Upstream aihxp skill: score human authenticity and flag AI-sounding spans without rewriting. |
| [`epic-plan`](skills/claude/epic-plan/SKILL.md) | Scope a goal into a GitHub epic + child issues, with staged research and one-at-a-time questions. |
| [`epic-run`](skills/claude/epic-run/SKILL.md) | Execute a planned epic: fan children into isolated worktrees, verify PRs, merge. |
| [`epic-research`](skills/claude/epic-research/SKILL.md) | Pre-plan research: three parallel agents on competitors, tech peers, and GitHub code. |
| [`epic-retro`](skills/claude/epic-retro/SKILL.md) | Mine closed epics and PRs for skill/process improvements. |
| [`humanizer`](skills/claude/humanizer/SKILL.md) | Upstream aihxp skill: rewrite AI-sounding prose into natural human prose while preserving facts. |
| [`issue-sweep`](skills/claude/issue-sweep/SKILL.md) | Claim oldest GitHub issues, fix in parallel worktrees, prove locally, and open PRs. Never merges. |
| [`tidy`](skills/claude/tidy/SKILL.md) | Anti-slop pass on changed code: delete junk, flatten ceremony, reuse existing things. |
| [`zero`](skills/claude/zero/SKILL.md) | Aggressively checkpoint, merge, clean, and push a repo. Destructive — read before use. |

### Codex

| Skill | Description |
|---|---|
| [`authentic-writing`](skills/codex/authentic-writing/SKILL.md) | Route prose audits and de-slop rewrites through authenticity-check and humanizer without detector-gaming loops. |
| [`authenticity-check`](skills/codex/authenticity-check/SKILL.md) | Upstream aihxp skill: score human authenticity and flag AI-sounding spans without rewriting. |
| [`epic-plan`](skills/codex/epic-plan/SKILL.md) | Same 7-stage flow adapted for Codex workers. |
| [`epic-run`](skills/codex/epic-run/SKILL.md) | Codex adapter for the epic-run orchestrator. |
| [`epic-research`](skills/codex/epic-research/SKILL.md) | Parity copy of the Claude epic-research skill. |
| [`humanizer`](skills/codex/humanizer/SKILL.md) | Upstream aihxp skill: rewrite AI-sounding prose into natural human prose while preserving facts. |
| [`issue-sweep`](skills/codex/issue-sweep/SKILL.md) | Claim oldest GitHub issues, fix in parallel worktrees, prove locally, and open PRs. Never merges. |
| [`quick-research`](skills/codex/quick-research/SKILL.md) | Lightweight fan-out research for practical decisions and tradeoff answers. |
| [`tidy`](skills/codex/tidy/SKILL.md) | Parity copy of the Claude tidy skill. |
| [`zero`](skills/codex/zero/SKILL.md) | Shared destructive cleanup skill, same source as Claude zero. |

## Pairing skills

```
/epic-research "should we adopt X"   →  answers "where do we stand"
/epic-plan "build X"                 →  turns a direction into child issues
/epic-run <N>                        →  executes the plan
/epic-retro                          →  mines closed epics for improvements
```

## Requirements

- Git
- GitHub CLI (`gh`) authenticated: `gh auth login`
- Python 3.10+ for `epic-tools`
- Claude Code and/or Codex with local skill directory support

### Optional

- `advisorModel` set in Claude Code settings — enables `advisor()` calls in `dispatch.md`

## Install

See [docs/install.md](docs/install.md) for full instructions.

`skill-issue` is the canonical source for these skills and `epic-tools`. Edit
the files in this checkout, then run `python3 scripts/check-install.py` to catch
any local install that points at an older copy.

```bash
# Quick install (symlinks — edits to the repo are immediately live)
mkdir -p ~/.claude/skills ~/.codex/skills ~/.local/bin

ln -sfn "$PWD/skills/claude/epic-plan"     ~/.claude/skills/epic-plan
ln -sfn "$PWD/skills/claude/epic-run"      ~/.claude/skills/epic-run
ln -sfn "$PWD/skills/claude/epic-research" ~/.claude/skills/epic-research
ln -sfn "$PWD/skills/claude/epic-retro"    ~/.claude/skills/epic-retro
ln -sfn "$PWD/skills/claude/humanizer"     ~/.claude/skills/humanizer
ln -sfn "$PWD/skills/claude/authenticity-check" ~/.claude/skills/authenticity-check
ln -sfn "$PWD/skills/claude/authentic-writing"  ~/.claude/skills/authentic-writing
ln -sfn "$PWD/skills/claude/issue-sweep"   ~/.claude/skills/issue-sweep
ln -sfn "$PWD/skills/claude/tidy"          ~/.claude/skills/tidy
ln -sfn "$PWD/skills/claude/zero"          ~/.claude/skills/zero

ln -sfn "$PWD/skills/codex/epic-plan"      ~/.codex/skills/epic-plan
ln -sfn "$PWD/skills/codex/epic-run"       ~/.codex/skills/epic-run
ln -sfn "$PWD/skills/codex/epic-research"  ~/.codex/skills/epic-research
ln -sfn "$PWD/skills/codex/humanizer"      ~/.codex/skills/humanizer
ln -sfn "$PWD/skills/codex/authenticity-check" ~/.codex/skills/authenticity-check
ln -sfn "$PWD/skills/codex/authentic-writing"  ~/.codex/skills/authentic-writing
ln -sfn "$PWD/skills/codex/issue-sweep"    ~/.codex/skills/issue-sweep
ln -sfn "$PWD/skills/codex/quick-research" ~/.codex/skills/quick-research
ln -sfn "$PWD/skills/codex/tidy"           ~/.codex/skills/tidy
ln -sfn "$PWD/skills/codex/zero"           ~/.codex/skills/zero

ln -sfn "$PWD/tools/epic-tools/bin/epic-tools" ~/.local/bin/epic-tools
```

Confirm `~/.local/bin` is on `PATH`, then verify:

```bash
epic-tools --help
```

## epic-tools

The `epic-tools` CLI lives at `tools/epic-tools/bin/epic-tools`. It's used by `epic-run` and `epic-retro` for GitHub operations and PR verification.

```
epic-tools --help
python3 scripts/check-install.py
```

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

## Status

Experimental. Read each skill before using it on an important repository.

`zero` is intentionally destructive — it merges everything into the default branch and pushes. Use only at a deliberate cleanup point.

`epic-run`'s scheduled wakeups (`ScheduleWakeup`) work only inside Claude Code's loop/cron harness. Without it, run one tick at a time manually.
