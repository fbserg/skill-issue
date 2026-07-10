# Contributing

## Issues

Use GitHub Issues for bug reports and feature requests.

- **Bug report**: describe what skill/command, what you expected, what happened. Include the skill name and relevant output.
- **Feature request**: describe the use case, not just the feature.

For security issues, see [SECURITY.md](SECURITY.md).

## Pull requests

1. Fork the repo and create a branch from `main`.
2. For skill changes: test the skill end-to-end in your own Claude Code setup before submitting.
3. Keep PRs focused — one skill per PR.
5. Update `CHANGELOG.md` with a summary under `## Unreleased`.

## Skill guidelines

- Treat this repository as the canonical edit point for shipped epic-plan,
  simplify-sweep, and zero skill behavior. Installed entries under `~/.claude/skills` and
  `~/.local/bin` should be symlinks back here; run
  `python3 scripts/check-install.py` after changing install wiring.
- Skills are prompt files. Keep them concise — every sentence is read by the model on every invocation.
- No hardcoded paths, account names, or repo-specific references.
- Use capability language rather than model names (`a capable reviewer model`, not a dated model ID).
- Declare external dependencies in the YAML frontmatter under `dependencies:`.
- Harness primitives (`ScheduleWakeup`, `TaskStop`, `advisor`, `code-simplifier`) must be declared as optional where they might not be available.

## Versioning

This project follows [semantic versioning](https://semver.org/). Breaking changes to skill interfaces surface a minor version bump until 1.0.
