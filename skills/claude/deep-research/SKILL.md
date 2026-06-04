---
name: deep-research
description: >
  Deep research harness — fan-out web searches, fetch sources, adversarially verify claims,
  synthesize a cited report. Use when the user wants a deep, multi-source, fact-checked
  research report on any topic. BEFORE invoking, check if the question is specific enough
  to research directly — if underspecified (e.g. "what car to buy" without budget/use-case/region),
  ask 2-3 clarifying questions to narrow scope. Then pass the refined question as args.
---

# deep-research

Thin wrapper around the built-in `deep-research` named workflow baked into the Claude Code binary.

## When to use

- User asks for a research report, fact-check, or multi-source investigation on any topic
- Question is specific enough to search directly (if not, ask 2–3 clarifying questions first)

## How to invoke

Call the built-in workflow, passing the question as `args`:

```
Workflow({ name: "deep-research", args: "<refined question>" })
```

Weave any clarifying answers into the question string before passing it.

## Pipeline (handled by the workflow)

```
Scope (1 agent)     — decomposes question into 5 search angles
Search (5 agents)   — parallel WebSearch per angle
Fetch (≤15 agents)  — URL-dedup → fetch sources → extract falsifiable claims
Verify (≤75 agents) — 3-vote adversarial check per claim (≥2 refutes kills it)
Synthesize (1 agent)— merge dupes, rank by confidence, write cited report
```

Total: ~30–100 agents depending on source count. Takes 2–5 minutes.

## Output

Returns a structured report with: summary, findings (claim + confidence + sources + evidence),
caveats, open questions, and per-claim vote tallies. Also returns the full source list and stats.
