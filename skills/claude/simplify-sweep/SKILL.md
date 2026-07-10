---
name: simplify-sweep
description: "Batch-clean a range of pushed commits: headless Sonnet /simplify per area, review the edits, commit. Successor to /tidy."
---

# simplify-sweep — periodic cleanup over pushed commits

Runs Claude Code's built-in `/simplify` over a commit range using cheap headless
Sonnet sessions, one per area batch. The expensive main session only orchestrates:
pick the range, batch, launch, review the resulting edits, commit.

`$ARGUMENTS` (optional): a ref range (`abc123..HEAD`), a base ref, or area paths.
If absent, sweep everything since the last sweep commit.

## 1. Pick the range

- If `$ARGUMENTS` gives a range/ref, use it.
- Else base = last commit matching `git log -i --grep='^tidy\|^sweep' -1` (the
  `sweep(<area>):` tag from step 4 is the state store — no other bookkeeping).
- Sanity-check with `git diff --stat <base>..HEAD` and report commits/files/churn
  to the user before launching.

## 2. Batch

- Small ranges: one batch. Larger: **balance batches by churn size, not by area**
  (per-directory `git diff --shortstat`), keeping each batch's file set disjoint
  and each batch small enough that its diff is comfortably reviewable in one
  sitting — split further if a batch's review drags.
- Skip generated files entirely (repo's Do-Not-Edit table); they get regenerated,
  never hand-cleaned.

## 3. Launch headless /simplify per batch

Parallel is the default for multi-batch sweeps: one detached worktree per batch
(`git worktree add ~/projects/<repo>-worktrees/sweep-<name> HEAD --detach`),
launch each run with `run_in_background`, then per finished batch export
`git -C <worktree> diff > patch`, apply to the main checkout, review, test,
commit, and finally `git worktree remove` them. Batches are disjoint, so patches
never conflict. Sequential in the main checkout is the fallback for 1–2 batches.
**3+ background batches → arm the watchdog** (pulse files + one Monitor, the
/issue pattern) — detached lanes die silently.

```bash
claude -p --model sonnet --permission-mode acceptEdits \
  "/simplify <base>..HEAD — only review files under <area paths>. \
Also hunt LLM slop: comment slop, tombstones, fake compatibility shims, \
defensive try/catch and null-checks on non-null values, impossible-case fallbacks, \
single-use helpers, one-option bags, nested ternaries, 3+ levels of nesting. \
Do NOT change public behavior, serialized output, generated files, CLI/user-visible \
text, or test intent. When unsure, leave it alone."
```

Rules:
- **Sonnet floor — never Haiku.** Haiku punts on large diffs ("verify X" instead of
  doing the work).
- **Never two headless runs editing one checkout.** Parallel only with one worktree
  per run.
- The run leaves uncommitted edits in the working tree — that's the handoff.

## 4. Review and commit (main session)

Per batch, before the next launch:
- Read the working-tree diff. Revert over-reaches: behavior changes, dict-key
  removals, getattr→direct rewrites, anything touching serialized output or tests'
  intent. Past sweeps show Sonnet over-reaches ~2–3 times per batch — expect it.
  This review gate is the skill's entire safety story; never skip it.
- Run the repo's fast test loop (`just test` in heartwood) plus any focused tests
  for touched areas.
- Commit the batch: subject `sweep(<area>): <summary>` (heartwood: via
  `just agent-commit`). Tests must pass before commit. The tag doubles as the
  next sweep's range marker.

Finish with a one-line tally per batch (files touched, reverted over-reaches,
commit hash) and the overall range covered.
