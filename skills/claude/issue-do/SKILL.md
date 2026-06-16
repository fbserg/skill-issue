---
name: issue-do
description: "Run one GitHub issue end-to-end: orchestrator plans against the real code, a Sonnet executor (or Workflow for multi-lane issues) implements the pinned plan in an isolated worktree, an independent reviewer verifies the diff against plan + acceptance criteria. One topic in, one verified PR out."
---

# Issue Do

One topic in, one verified PR out. The orchestrator owns the thinking (plan,
design decisions, routing, review verdicts); subagents own the typing.

`/issue-do <num>` (existing issue) skips to Pre-flight. Multi-issue
(`/issue-do 42 43`) → refuse, suggest /epic-plan.

## When NOT to use this

Multi-session / multi-subsystem / deps on in-flight work → /epic-plan instead.
If the Plan step reveals this (not obvious up front), stop there and say so —
don't dispatch.

## Steps

### 1. Shape (skip if topic is unambiguous)

1–3 sharp questions: AC in one line, anything explicitly out of scope,
existing helper to reuse. Stop and wait if you asked.

### 2. File the issue (skip when called with a number)

`gh issue create` with body containing `## Scope`, `## Acceptance criteria`,
optional `## Out of scope`, `## Files likely touched`. Capture issue number.

### 3. Pre-flight

- Concurrent-run guard: `gh pr list --search "issue-<N>" --state all` → a PR
  genuinely for this issue exists → surface and stop. (If GraphQL 401s, use
  REST: `gh api 'search/issues?q=repo:<R>+is:pr+issue-<N>'`.)
- `DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name)`
- `SUFFIX=$(openssl rand -hex 4)`
- No orch worktree — main checkout is fine for a one-shot. Subagents run in
  isolated worktrees.

### 4. Plan (orchestrator-owned — the core of this skill)

The dispatch prompt must contain decisions, not questions. Build the plan
before any executor exists:

- Fan out read-only Explore/Plan subagents (`model: "sonnet"`) to read the
  files in scope, find existing helpers, and surface constraints. Keep the
  main context lean — take back conclusions, not file dumps.
- **You** make the design decisions: approach, file-by-file changes, what to
  reuse, what's out of scope, AC → concrete verification commands.
- Output: a pinned plan with sections `Decisions`, `Changes by file`,
  `Verification` (exact commands), `Out of scope`. Post it as an issue
  comment (`gh api repos/<R>/issues/<N>/comments -f body=...`) so it
  survives the session.

Routing verdict, made from the plan:

- **Single lane** (one coherent change set, sequential edits) → Step 5a.
- **2+ independent lanes** inside the issue (separable file sets, no shared
  implicit choices) → Step 5b.
- **Actually multi-session / design still open** → stop, report, suggest
  /epic-plan.

### 5a. Execute — single lane

One subagent (`model: "sonnet"`, `isolation: "worktree"`,
`mode: "bypassPermissions"`) using the child template in
`~/.claude/skills/epic-run/dispatch.md` with substitutions:

- branch: `issue-<N>-<slug>-<SUFFIX>`
- replace `epic-<N>-<child>-<slug>` references → above
- replace `(#<child>)` in PR title → `(#<N>)`
- omit WAIT_FOR (no deps in single-issue mode)
- TIDY=yes unless trivial (typo/comment/version-bump)
- **Replace the `## Issue scope` block with the pinned plan**, framed as:
  "Execute this plan verbatim. Deviations require STATUS=fail
  REASON=plan-conflict with what you found — do not improvise a different
  design."

Wait for the STATUS= line.

### 5b. Execute — multi-lane (Workflow)

Use the Workflow tool: one Sonnet agent per lane, each in its own worktree,
each receiving only its lane of the plan. A final integration agent merges
lane branches into one `issue-<N>-<slug>-<SUFFIX>` branch, runs the
verification commands from the plan, and opens the single PR per dispatch.md
steps 6–8. One issue = one PR is an invariant.

### 6. Review (separate, independent)

After STATUS=ok, dispatch a **fresh** reviewer subagent (`model: "sonnet"`,
read-only — never the executor, never its worktree):

- Input: PR number, the pinned plan, the issue AC.
- Job: adversarial diff review — does the diff implement the plan, does
  every AC hold, do the tests actually exercise the change (no
  weakened/hollow/skipped tests), any foreign files in the diff.
- Output: `VERDICT=pass` or `VERDICT=fail` with blocking findings.

On fail: send findings back to the executor (SendMessage to the same agent,
context intact) for one fix round, then re-review. Second fail → stop,
report findings, leave the PR open with a comment listing them. Never loop
more than twice.

### 7. Report

PR URL, status, reviewer verdict, plan-comment link, anything punted.
Under 100 words.

## Notes

- One-shot. Fuzzy/multi-session → /epic-plan.
- All subagents are Sonnet, explicitly (`model: "sonnet"`). The orchestrator
  never delegates design decisions or review verdicts to the executor.
- Subagents inherit bypassPermissions; honor repo CLAUDE.md.
- PR-only: orchestrator owns merge actions; executor and reviewer never
  merge, push to main, or close issues.
