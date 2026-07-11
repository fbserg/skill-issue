---
name: blitz
description: Lightweight executor for multiple issues or lanes — fast, parallel, adversarial — without the full /issue → /resolve-issue pipeline (no tiered phases, no typed handoffs). Use when the user invokes /blitz or says to run a batch fast and adversarial. Not a planner (that's /epic-plan) and not a pipeline; just the execution posture.
---

Boundary: filed issues wanting tiered review → `/issue` batch. Exactly one task, plan-first with approval → `/ww`. Ad-hoc, unfiled, fast → here.

You're the orchestrator; you don't implement. Posture:

- **Fan out now.** Independent lanes run in parallel worktrees (`claude --worktree` / `isolation: 'worktree'`), one lane per disjoint file set; serialize only genuine overlap. Don't do sequentially what has no dependency.
- **Adversarial review before believing anything.** Distinct lenses, role-locked to refute; verify claims against the repo, not rhetoric. Applies to plans, diffs, and your own conclusions.
- **3+ background lanes → arm the watchdog** (pulse files + one Monitor, the /issue pattern). Lanes die silently; fast without it is fast into a ditch.
- **Fast through gates.** No re-confirming between phases; push each lane to done (commit, PR, human merges). Stop only for real scope changes or destruction.

## Keep fast lanes fast

- Define a gate ladder per lane: targeted checks → one batched preflight → one expensive full gate. Never use the full gate to discover one failure at a time.
- On failure, collect the complete failure set, fix it as one batch, and prove the batch with narrow checks before repeating the full gate.
- Never run the same expensive gate more than twice without a new diagnosis or changed hypothesis. After the second failure, inspect orchestration/test topology and report the blocker.
- Clear golden drift, formatting, static analysis, resource parity, and literal audits in preflight. Do not interleave each finding with a full-suite rerun.
- Reject retry-only flake greens: stress the focused failure and fix lifecycle, dispatcher, shared-state, or isolation defects. Record non-reproduction evidence once.
- Reserve build mutexes, emulators, and backend records explicitly; release them between commands. Treat stale reservations as blockers.
- Emit a concrete progress pulse at least every 60 seconds: current command/gate, last observed result, next terminal condition. Repeated waits are not progress.
- Two silent pulse intervals trigger intervention: request a ledger update, then interrupt/re-scope a lane that remains silent or repeats the same gate.
- Merge only after required hosted checks pass; any permitted post-merge failure becomes an urgent repair before downstream landing.

<!-- accreting reminders — add one line each time the user has to repeat something -->
