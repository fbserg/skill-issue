# Install

These examples use symlinks so local edits in this repo are immediately visible
to the agent runtime. Use `cp -R` instead if you prefer static copies.

## Claude

```bash
mkdir -p ~/.claude/skills
ln -sfn "$PWD/skills/claude/epic-plan" ~/.claude/skills/epic-plan
ln -sfn "$PWD/skills/claude/epic-run" ~/.claude/skills/epic-run
ln -sfn "$PWD/skills/claude/epic-retro" ~/.claude/skills/epic-retro
ln -sfn "$PWD/skills/claude/grill-me" ~/.claude/skills/grill-me
ln -sfn "$PWD/skills/claude/sweep" ~/.claude/skills/sweep
ln -sfn "$PWD/skills/claude/zero" ~/.claude/skills/zero
```

## Codex

```bash
mkdir -p ~/.codex/skills
ln -sfn "$PWD/skills/codex/epic-plan" ~/.codex/skills/epic-plan
ln -sfn "$PWD/skills/codex/epic-run" ~/.codex/skills/epic-run
ln -sfn "$PWD/skills/codex/grill-me" ~/.codex/skills/grill-me
ln -sfn "$PWD/skills/codex/zero" ~/.codex/skills/zero
```

## epic-tools

```bash
mkdir -p ~/.local/bin
ln -sfn "$PWD/tools/epic-tools/bin/epic-tools" ~/.local/bin/epic-tools
```

Confirm `~/.local/bin` is on `PATH`, then run:

```bash
epic-tools --help
```
