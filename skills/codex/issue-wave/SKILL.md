---
name: issue-wave
description: Batch GitHub issue execution methodology for Codex. Use when the user asks to run several issues, send out agents, coordinate worker PRs, review them, resend fixes, merge completed work, push main, or clean up after a multi-agent issue wave. Orchestrates resolve-issue, adversarial-review, repository merge gates, and zero cleanup.
---

# Issue Wave

Run a small batch of GitHub issues through isolated worker lanes, review each result with evidence, either resend for bounded fixes or merge, then clean up. This skill owns integration; `resolve-issue` still owns one issue to one review-ready PR and never merges.

## Retrospective Baseline

The 2026-06-24 Heartwood issue wave worked because each issue had an isolated worktree, real tests, adversarial review, and a final zero cleanup. It was inefficient because review was open-ended, findings were discussed before being locally verified, and some lanes bounced between reviewer and worker without a crisp acceptance ledger.

The improved method is:

```
dispatch -> worker PR -> integrator verification -> adversarial review
         -> accept | one focused resend | stop as blocked
         -> integrate -> push/deploy -> zero
```

## Fit Check

Use this skill when all are true:

- The user explicitly wants a batch, wave, or agent fan-out.
- Issues are independent enough for separate branches/worktrees.
- The integrator can merge and push after checks pass.
- The batch can finish in one working session, normally two to four issues.

Do not use it for a vague epic, a single issue, or work that needs one shared design surface. Route epics to `epic-plan`; route one issue to `resolve-issue`.

## Dispatch

1. Read each issue title, body, comments, labels, and existing PRs.
2. Reject or defer issues that share the same files, schema migration, output contract, or product decision.
3. Assign each accepted issue one worker lane running `resolve-issue`.
4. Give each worker a narrow ownership brief:
   - exact issue number
   - branch/worktree isolation requirement
   - expected acceptance criteria
   - required tests/checks from repo docs
   - instruction to open a draft PR early and never merge
5. Keep a visible wave ledger with one row per issue:
   - issue
   - branch/worktree
   - PR
   - status: dispatched, needs-fix, ready, merged, blocked, skipped
   - verification evidence

Cap active implementation lanes at four. Prefer two when issues touch adjacent systems or the repo has slow gates.

## Worker Completion Gate

Treat a worker PR as ready for review only when it has:

- a linked issue and branch
- a concise PR body
- tests/checks listed with pass/fail result
- pushed commits
- no uncommitted work in the worker worktree

If any of these are missing, resend to the worker once with a precise checklist instead of reviewing the diff.

## Integrator Verification

Before adversarial review, the integrator must locally verify the change enough to avoid wasting reviewer time:

1. Fetch the branch and inspect the diff against main.
2. Check that the implementation maps to the issue acceptance criteria.
3. Run the narrow tests or repo gate the worker claimed, unless already proven by trusted required checks.
4. Search for output parsers, generated files, dynamic references, and callers when the diff changes contracts or deletes code.
5. Record the evidence in the wave ledger.

Do not ask for adversarial review while the integrator still has obvious unanswered questions.

## Review Lanes

Run adversarial review after integrator verification for risky PRs: migrations, deletions, output structure, shared helpers, cross-app behavior, or more than a narrow local patch.

Give the reviewer a concrete artifact and lens:

- Correctness: does the behavior match the issue and callers?
- Regression surface: which existing flows could break?
- Verification: what is not covered by the tests that ran?
- Simplicity: is there speculative code or dead flexibility?

Every finding must have:

- evidence from the repo or diff
- expected failure mode
- required action
- severity: blocker, should-fix, advisory

Discard generic findings. A review that cannot point to code, tests, docs, or runtime state is not actionable.

## Resend or Merge

For each reviewed PR, choose exactly one path:

- Merge: all blockers fixed, checks pass, acceptance criteria verified.
- Resend: one focused fix packet with exact findings and expected validation.
- Block: product decision, merge conflict, red required gate, or uncertain data loss risk.
- Skip: user deprioritized the issue; preserve branch/PR state and stop.

Limit review bounce:

- First resend: worker fixes confirmed findings.
- Second failure on the same class: integrator re-reads the failing artifact and either patches directly or blocks with evidence.
- Do not run another open-ended adversarial pass after the final fix. Run a targeted check for the previously confirmed finding.

This prevents review ping-pong while keeping the useful skepticism.

## Integration

Merge one PR at a time through the repository-approved path. For Heartwood-style repos, prefer the repo's integration command, then run the documented push/deploy command from main.

For each merge:

1. Confirm main is clean.
2. Integrate the branch with the repo's merge gate.
3. Run required post-merge checks.
4. Push/deploy main if repo policy requires it.
5. Verify runtime health for runtime changes.
6. Close or update the issue only when the merge path did not do it automatically.

If a merge fails, stop the merge operation, preserve the branch, and mark the lane blocked or needs-fix. Do not move to the next merge while the repo is mid-merge or has lock/index state.

## Cleanup

After the wave, invoke `zero` when the user asked for cleanup or when the repo policy expects it.

Cleanup must:

- checkpoint dirty work before removing anything
- remove only merged or patch-equivalent branches
- preserve skipped or blocked work by pushed branch or open PR
- remove stale worktrees only after branch work is merged, empty, or preserved
- push main at the end

## Final Report

Report compactly:

- issues completed, skipped, or blocked
- PRs merged and PRs left open
- commits made by the integrator
- tests/checks and runtime proof
- branches/worktrees removed
- preserved branches with why they remain
- one methodology note if the wave exposed a reusable failure pattern
