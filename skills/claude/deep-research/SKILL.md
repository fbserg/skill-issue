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

Call the local workflow script (leaner than the built-in):

```
Workflow({ scriptPath: "/Users/serg/projects/skill-issue/skills/claude/deep-research/workflow.js", args: "<refined question>" })
```

Weave any clarifying answers into the question string before passing it.

## Pipeline (handled by the workflow)

```
Scope (1 agent)     — decomposes question into 3 search angles
Search (3 agents)   — parallel WebSearch per angle
Fetch (≤8 agents)   — URL-dedup → fetch sources → extract falsifiable claims
Verify (≤24 agents) — 2-vote adversarial check per claim (both must refute to kill)
Synthesize (1 agent)— merge dupes, rank by confidence, write cited report
```

Total: ~15–37 agents. Takes 1–3 minutes.

## Output

Returns a structured report with: summary, findings (claim + confidence + sources + evidence),
caveats, open questions, and per-claim vote tallies. Also returns the full source list and stats.
