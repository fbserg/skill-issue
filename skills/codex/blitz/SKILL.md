---
name: blitz
description: Lightweight Codex executor for multiple ad-hoc tasks or lanes—fast, parallel, and adversarial—without the full issue or resolve-issue pipeline. Use when the user invokes /blitz or $blitz, asks to run several unfiled tasks quickly, or explicitly wants a fast adversarial fan-out. Not a planner; use epic-plan for broad planning, issue for filed GitHub work, and ww for one approval-gated lane.
---

# Blitz

Act as the orchestrator; do not implement lane work in the main checkout.

- Fan out immediately. Run independent lanes concurrently with Codex sub-agents, one isolated worktree per disjoint file set. Serialize only genuine overlap.
- Cap concurrency at ~12 active descendants per root. More lanes than that run as sequential waves, not one wide fan-out.
- Give each lane a lane-scoped task card — file scope, acceptance gate, only the rulings that bind that lane — never the full root prompt. Never let two agents edit the same checkout.
- When a lane corresponds to a filed issue, claim it for the authenticated GitHub user as the lane starts. Stop rather than stealing an issue assigned to someone else. Keep queued issues unassigned until their lane actually starts.
- Adversarially review plans, diffs, and conclusions before accepting them. Use distinct, role-locked lenses that try to refute claims against repository evidence.
- With three or more background lanes, keep a visible ledger and actively monitor every lane. A silent lane is not evidence of progress.
- Every lane must end with exactly one of `DONE` / `BLOCKED` / `HANDED_OFF` plus a one-line reason. A bare trailing message with no terminal status is a defect — chase it down before closing the ledger.
- Any FOLLOW-UP a lane surfaces is filed via `gh issue create` (label `follow-up`) before that lane may report `DONE`. A follow-up left only in transcript prose counts as dropped.
- Move through gates without re-confirming phases. Take each lane through checks, commit, push, and PR or integration as the repository policy requires.
- Stop only for scope changes, destructive ambiguity, an unresolvable failed gate, or overlapping ownership that cannot be isolated.

## Keep fast lanes fast

- Give each lane a gate ladder before it starts: cheap targeted checks, one batched preflight, then one expensive full gate. Do not use the full gate as a discovery loop.
- After any gate failure, collect the complete failure set and fix it as one batch. Re-run the narrowest checks that prove the batch before returning to the full gate.
- Never run the same expensive gate more than twice without a new diagnosis or changed hypothesis. After the second failure, stop the loop, inspect the orchestration and test topology, and report the concrete blocker.
- Treat golden drift, formatting, static analysis, resource parity, and literal audits as preflight checks. Clear all of them before the final full suite.
- Batch all known review and adversarial findings before the first push and before any hosted-CI rerun. Do not use hosted CI as a fix-by-fix feedback loop.
- Do not push cosmetic-only cleanup that restarts expensive hosted CI unless correctness or required reviewer understanding materially requires an immediate push; fold all other clarity cleanup into the next substantive batch.
- Do not accept retry-only greens for flakes. Stress the focused failure and repair lifecycle, dispatcher, shared-state, or test isolation defects; if it does not reproduce, record the stress evidence once and continue.
- Reserve shared resources explicitly (build mutexes, emulators, backend records). Release them immediately between commands; stale reservations are blockers, not queues to poll forever.
- Send a user-visible update at least every 60 seconds while work is active. Report the current command or gate, the last observed result, and the next terminal condition. Repeated `wait` calls are not progress.
- If a lane is silent for two update intervals, request a ledger update. If it remains silent or repeats the same gate, interrupt and re-scope it instead of continuing to poll.
- After targeted, preflight, and full local gates pass and adversarial review clears a lane, dependent lanes may start on explicitly tracked stacked branches while the prerequisite's hosted CI runs. Record each stack's base and dependency order.
- Merge stacks only in dependency order, and only after every final branch head receives its required hosted checks. Restack or rebase after prerequisites merge, then rerun invalidated checks without discarding the recorded proof from the pre-restack head.

Use `issue` for filed GitHub issues and its batch routing. Use `ww` for exactly one plan-first, approval-gated task. Use `epic-plan` when the work first needs decomposition.
