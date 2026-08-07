# Resolve-issue full pipeline (--full)

The phased multi-agent path behind `/resolve-issue <N> --full`. Runs only on
a user-typed flag — the skill never self-escalates into it (DECISIONS.md
2026-08-07). The skill's hard rules (never merge, worktree-or-abort, gates
verbatim, untrusted issue text) and tripwires (amendment re-poll, negative
control, mergeable-before-ready) all still bind; this doc adds the pipeline
structure on top and doesn't restate them.

You are the orchestrator; each phase is a fresh-context subagent and phases
communicate only through handoff blocks. The structure keeps roles honest —
it does not replace your judgment. Deviate when the situation clearly calls
for it and say so; never deviate on the hard rules.

## Pipeline-specific rules

- **Orchestrator holds no code context.** You never read repo files or run
  git/test commands yourself. Handoffs carry prose and file names — never
  source lines or diffs.
- **Role separation:** the implementer writes no tests; the test writer
  changes no production code; the final review pass triggers no fixes.
- **Model tiering — Sonnet researches, Opus judges, Codex builds.** Every
  spawn names `agentType` explicitly (a bare `model:` inherits the session's
  often-low effort): `worker` for assess/test/finalize, `opus-worker` for
  plan and review, the Codex builder lane (`docs/codex-builder-lane.md`) for
  implement/fix. The test writer stays Claude regardless of builder: its
  independence is what makes a Codex builder safe (Codex's green self-reports
  are unreliable; measured).

## Handoffs

Every phase subagent ends its reply with one block:

```
HANDOFF
KEY: value
END_HANDOFF
```

Missing or malformed → re-ask once for the block alone, then treat the phase
as failed. Scratch files live under `/tmp/resolve-issue-<N>/`.

## Assess

Read-only worker: fetch the issue and comments, detect the base branch, probe
blast radius (grep candidate files' importers — a widely imported file is a
shared-interface hit). Check the shortcuts first: already fixed on base →
verify and close with evidence, no PR; an open PR already fixes it → converge
on that PR. Substantive open questions → surface them to the user before
implementing; an answered question is cheaper than a rejected PR. Multiple
separable deliverables → stop, point at `/epic-plan <N>`.

Handoff: `RATIONALE`, `OPEN_QUESTIONS`, `IMPACT_SET`, `SHARED_INTERFACE_HIT`,
`BASE_BRANCH`, `ACCEPTANCE_CRITERIA` (numbered).

## Plan

Read-only planner (`opus-worker`): files and functions to change, the
approach, and a mapping from each acceptance criterion to the change that
satisfies it — a plan that can't say which change satisfies which criterion
isn't done. If the solution space is genuinely contested (substantive open
questions or a shared-interface hit that user input didn't settle), spawn 2–3
planners with different stances concurrently and synthesize once.
Sanity-check the plan against the assessment yourself; a weak plan gets one
revision round with specific objections.

**Post the plan as an issue comment before any branch exists.** It is the
scope-confirm point where a human can redirect before code is written, the
durable record `--resume` reads back, and the claim that closes the race
window between concurrent runs. Carry `PLAN_COMMENT` forward.

Handoff: `PLAN`, `CRITERION_MAP`, `RISKS`.

## Implement

Builder via the builder-lane contract in `docs/codex-builder-lane.md`. The
lane-runner:

