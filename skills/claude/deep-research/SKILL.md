---
name: deep-research
description: >
  Deep multi-source, fact-checked research report via the Workflow harness. BEFORE
  invoking, check the question is specific enough — if underspecified (e.g. "what car
  to buy" without budget/use-case/region), ask 2-3 clarifying questions first, then
  pass the refined question as args.
---

# deep-research

Dynamic research engine built on the Workflow harness. `workflow.js` owns everything —
complexity sizing, the lens catalog, evidence tiering, and the bounded saturation loop — and
selects it internally from the scope agent's complexity verdict; nothing here is caller-tunable,
so read `workflow.js` directly for the current mechanics rather than this file.

Every `agent()` call inside `workflow.js` names an explicit `agentType`: `worker` for
search/fetch/verify (judgment, not mechanical, so not `bulk`), `opus-worker` only for the
scope/critic/reasoning/synthesize judgment-and-synthesis stages — never a bare fan-out at Opus
(`docs/subagent-model-effort.md`).

## How to invoke

Run scope-only first — a Workflow can't ask the user mid-run, so this is a two-step dance:

1. **Scope-only pass.** `Workflow({ scriptPath: "<this skill directory>/workflow.js", args: { question: "<refined question>", mode: "scope" } })`.
   Returns the denominator (what population/dataset the question is actually measuring
   against, flagged if it looks too narrow), the angle plan with boundaries, and one live
   sample row (one real search + fetch) — no fan-out yet. Show this to the user (measured:
   an analysis fan-out burned ~6h on a slice that was 0.1% of the business before anyone
   checked the scope).
2. **On an explicit yes**, run the full workflow, reusing the confirmed plan instead of
   re-deriving it: `Workflow({ scriptPath: "...", args: { question: "<refined question>", mode: "full", confirmedScope: <the confirmedScope object from step 1> } })`.

A bare string `args` (legacy) still runs the full workflow directly, deriving its own scope —
use only when the caller has already gotten explicit confirmation another way.

Resolve `<this skill directory>` from the installed `deep-research` skill path,
then weave any clarifying answers into the question string before passing it.
