---
name: sweep
description: Batch review-and-fix pass over recent commits. Invoke as /sweep, /sweep 24h, /sweep 50, /sweep SHA, or /sweep epic N.
---

# sweep — batch review-and-fix pass over recent commits

Collects recent commits, groups them by repo area into batches, runs `/code-review` on each batch, then dispatches Sonnet fix agents for confirmed findings.

## Invocation forms

```
/sweep              # last 30 non-merge commits
/sweep 24h          # last 24 hours
/sweep 48h          # last 48 hours
/sweep 50           # last N commits
/sweep abc1234      # from this SHA to HEAD
/sweep epic 123     # all commits belonging to GitHub epic #123
```

The preferred entry point for planned work is `/sweep epic <N>` immediately after an epic closes.

## Step 1 — Collect commits

**Time window / count / SHA range:**
```bash
git log --since="24 hours ago" --oneline --no-merges     # for time window
git log -30 --oneline --no-merges                        # for count
git log abc1234..HEAD --oneline --no-merges              # for SHA range
```

**Epic (`/sweep epic <N>`):**
1. Fetch the epic and its closed children:
   ```bash
   gh api repos/{owner}/{repo}/issues/N
   # parse child issue numbers from the task list in the body
   ```
2. For each child issue, find the merge commit of its linked PR:
   ```bash
   gh api repos/{owner}/{repo}/issues/CHILD/timeline \
     --jq '[.[] | select(.event=="cross-referenced") | .source.issue.pull_request.merged_at] | min'
   # get the merge SHA
   gh api repos/{owner}/{repo}/pulls/PR_NUMBER --jq '.merge_commit_sha'
   ```
3. Find the oldest merge commit SHA across all children — call it `<base>`.
4. Collect commits: `git log <base>^..HEAD --oneline --no-merges`

Skip commits that only touch:
- `*.md`, `docs/`, `AGENTS.md`, `CLAUDE.md`, `*.toml` (docs/config-only)
- `.claude/skills/` (skill files)
- Single-file chores with no logic change (e.g. docstring-only, import rename)

## Step 2 — Group into batches by area, then size-check each one

**2a — Initial grouping**

Get file lists per commit with `git show --stat <sha>` and group by natural area:

| Batch label | File pattern |
|---|---|
| core/domain | `src/domain/**`, `app/domain/**` |
| core/services | `src/services/**`, `app/services/**`, `lib/**` |
| commands + tools | `cli/**`, `commands/**`, `tools/**`, `scripts/**` |
| server | `server/**`, `api/**`, `db/**` |
| frontend | `web/**`, `ui/**`, `components/**` |
| tests | `tests/**`, `spec/**`, `__tests__/**` |

Merge adjacent small areas freely. State the proposed batches before proceeding so the user can redirect if the grouping looks wrong.

**2b — Measure and size-check each batch (~600L target)**

For each batch, measure the actual diff:
```bash
git diff <oldest>^..<newest> -- <files> | wc -l
```

Target is ~600L per batch. This is a **soft limit**: a single atomic commit or file that can't be meaningfully split is fine at 700–800L — just use `high` effort for the review. Only split when a batch is well over 600L and a natural seam exists. Prefer fewer, larger batches over many tiny fragments.

Split a batch when it's significantly over target — in order of preference:
1. **By sub-area** — divide into subdirectory or file-type groups
2. **By commit range** — first half vs second half of the commits in that batch

There is no minimum — a 50L batch is fine.

## Step 3 — Review batches 2 at a time via Agent

Each code review runs 3 independent finder angles, deduplicates, verifies each candidate, and returns a JSON findings array. Do NOT use `Skill({ skill: "code-review" })` here — Skill is main-thread only and can't run in parallel. Use `Agent` instead with the instructions below embedded.

Process batches **2 at a time in parallel**. Launch two `Agent` calls in a single message, wait for both to return, collect their findings, then launch the next pair.

Each Agent prompt should instruct the subagent to:
1. Run `git diff <oldest>^..<newest> -- <files>` to get the diff
2. Run 3 independent finder angles in parallel (line-by-line scan / removed-behavior audit / cross-file tracer), each surfacing up to 6 candidates with file, line, summary, failure_scenario
3. Dedup and verify each candidate (CONFIRMED / PLAUSIBLE / REFUTED) — keep CONFIRMED and PLAUSIBLE
4. Return a JSON array of findings (≤8 for medium, ≤10 for high effort), ranked most-severe first

Effort: `medium` by default (≤8 findings). Use `high` for batches over 500L or touching security-sensitive code (≤10 findings, recall-biased verification).

Use `model: "sonnet"` for all review agents.

## Step 4 — Dispatch fix agents in parallel after all reviews complete

Once all batches have been reviewed, dispatch **Sonnet** fix agents — one per batch — all in parallel. Each fix agent works in an isolated worktree to avoid index conflicts:

```
Agent({
  subagent_type: "general-purpose",
  model: "sonnet",
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

- **Review model**: Sonnet for fix agents.
- **Scope**: Only touch files changed in the commits being reviewed. Don't wander.
- **Tests must pass** before committing any fix. If tests break, surface the conflict — don't patch around it.
- **Protect**: No public signature changes, no serialized output changes, no test-intent changes unless explicitly requested.