1. Worktree on `fix/issue-<N>-<slug>`; verify `pwd` casing.
2. **Amendment re-poll, before any commit.** Diff issue-comment timestamps
   against the `PLAN_COMMENT` snapshot; a newer scope-relevant comment is
   folded in or explicitly declared out-of-scope with a reply — never silently
   implemented against a stale snapshot (measured: issue #245).
3. *Before any code*: push an empty commit and open a **stub draft PR** — the
   durable in-flight marker. Run any repo bootstrap block verbatim.

Handoff: `WORKTREE`, `BRANCH`, `PR_URL`, `BUILDER`, `DEVIATIONS_FROM_PLAN`,
`CRITERION_STATUS`, `DIFF_STAT`. A diff past ~800 changed lines → stop and
bounce: mis-sized — split it or `/epic-plan`, don't push it into review.

## Test

Fresh worker, same worktree; it sees the issue, criteria, and impact set —
not the implementer's reasoning. Component tests with stable IDs
(`test_B_<N>_A_...`), one boundary per test, asserting through real
collaborators; mock only genuinely external things.

- **Negative control:** temporarily invert the core fix — at least one new test
  must fail (N≥1) — then restore and confirm green. A suite that survives
  reversal of its own fix asserts nothing; add a discriminating test before
  proceeding.
- Commit tests on the same branch, push.

Handoff: `TEST_IDS`, `NEGATIVE_CONTROL`, `TEST_RESULTS`, `UNCOVERED`.

## Review

One reviewer (`opus-worker`, fresh context, full PR diff) by default:
correctness against the acceptance criteria and the plan,
tests-actually-assert, security where the change touches input/IO/untrusted
data, and delete-grade speculative code (advisory only, never a blocker). On
a shared-interface hit or genuinely competing concerns, spawn up to three
lenses concurrently instead; dedup findings by file+description, keeping the
highest severity.

**Evidence bar — what keeps this loop honest.** A blocker must name its
concrete observable failure: a failing test, a repro command, or a broken
invariant verified against the code (file:line). A finding without that
evidence is advisory (should-fix / nit), never a blocker — and advisories
never trigger another cycle. Post findings on the PR itself, not just issue
prose.

**One fix cycle.** The fixer (builder lane, existing worktree) fixes blockers
and cheap should-fixes, declines the rest with a reason, and updates each
finding's PR comment with the fix commit. A blocker that survives its fix
attempt gets one retry on `opus-worker`; if it still fails → stop: BLOCKER,
and post a `CONTINUATION` comment on the issue (remaining finding IDs,
branch, `PR_URL`, last green step). The closing look at the fixes is
read-only — whatever it finds is reported, never fixed in this run.

Handoff: `FINDINGS`, `RESOLVED` (per finding: fixed / declined + reason).

## Finalize

One worker: re-run the amendment re-poll; rebase onto the current base; run
the repo's gates verbatim. Every acceptance criterion needs observed
evidence — a passing named test — and anything unproven is a BLOCKER, not a
footnote. A criterion the worktree genuinely cannot prove
(live/operator-gated) goes under a `## Deferred (post-merge)` PR section with
owner and command, and the PR then references the issue with `Refs #<N>` —
never `Closes` — so merging doesn't auto-close it while real criteria remain
open.

**Finalize gate: repo checks pass and each acceptance criterion has observed
evidence in the PR body.** The state machine is GitHub draft vs ready, nothing
else — a body phrase like "Not merging" is not a control mechanism and is
banned as one (measured: PR #254 merged 50 s after shipping one). If it isn't
ready, don't call `gh pr ready`, full stop. Mark ready only after `gh pr view
--json mergeable,mergeStateStatus` reports `MERGEABLE`/`CLEAN`; anything else →
rebase and recheck, never ship a PR GitHub can't merge.

PR body sections: what changed; brief walkthrough; edge cases; intentionally
not changed; acceptance criteria as checkboxes, each checked only with its
passing test ID named; deferred section when used; test evidence including the
negative-control line; review findings with resolutions; merge instructions
for the human (never executed).

Handoff: `STATE` (READY | BLOCKER), `PR_URL`, `CHECKS`, `BLOCKER_DETAIL`,
`CONTINUATION` when blocked.

## Resume

Read the draft PR, the plan comment, and the latest `CONTINUATION` comment;
re-create the worktree from the existing branch (never a fresh one);
re-enter at the step the continuation names — usually the fixer, scoped to
the remaining finding IDs — then finalize. Plan comment but no branch yet (a
run died mid-implement) → re-enter at implement with the posted plan.
