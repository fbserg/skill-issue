# Install

## Prerequisites

1. **Git** — any recent version
2. **GitHub CLI** — install from <https://cli.github.com/> then authenticate:
   ```bash
   gh auth login
   ```
3. **Claude Code and/or Codex** with local skill directory support

### Optional

- **`advisorModel` setting** — set in Claude Code's `settings.json` to enable `advisor()` calls in `dispatch.md`. Without it, a subagent is dispatched for second opinions instead.

## Install

These examples use symlinks so local edits in this repo are immediately visible
to the agent runtime. Use `cp -R` instead if you prefer static copies.

This checkout is the canonical edit point for the shipped prose, issue
(front door + resolve-issue), and zero skills. Do not edit installed
copies under `~/.claude/skills/` or `~/.codex/skills/`.

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

### Codex

```bash
mkdir -p ~/.codex/skills
ln -sfn "$PWD/skills/codex/adversarial-review" ~/.codex/skills/adversarial-review
ln -sfn "$PWD/skills/codex/epic-plan"          ~/.codex/skills/epic-plan
ln -sfn "$PWD/skills/codex/issue"              ~/.codex/skills/issue
ln -sfn "$PWD/skills/codex/refactor-dupes"     ~/.codex/skills/refactor-dupes
ln -sfn "$PWD/skills/codex/resolve-issue"      ~/.codex/skills/resolve-issue
ln -sfn "$PWD/skills/codex/ww"                 ~/.codex/skills/ww
ln -sfn "$PWD/skills/codex/zero"               ~/.codex/skills/zero
```

## Verification

```bash
# Skill files are accessible and point at this checkout
ls ~/.claude/skills/epic-plan/SKILL.md
ls ~/.claude/skills/humanizer/SKILL.md
ls ~/.codex/skills/issue/SKILL.md
python3 scripts/check-install.py
```

`scripts/check-install.py` verifies that every shipped skill symlink resolves back to this checkout.

Open Claude Code or Codex in any repo and invoke one installed skill to confirm
the runtime picked up the symlinked files.

## Codex exclusions

The Codex install intentionally does not include `deep-research`,
`authentic-writing`, `authenticity-check`, `humanizer`, or the old Claude
`simplify-sweep` workflow.

## Deprecated components

The `epic-run` family (epic-run, epic-research, epic-retro), `epic-tools` CLI,
and the old Codex skills are deprecated and archived under `deprecated/`. See
`deprecated/README.md`. They are not installed by this script.

## Uninstall

```bash
# Remove Claude skill symlinks
rm ~/.claude/skills/epic-plan ~/.claude/skills/humanizer
rm ~/.claude/skills/authenticity-check ~/.claude/skills/authentic-writing
rm ~/.claude/skills/issue ~/.claude/skills/resolve-issue
rm ~/.claude/skills/zero

# Remove Codex skill symlinks
rm ~/.codex/skills/adversarial-review ~/.codex/skills/epic-plan
rm ~/.codex/skills/issue ~/.codex/skills/refactor-dupes
rm ~/.codex/skills/resolve-issue ~/.codex/skills/ww ~/.codex/skills/zero
```
