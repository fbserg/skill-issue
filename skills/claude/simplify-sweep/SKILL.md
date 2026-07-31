---
name: simplify-sweep
description: "Batch-clean a range of pushed commits: headless Sonnet /simplify per area, review the edits, commit. Successor to /tidy."
---

# simplify-sweep — periodic cleanup over pushed commits

Runs `/simplify` over a commit range via cheap headless Sonnet sessions, one
per area batch; the main session only orchestrates. `$ARGUMENTS` (optional): a
ref range, base ref, or area paths — else sweep everything since the last
commit matching `git log -i --grep='^tidy\|^sweep' -1` (the `sweep(<area>):`
tag from step 3 is the only state store). Report commits/files/churn before
launching.

## 1. Batch

Balance batches by churn size (`git diff --shortstat` per dir), file sets
disjoint, each batch's diff reviewable in one sitting. Skip generated files
entirely (repo's Do-Not-Edit table).

## 2. Launch headless /simplify per batch

Parallel default: one detached worktree per batch
(`git worktree add ~/projects/<repo>-worktrees/sweep-<name> HEAD --detach`),
`run_in_background`; per finished batch export the worktree diff as a patch,
apply to the main checkout, review, test, commit, remove the worktree.
Sequential in the main checkout is fine for 1–2 batches. **3+ background
batches → watchdog per `docs/lane-watchdog.md`.**

```bash
claude -p --model sonnet --permission-mode acceptEdits \
  "/simplify <base>..HEAD — only review files under <area paths>. \
Also hunt LLM slop: comment slop, tombstones, fake compatibility shims, \
defensive try/catch and null-checks on non-null values, impossible-case fallbacks, \
single-use helpers, one-option bags, nested ternaries, 3+ levels of nesting. \
Do NOT change public behavior, serialized output, generated files, CLI/user-visible \
text, or test intent. When unsure, leave it alone."
```

**Sonnet floor — never Haiku** (punts on large diffs). **Never two headless
runs editing one checkout.** The run leaves uncommitted edits — that's the
handoff.

## 3. Review and commit (main session)

Per batch: read the diff and revert over-reaches — behavior changes, dict-key
removals, anything touching serialized output or test intent (expect ~2–3 per
batch; this gate is the skill's entire safety story, never skip it). Run the
repo's fast test loop; tests pass before commit. Subject `sweep(<area>):
<summary>` — the tag doubles as the next sweep's range marker. Finish with a
one-line tally per batch (files, reverted over-reaches, hash) and the range
covered.
