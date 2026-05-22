# Install

## Prerequisites

1. **Git** — any recent version
2. **GitHub CLI** — install from <https://cli.github.com/> then authenticate:
   ```bash
   gh auth login
   ```
3. **Python 3.10+** — for `epic-tools`
4. **Claude Code** and/or **Codex** with local skill directory support

### Optional

- **`advisorModel` setting** — set in Claude Code's `settings.json` to enable `advisor()` calls in `dispatch.md`. Without it, a subagent is dispatched for second opinions instead.
- **`code-simplifier` plugin** — required by the `sweep` skill. Install from the `claude-plugins-official` marketplace in Claude Code.

## Install

These examples use symlinks so local edits in this repo are immediately visible
to the agent runtime. Use `cp -R` instead if you prefer static copies.

### Claude

```bash
mkdir -p ~/.claude/skills
ln -sfn "$PWD/skills/claude/epic-plan"     ~/.claude/skills/epic-plan
ln -sfn "$PWD/skills/claude/epic-run"      ~/.claude/skills/epic-run
ln -sfn "$PWD/skills/claude/epic-research" ~/.claude/skills/epic-research
ln -sfn "$PWD/skills/claude/epic-retro"    ~/.claude/skills/epic-retro
ln -sfn "$PWD/skills/claude/sweep"         ~/.claude/skills/sweep
ln -sfn "$PWD/skills/claude/tidy"          ~/.claude/skills/tidy
ln -sfn "$PWD/skills/claude/zero"          ~/.claude/skills/zero
```

### Codex

```bash
mkdir -p ~/.codex/skills
ln -sfn "$PWD/skills/codex/epic-plan"     ~/.codex/skills/epic-plan
ln -sfn "$PWD/skills/codex/epic-run"      ~/.codex/skills/epic-run
ln -sfn "$PWD/skills/codex/epic-research" ~/.codex/skills/epic-research
ln -sfn "$PWD/skills/codex/tidy"          ~/.codex/skills/tidy
ln -sfn "$PWD/skills/codex/zero"          ~/.codex/skills/zero
```

### epic-tools

```bash
mkdir -p ~/.local/bin
ln -sfn "$PWD/tools/epic-tools/bin/epic-tools" ~/.local/bin/epic-tools
```

Confirm `~/.local/bin` is on `PATH`, then verify the install:

```bash
epic-tools --help
```

## Verification

```bash
# epic-tools responds
epic-tools --help

# Skill files are accessible
ls ~/.claude/skills/epic-plan/SKILL.md
ls ~/.codex/skills/epic-run/SKILL.md
```

Open Claude Code in any repo and type `/epic-plan "hello world"` — you should see Stage 0 (topic capture) immediately and Stage 1 (first scoping question) after.

## Skill and Codex parity

Claude and Codex both have: `epic-plan`, `epic-run`, `epic-research`, `tidy`, `zero`.

Claude-only: `epic-retro`, `sweep` (requires `code-simplifier` plugin).

## Uninstall

```bash
# Remove Claude skill symlinks
rm ~/.claude/skills/epic-plan ~/.claude/skills/epic-run ~/.claude/skills/epic-research
rm ~/.claude/skills/epic-retro ~/.claude/skills/sweep ~/.claude/skills/tidy ~/.claude/skills/zero

# Remove Codex skill symlinks
rm ~/.codex/skills/epic-plan ~/.codex/skills/epic-run ~/.codex/skills/epic-research
rm ~/.codex/skills/tidy ~/.codex/skills/zero

# Remove epic-tools
rm ~/.local/bin/epic-tools
```
