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
| [`epic-plan`](skills/claude/epic-plan/SKILL.md) | Scope a goal into a GitHub epic + child issues, with staged research and one-at-a-time questions. |
| [`epic-run`](skills/claude/epic-run/SKILL.md) | Execute a planned epic: fan children into isolated worktrees, verify PRs, merge. |
| [`epic-research`](skills/claude/epic-research/SKILL.md) | Pre-plan research: three parallel agents on competitors, tech peers, and GitHub code. |
| [`epic-retro`](skills/claude/epic-retro/SKILL.md) | Mine closed epics and PRs for skill/process improvements. |
| [`issue-sweep`](skills/claude/issue-sweep/SKILL.md) | Claim oldest GitHub issues, fix in parallel worktrees, land commits, and close issues. |
| [`sweep`](skills/claude/sweep/SKILL.md) | Review recent commits in batches and dispatch fix agents. Requires `code-simplifier` plugin. |
| [`tidy`](skills/claude/tidy/SKILL.md) | Anti-slop pass on changed code: delete junk, flatten ceremony, reuse existing things. |
| [`zero`](skills/claude/zero/SKILL.md) | Aggressively checkpoint, merge, clean, and push a repo. Destructive — read before use. |

### Codex

| Skill | Description |
|---|---|
| [`epic-plan`](skills/codex/epic-plan/SKILL.md) | Same 7-stage flow adapted for Codex workers. |
| [`epic-run`](skills/codex/epic-run/SKILL.md) | Codex adapter for the epic-run orchestrator. |
| [`epic-research`](skills/codex/epic-research/SKILL.md) | Parity copy of the Claude epic-research skill. |
| [`issue-sweep`](skills/codex/issue-sweep/SKILL.md) | Claim oldest GitHub issues, fix in parallel worktrees, land commits, and close issues. |
| [`quick-research`](skills/codex/quick-research/SKILL.md) | Lightweight fan-out research for practical decisions and tradeoff answers. |
| [`tidy`](skills/codex/tidy/SKILL.md) | Parity copy of the Claude tidy skill. |
| [`zero`](skills/codex/zero/SKILL.md) | Same as Claude zero. |

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
- `code-simplifier` plugin from `claude-plugins-official` — required by the `sweep` skill

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
ln -sfn "$PWD/skills/claude/issue-sweep"   ~/.claude/skills/issue-sweep
ln -sfn "$PWD/skills/claude/sweep"         ~/.claude/skills/sweep
ln -sfn "$PWD/skills/claude/tidy"          ~/.claude/skills/tidy
ln -sfn "$PWD/skills/claude/zero"          ~/.claude/skills/zero

ln -sfn "$PWD/skills/codex/epic-plan"      ~/.codex/skills/epic-plan
ln -sfn "$PWD/skills/codex/epic-run"       ~/.codex/skills/epic-run
ln -sfn "$PWD/skills/codex/epic-research"  ~/.codex/skills/epic-research
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

## Status

Experimental. Read each skill before using it on an important repository.

`zero` is intentionally destructive — it merges everything into the default branch and pushes. Use only at a deliberate cleanup point.

`sweep` requires the `code-simplifier` plugin from `claude-plugins-official`.

`epic-run`'s scheduled wakeups (`ScheduleWakeup`) work only inside Claude Code's loop/cron harness. Without it, run one tick at a time manually.
