# skill-issue

Reusable agent skills and workflow helpers for Claude and Codex.

This repo is a curated public bundle, not a dump of a local skills directory.
The first cut focuses on GitHub issue/epic workflows and a few general-purpose
agent operating skills.

## Included Skills

Claude skills:

- `epic-plan` - turn a scoped idea into a GitHub epic and child issues.
- `epic-run` - run a planned epic through worker branches and verified PRs.
- `epic-retro` - mine closed epics and PRs for skill/process improvements.
- `sweep` - review recent commits in batches and dispatch focused fix agents.
- `zero` - aggressively checkpoint, merge, clean, and push a repo.

Codex skills:

- `epic-plan`
- `epic-run`
- `zero`

`issue-do` is intentionally not included in this public cut.

## Requirements

- Git
- GitHub CLI (`gh`) authenticated for repos you want the epic skills to manage
- Python 3.12+ for `epic-tools`
- Claude and/or Codex with local skill directory support

## Install

See [docs/install.md](docs/install.md) for manual copy and symlink examples.

The bundled `epic-tools` script lives at:

```text
tools/epic-tools/bin/epic-tools
```

Put that script on `PATH` before using `epic-run` or `epic-retro`.

## Status

Experimental. Read each skill before using it on an important repository.
`zero` is intentionally aggressive and should only be invoked at a deliberate
cleanup point.
