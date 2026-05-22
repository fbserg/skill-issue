# Contributing

## Issues

Use GitHub Issues for bug reports and feature requests.

- **Bug report**: describe what skill/command, what you expected, what happened. Include the skill name and relevant output.
- **Feature request**: describe the use case, not just the feature.

For security issues, see [SECURITY.md](SECURITY.md).

## Pull requests

1. Fork the repo and create a branch from `main`.
2. For skill changes: test the skill end-to-end in your own Claude Code or Codex setup before submitting.
3. For `epic-tools` changes: `python3 -m py_compile tools/epic-tools/bin/epic-tools` must pass.
4. Keep PRs focused — one skill or one tool per PR.
5. Update `CHANGELOG.md` with a summary under `## Unreleased`.

## Skill guidelines

- Skills are prompt files. Keep them concise — every sentence is read by the model on every invocation.
- No hardcoded paths, account names, or repo-specific references.
- Use capability language rather than model names (`a capable reviewer model` not `claude-sonnet-4-6`).
- Declare external dependencies in the YAML frontmatter under `dependencies:`.
- Harness primitives (`ScheduleWakeup`, `TaskStop`, `advisor`, `code-simplifier`) must be declared as optional where they might not be available.

## epic-tools guidelines

- Python 3.10+ stdlib only (no third-party deps).
- All destructive subcommands must have a `--yes` flag and a y/N prompt.
- New subcommands need a usage example in the argparse epilogue.

## Versioning

This project follows [semantic versioning](https://semver.org/). Breaking changes to skill interfaces or `epic-tools` CLI surface a minor version bump until 1.0.
