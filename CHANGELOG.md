# Changelog

All notable changes to this project will be documented here.

## Unreleased

### Added
- `issue-do` skill (Claude): single-issue end-to-end runner — orchestrator plans, Sonnet executor implements in an isolated worktree, independent reviewer verifies; one verified PR out. Moved from a loose `~/.claude/skills/` copy into the repo and symlinked, matching the other skills.
- `tools/claude-spend/spend.py`: Claude Code per-project spend analyzer — per-session/per-skill token+cost rollup, cache-tier aware, long-context surcharge detection; stolen from hong (https://github.com/hyang0129/dot-claude)
- `epic-research` skill (Claude + Codex): pre-plan research with three parallel agent lanes
- `quick-research` skill (Codex): lightweight fan-out research for practical decisions
- `tidy` skill (Claude + Codex): anti-slop pass on changed code
- `skills/shared/` directory with canonical shared skill files

### Changed
- README and install docs now match the shipped skill set and avoid treating Markdown as an install script
- `check-install.py` now verifies every shipped Claude/Codex skill symlink, including `issue-sweep` and `quick-research`
- `issue-sweep`: simplified to PR-only automation; require `proofCommand`, prove before push/PR creation, remove auto-merge/check-upload/CI-polling paths, and make `--limit` cap all touched issues
- `epic-plan` (Claude + Codex): refactored to 7-stage flow with one-question-at-a-time grilling and inlined external research (Stages 0–7)
- `zero`: default conflict resolution changed from auto-resolve to stop+ask; add `--auto-resolve` opt-in flag; add pre-push confirmation gate; detect default branch dynamically
- Remove stale `sweep` install/check documentation after the skill was dropped from the public bundle
- `dispatch.md`: replace `Skill({skill:"tidy"})` with reference to shipped tidy skill; make `advisor()` conditional on `advisorModel` setting; remove private `scripts/tests_for.py` path
- `epic-retro`: remove `$HOME/projects/*` hardcoded path and fix jq filter
- `epic-run`: trim Hard rails and add harness contract note

### Fixed
- Add an install-contract check so shipped Claude/Codex skills and `epic-tools` cannot silently point at different checkouts
- Fix skill frontmatter so all shipped skills pass validation
- Remove stale completion-audit documentation from the current `epic-tools` surface
- `epic-tools revert` and `cleanup` now require `--yes` or interactive confirmation
- `codex/epic-run/SKILL.md`: replace `~/.claude/state` hardcoded path with runtime-neutral note
- LICENSE: change copyright from "Serg" to "skill-issue contributors"

### Removed
- Empty `grill-me/` directories (skill was never included)
- Empty `codex/epic-plan/references/` directory
- Extra `agents/README.md` from the Codex `epic-plan` skill package

## Initial public release (2026-05-22)

- `epic-plan`, `epic-run`, `epic-retro`, `zero` for Claude
- `epic-plan`, `epic-run`, `zero` for Codex
- `epic-tools` CLI
