# Install

## Prerequisites

1. **Git** — any recent version
2. **GitHub CLI** — install from <https://cli.github.com/> then authenticate:
   ```bash
   gh auth login
   ```
3. **Claude Code** with local skill directory support

### Optional

- **`advisorModel` setting** — set in Claude Code's `settings.json` to enable `advisor()` calls in `dispatch.md`. Without it, a subagent is dispatched for second opinions instead.

## Install

These examples use symlinks so local edits in this repo are immediately visible
to the agent runtime. Use `cp -R` instead if you prefer static copies.

This checkout is the canonical edit point for the shipped prose, issue
(front door + resolve-issue), and zero skills. Do not edit installed
copies under `~/.claude/skills/`.

### Claude

```bash
mkdir -p ~/.claude/skills
ln -sfn "$PWD/skills/claude/epic-plan"     ~/.claude/skills/epic-plan
ln -sfn "$PWD/skills/claude/humanizer"     ~/.claude/skills/humanizer
ln -sfn "$PWD/skills/claude/authenticity-check" ~/.claude/skills/authenticity-check
ln -sfn "$PWD/skills/claude/authentic-writing"  ~/.claude/skills/authentic-writing
ln -sfn "$PWD/skills/claude/issue"         ~/.claude/skills/issue
ln -sfn "$PWD/skills/claude/resolve-issue" ~/.claude/skills/resolve-issue
ln -sfn "$PWD/skills/claude/zero"          ~/.claude/skills/zero
```

## Verification

```bash
# Skill files are accessible and point at this checkout
ls ~/.claude/skills/epic-plan/SKILL.md
ls ~/.claude/skills/humanizer/SKILL.md
python3 scripts/check-install.py
```

`scripts/check-install.py` verifies that every shipped skill symlink resolves back to this checkout.

Open Claude Code in any repo and type `/epic-plan "hello world"` — you should see the research phase kick off immediately.

## Deprecated components

The `epic-run` family (epic-run, epic-research, epic-retro), `epic-tools` CLI,
and all Codex skills are deprecated and archived under `deprecated/`. See
`deprecated/README.md`. They are not installed by this script and do not appear
in `check-install.py`.

## Uninstall

```bash
# Remove Claude skill symlinks
rm ~/.claude/skills/epic-plan ~/.claude/skills/humanizer
rm ~/.claude/skills/authenticity-check ~/.claude/skills/authentic-writing
rm ~/.claude/skills/issue ~/.claude/skills/resolve-issue
rm ~/.claude/skills/zero
```
