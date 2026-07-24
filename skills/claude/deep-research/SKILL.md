---
name: deep-research
description: >
  Deep research harness v2 — Opus-planned dynamic fan-out with a guaranteed disconfirmation
  lens, GRADE-lite evidence tiering, first-principles reasoning, and an Opus completeness
  critic driving a bounded saturation loop. Use when the user wants a deep, multi-source,
  fact-checked research report on any topic. BEFORE invoking, check if the question is
  specific enough to research directly — if underspecified (e.g. "what car to buy" without
  budget/use-case/region), ask 2-3 clarifying questions to narrow scope. Then pass the
  refined question as args.
---

# deep-research

Dynamic research engine built on the Workflow harness. `workflow.js` owns everything —
complexity sizing, the lens catalog, evidence tiering, and the bounded saturation loop — and
selects it internally from the scope agent's complexity verdict; nothing here is caller-tunable,
so read `workflow.js` directly for the current mechanics rather than this file.

## How to invoke

```
Workflow({ scriptPath: "<this skill directory>/workflow.js", args: "<refined question>" })
```

Resolve `<this skill directory>` from the installed `deep-research` skill path,
then weave any clarifying answers into the question string before passing it.
