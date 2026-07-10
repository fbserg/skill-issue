# Decisions

Durable rulings on contested choices. Check here before re-litigating; a
standing ruling short-circuits the debate unless its reopen condition fired.

## 2026-07-10 — Orchestration lineup: four entry points, no wave-loop orchestrator

**Decision:** the lineup stays four execution entry points with explicit
boundaries, no new orchestrator skill.

- `/epic-plan` plans (tracker + children, adversarial decomposition review, GO
  gate, close-out verification). It never executes.
- `/issue` runs FILED issues — single or batch (≤4 lanes, watchdog,
  GitHub-state resume) via `/resolve-issue`, which self-scales.
- `/blitz` runs AD-HOC/UNFILED lanes fast: parallel worktrees + adversarial
  review + no gate re-confirmation; watchdog required at 3+ background lanes.
- `/ww` is exactly one lane, plan-first, approval-gated.

**Killed:** epic-run revival (any wave-loop skill). /issue batch already owns
concurrency/resume/watchdog; the residual gap (cross-/issue wave sequencing,
tracker checklist sync, composed verification) went into epic-plan's re-entry
and close-out text instead of a new skill. The old epic-run died of machinery
(lock label, own CLI, tick loop, orchestrator merging) that never addressed its
real failures (verification debt, cross-child duplication, sequencing leaks).

**Evidence:** field audit 2026-07-10 — 9 marker-confirmed epics / 46 children
over 4 weeks, 8 epic-plan transcript sessions; July-2026 practitioner consensus
(native primitives + simple loops over hand-rolled pipelines, SDD backlash for
solo work, 3–5 lane ceiling, distinct-lens panels).

**Reopen when:** Anthropic's Dynamic Workflows (research preview, June 2026)
graduates and subsumes the hand-rolled fan-out conventions; or a real epic
stalls specifically on nobody executing the /issue waves in order; or /blitz
lanes repeatedly die despite the watchdog line.

**Consciously skipped** (simplicity ruling): retro/playbook-capture skill,
PR-babysitting/merge-queue skill, generic "what's in flight" command. Revisit
on second occurrence of the pain.

## 2026-07-05 — Codex is the default builder in resolve-issue

**Decision:** `/resolve-issue`'s write phases (implement, fixer) run on Codex
by default, wrapped in a Sonnet lane-runner that owns worktree/git/PR mechanics
and independently verifies the result. Claude keeps every judgment phase
(plan, review lenses, blocker skeptics) and the test writer. `--builder sonnet`
is the fallback knob. Tiering: **Sonnet researches, Opus judges, Codex builds**
(assess moved Opus → Sonnet in the same ruling).

**Reverses (narrowly):** 2026-06-20 "going full claude, codex is being phased
out" — which killed the old Codex-*owned* epic-run pipeline. This ruling does
not resurrect that: Codex is a builder inside a Claude-judged pipeline, never
the orchestrator, and its self-reports are never trusted as verification.

**Evidence:** architect-loop's Claude-architect/GPT-builder split (the six
mechanisms stolen in PR #9 came from the same design); Codex quota is a
separate, cheaper pool than the Claude main profile; the pipeline's independent
Claude test writer + review panel already compensates for the measured
distrust-Codex failure modes (fixes the reported case, misses the symmetric
one; misreports its own regressions). Known cost, accepted: one Codex lane is
slow (~3× a Sonnet workflow's wall-clock, measured) — acceptable because
implement is serial anyway.

**Reopen when:** Codex quota economics or schema-enforced returns change
materially; or two consecutive pipeline runs where the Codex builder's output
fails review on defects a Sonnet builder demonstrably wouldn't produce; or
`/issue` batch lanes need >2 concurrent builder lanes (wall-clock cost then
dominates — re-measure).

## 2026-06-20 — Full-Claude orchestration; Codex epic pipeline retired

**Decision:** the Codex-owned `epic-run` pipeline and its skill tree moved to
`deprecated/`; `epic-plan` rebuilt Claude-only. Codex retained only as
cross-model reviewer (`/adversary`) and stuck-subtask escalation.

**Superseded (narrowly)** by the 2026-07-05 ruling above: Codex returns as
default *builder* under Claude judgment. The "Codex never orchestrates"
component of this ruling stands.
