---
name: ww
description: Do this task via the worktree workflow — isolated worktree, plan-first, PR by default. Use when the user invokes /ww.
user-invocable: true
---

Execute the requested change via the worktree workflow: spin up an isolated worktree (`claude --worktree <name>`, or dispatch a Sonnet `worker` agent with `isolation: 'worktree'`), do the work there behind an agreed plan, and open a PR by default. Main stays clean. Never edit the main checkout for this.

Boundary: this is one lane, plan-first, with an approval gate. Multiple ad-hoc lanes run fast → /blitz; filed issues → /issue.
