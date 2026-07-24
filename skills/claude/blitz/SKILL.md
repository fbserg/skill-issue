---
name: blitz
description: Lightweight executor for multiple issues or lanes — fast, parallel, adversarial — without the full /issue → /resolve-issue pipeline (no tiered phases, no typed handoffs). Use when the user invokes /blitz or says to run a batch fast and adversarial. Not a planner (that's /epic-plan) and not a pipeline; just the execution posture.
---

Boundary: filed issues wanting tiered review → `/issue` batch. Exactly one task, plan-first with approval → `/ww`. Ad-hoc, unfiled, fast → here.

You're the orchestrator; you don't implement. Posture:

- **Fan out now.** Independent lanes run in parallel worktrees (`claude --worktree` / `isolation: 'worktree'`), one lane per disjoint file set; serialize only genuine overlap. Don't do sequentially what has no dependency.
- **Cluster before you cut cards.** Disjoint file lists are not disjoint scope: linked items
  (parent/follow-up, "after #N", same surface) go in one lane or sequential waves — never
  side by side. File-scope checks and rebase gates can't catch semantic duplication
  (measured: #690/#749 raced to two overlapping merged PRs); only clustering can.
- **Lane cards, not broadcasts.** Each lane is dispatched with a scoped brief — its file scope, its acceptance gate, only the rulings that bind it — never the full root prompt re-sent verbatim. A naive re-broadcast has been measured at ~15x context inflation per fan-out; write the card instead.
  Check BOTH CLAUDE.md and AGENTS.md for binding rulings — AGENTS.md-only rulings exist
  and the session auto-loads only CLAUDE.md.
- **Micro-work gets no lane.** A ≤~50-line fix with green targeted checks commits straight to
  the integration branch (where the repo permits) — no issue, no PR, no worktree. Batch several
  into one commit train. Lanes and PRs are for work that needs review or outlives one sitting.
  (Measured: 55% of one repo's issues closed within 2h of filing — tracker as commit log.)
- **Spine files are single-writer.** Before carding, check churn (`git log --name-only`): the
  repo's most-touched wiring/shared files go to at most ONE lane per wave. "Disjoint file
  lists" that all import the same spine are not disjoint. (Measured: 98/100 sampled PRs
  overlapped a <24h-prior PR's files; a 17-PR lockstep chain on one file pair.)
- **Adversarial review before believing anything.** Distinct lenses, role-locked to refute; verify claims against the repo, not rhetoric. Applies to plans, diffs, and your own conclusions.
- **Findings return batched, never as issue confetti.** A review lane reports one batched
  finding list; at most one follow-up issue per surface. Never one issue per finding/assertion
  (measured: 42 follow-up issues filed in one day from a single UI wave).
- **3+ background lanes → arm the watchdog** (pulse files + one Monitor, the /issue pattern). Lanes die silently; fast without it is fast into a ditch.
- **Fast through gates.** No re-confirming between phases; push each lane to done (commit, PR, human merges). Stop only for real scope changes or destruction.

## Keep fast lanes fast

- A lane's first action, before any edit: record the baseline test count and restate its file scope from the card; confirm that scope doesn't overlap any sibling lane's card. Skipped, this is how four lanes collide and only find out at triage.
- Define a gate ladder per lane: targeted checks → one batched preflight → one expensive full gate. Never use the full gate to discover one failure at a time.
- On failure, collect the complete failure set, fix it as one batch, and prove the batch with narrow checks before repeating the full gate.
- Never run the same expensive gate more than twice without a new diagnosis or changed hypothesis. After the second failure, inspect orchestration/test topology and report the blocker.
- Clear golden drift, formatting, static analysis, resource parity, and literal audits in preflight. Do not interleave each finding with a full-suite rerun.
- Reject retry-only flake greens: stress the focused failure and fix lifecycle, dispatcher, shared-state, or isolation defects. Record non-reproduction evidence once.
- Reserve build mutexes, emulators, and backend records explicitly; release them between commands. Treat stale reservations as blockers.
- Emit a concrete progress pulse at least every 60 seconds: current command/gate, last observed result, next terminal condition. Repeated waits are not progress.
- Two silent pulse intervals trigger intervention: request a ledger update, then interrupt/re-scope a lane that remains silent or repeats the same gate.
- Before opening any PR: test-count delta complies with the repo's stated posture, and the branch rebases clean against current main and against every sibling lane already pushed. Fix or abandon a PR that fails this before it opens — a final triage lane rejecting finished PRs is a process failure, not a safety net.
- Merge only after required hosted checks pass; any permitted post-merge failure becomes an urgent repair before downstream landing.

<!-- accreting reminders — add one line each time the user has to repeat something -->
