# Release checklist

Before tagging and announcing a new release:

## Code quality
- [ ] `python3 -m py_compile tools/epic-tools/bin/epic-tools` passes
- [ ] `epic-tools --help` lists all subcommands
- [ ] `python3 scripts/check-install.py` passes and covers every shipped Claude/Codex skill symlink plus `epic-tools`
- [ ] `epic-tools revert --help` and `epic-tools cleanup --help` both mention `--yes`
- [ ] `git grep -nE '(/Users/[a-z]+|info@|~/projects/|\$HOME/projects/|scripts/tests_for|just push-main|claude-(haiku|sonnet|opus)-[0-9])' -- . ':!CHANGELOG.md' ':!docs/publication-checklist.md' ':!.github/PULL_REQUEST_TEMPLATE.md'` returns nothing
- [ ] `grep -rn '/simplify' skills/` returns nothing
- [ ] `grep -rE 'Skill\(\{skill:"(simplify|loop|epic-research|advisor)"' skills/` returns nothing
- [ ] `find skills -type d -empty` returns nothing

## Documentation
- [ ] README quickstart tested on a clean machine (or fresh clone)
- [ ] `docs/install.md` verify step works end-to-end
- [ ] All skill links in README point to real SKILL.md files
- [ ] LICENSE copyright name is correct

## Safety
- [ ] `zero` on a repo with a conflict stops only when the conflict requires a product decision
- [ ] `sweep` frontmatter declares `code-simplifier` plugin dependency
- [ ] `epic-tools revert <N>` (without --yes) prompts for confirmation
- [ ] `epic-tools cleanup <N>` (without --yes) prompts for confirmation

## Functional
- [ ] `/epic-plan "<topic>"` goes through all 7 stages and asks one question at a time
- [ ] No skill references an unshipped sibling skill

## Repo
- [ ] CHANGELOG.md updated with release date and summary
- [ ] Git tag created: `git tag -a vX.Y.Z -m "Release X.Y.Z"`
- [ ] GitHub release created from tag
