# Release checklist

Before tagging and announcing a new release:

## Code quality
- [ ] `python3 -m py_compile tools/epic-tools/bin/epic-tools` passes
- [ ] `epic-tools --help` lists all subcommands
- [ ] `epic-tools revert --help` and `epic-tools cleanup --help` both mention `--yes`
- [ ] `grep -rE '(/Users/[a-z]+|fbserg|info@|~/projects/|\$HOME/projects/|scripts/tests_for|just push-main|claude-(haiku|sonnet|opus)-[0-9])' .` returns nothing
- [ ] `grep -rn '/simplify' skills/` returns nothing
- [ ] `grep -rE 'Skill\(\{skill:"(simplify|loop|epic-research|advisor)"' skills/` returns nothing
- [ ] `find skills -type d -empty` returns nothing

## Documentation
- [ ] README quickstart tested on a clean machine (or fresh clone)
- [ ] `docs/install.md` verify step works end-to-end
- [ ] All skill links in README point to real SKILL.md files
- [ ] LICENSE copyright name is correct

## Safety
- [ ] `zero` on a repo with a conflicting open PR stops and asks (no --auto-resolve)
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
