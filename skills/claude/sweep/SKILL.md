---
name: sweep
description: Batch simplify-pass over recent commits — groups by repo area, dispatches code-simplifier review agents 2 batches at a time, then dispatches fix agents for each batch. Invoke as `/sweep` (last 30 commits) or `/sweep 24h` / `/sweep 50` / `/sweep <sha>`.
user-invocable: true
dependencies:
  - code-simplifier plugin from claude-plugins-official (required for Step 3 review)
---

# sweep — batch simplify pass on recent commits

Collects recent commits, groups them by repo area into reasonable batches, dispatches `code-simplifier` review agents 2 batches at a time, then dispatches fix agents based on findings.

**Requires:** `code-simplifier` plugin installed from `claude-plugins-official`. Without it, Step 3 review agents will fail to dispatch.

## Invocation forms

```
/sweep           # last 30 non-merge commits
/sweep 24h       # last 24 hours
/sweep 48h       # last 48 hours
/sweep 50        # last N commits
/sweep abc1234   # from this SHA to HEAD
```

## Step 1 — Collect commits

```bash
git log --since="24 hours ago" --oneline --no-merges     # for time window
git log -30 --oneline --no-merges                        # for count
git log abc1234..HEAD --oneline --no-merges              # for SHA range
```

Skip commits that only touch:
- `*.md`, `docs/`, `AGENTS.md`, `CLAUDE.md`, `*.toml` (docs/config-only)
- `.claude/skills/` (skill files)
- Single-file chores with no logic change (e.g. docstring-only, import rename)

## Step 2 — Group into batches by area

Get file lists per commit with `git show --stat <sha>` and group by natural area. Target ~150–500 lines of diff per batch. Split large areas; merge small adjacent ones.

Common area examples:

| Batch label | File pattern |
|---|---|
| core/domain | `src/domain/**`, `app/domain/**` |
| core/services | `src/services/**`, `app/services/**`, `lib/**` |
| commands + tools | `cli/**`, `commands/**`, `tools/**`, `scripts/**` |
| server | `server/**`, `api/**`, `db/**` |
| frontend | `web/**`, `ui/**`, `components/**` |
| tests | `tests/**`, `spec/**`, `__tests__/**` |

State the batches and their approximate line counts before proceeding, so the user can redirect if the grouping looks wrong.

## Step 3 — Review 2 batches at a time via code-simplifier

For each pair of batches, get the diffs first, then dispatch `code-simplifier` agents — one per batch — in parallel. Never do the analysis inline.

For each batch:

1. Run `git diff <oldest_commit_in_batch>^..<newest_commit_in_batch> -- <files>` to get the scoped diff
2. Dispatch one `Agent({subagent_type: "code-simplifier", ...})` call per batch:

```
Agent({
  subagent_type: "code-simplifier",
  prompt: "Review this diff for simplification opportunities — dead code, over-engineering, phantom abstractions, defensive theater, comment slop. Return findings as JSON: [{file, line, summary, fix}]. Diff:\n<diff>"
})
```

3. Collect all findings from the agents. Dedup near-duplicates (same defect + location → keep one). Discard findings that are clearly style-only with no observable effect.

Process pairs sequentially so findings from earlier batches don't bleed into later ones.

## Step 4 — Dispatch fix agents per batch

After each pair of review runs, dispatch fix agents — one per batch — in parallel. Each fix agent works in **an isolated worktree** to avoid index conflicts:

```
Agent({
  subagent_type: "general-purpose",
  isolation: "worktree",
  prompt: "Apply these fixes to <batch files>: <findings from Step 3>. Run tests after. Commit if tests pass."
})
```

Give each fix agent the specific findings (file:line + description), not the full review output. Fix agents should:
- Apply auto-fixable items (dead code, comment slop, single-use helper inlining)
- Skip cross-file or behavioral changes unless explicitly listed
- Run the tests appropriate for the changed files and commit if green

## Step 5 — Report

After all batches complete:
- List what was fixed and by which batch
- List anything flagged but not auto-fixed, with `file:line` references
- One-line tally: `sweep: N commits reviewed, M fixes applied, K flagged`

## Guardrails

- **Don't double-run**: If Wave 1 agents are already in the background, launch Wave 2 while they run — don't wait idle.
- **Scope**: Only touch files changed in the commits being reviewed. Don't wander.
- **Tests must pass** before committing any fix. If tests break, surface the conflict — don't patch around it.
- **Protect**: No public signature changes, no serialized output changes, no test-intent changes unless explicitly requested.
