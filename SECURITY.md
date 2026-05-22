# Security

## Reporting vulnerabilities

Report security issues via GitHub Issues. For anything sensitive, use GitHub's private vulnerability reporting (Security tab → "Report a vulnerability").

## Scope

This repository contains agent skills (prompt files) and a CLI tool (`epic-tools`). The primary security concerns are:

### `zero` skill

`/zero` merges all open PRs, merges all local branches into the default branch, and pushes. It is intentionally destructive. It requires an explicit `--auto-resolve` flag to auto-resolve merge conflicts; by default it stops and asks.

**Do not run `/zero` on a repo where other agents are still working.**

### `epic-tools revert` and `cleanup`

Both subcommands are irreversible (revert opens a revert PR over all merged epic children; cleanup drops worktrees and deletes branches). Both now require `--yes` or an interactive y/N confirmation.

### `epic-run` / dispatch

Child agents run with worktree isolation and bypass permissions for the scope of their child issue. They are scoped to `epic-<N>-<child>-*` branches and must not push to main, deploy, or restart daemons.

### `epic-tools` shell-out surface

`epic-tools` shells out to `gh` and `git`. It does not eval user-provided strings as shell commands. Issue numbers and SHA values are validated before use.

## Known limitations

- Skills are prompt files read by LLMs. Adversarial content in GitHub issues, PR bodies, or file content could potentially influence model behavior. Do not run `epic-run` on repos with untrusted content in issues.
- `epic-tools` follows GitHub API pagination to 100 results per call by default. Very large epics (>100 PRs) may see truncated results.
