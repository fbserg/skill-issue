---
name: blitz
description: Lightweight Codex executor for multiple ad-hoc tasks or lanes—fast, parallel, and adversarial—without the full issue or resolve-issue pipeline. Use when the user invokes /blitz or $blitz, asks to run several unfiled tasks quickly, or explicitly wants a fast adversarial fan-out. Not a planner; use epic-plan for broad planning, issue for filed GitHub work, and ww for one approval-gated lane.
---

# Blitz

Act as the orchestrator; do not implement lane work in the main checkout.

- Fan out immediately. Run independent lanes concurrently with Codex sub-agents, one isolated worktree per disjoint file set. Serialize only genuine overlap.
- Give every lane explicit ownership, acceptance criteria, required checks, and a finish condition. Never let two agents edit the same checkout.
- Adversarially review plans, diffs, and conclusions before accepting them. Use distinct, role-locked lenses that try to refute claims against repository evidence.
- With three or more background lanes, keep a visible ledger and actively monitor every lane. A silent lane is not evidence of progress.
- Move through gates without re-confirming phases. Take each lane through checks, commit, push, and PR or integration as the repository policy requires.
- Stop only for scope changes, destructive ambiguity, an unresolvable failed gate, or overlapping ownership that cannot be isolated.

Use `issue` for filed GitHub issues and its batch routing. Use `ww` for exactly one plan-first, approval-gated task. Use `epic-plan` when the work first needs decomposition.
