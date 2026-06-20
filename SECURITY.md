# Security

## Reporting vulnerabilities

Report security issues via GitHub Issues. For anything sensitive, use GitHub's private vulnerability reporting (Security tab → "Report a vulnerability").

## Scope

This repository contains agent skills (prompt files) and supporting tools. The primary security concerns are:

### `zero` skill

`/zero` merges open PRs, merges local branch/worktree changes into the default
branch when they are not already merged or patch-equivalent, deletes cleaned-up
branches/worktrees, and pushes the default branch. It is intentionally
destructive. The skill always runs a read-only inventory first and stops only
for blockers that cannot be handled safely by the workflow, such as active Git
operations, failed checkpoint commits, failed PR merges, or conflicts requiring
a product decision.

**Do not run `/zero` on a repo where other agents are still working.**

### Deprecated components (epic-run / epic-tools)

The `epic-run` orchestrator, `epic-tools` CLI, and related subcommands (`revert`, `cleanup`, dispatch) are deprecated and archived under `deprecated/` — they are not installed. Their security surface no longer applies to active installs.

## Known limitations

- Skills are prompt files read by LLMs. Adversarial content in GitHub issues, PR bodies, or file content could potentially influence model behavior. Keep this in mind when running `/resolve-issue` or `/epic-plan` on repos with untrusted content in issues.
