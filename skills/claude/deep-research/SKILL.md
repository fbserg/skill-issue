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

Dynamic research engine built on the Workflow harness. Sizes itself to query complexity,
guarantees a disconfirmation angle (science *and* counter-examples, not parroted consensus),
tiers every claim by evidence strength, and loops until an Opus critic says saturated.

## When to use

- User asks for a research report, fact-check, or multi-source investigation on any topic
- Question is specific enough to search directly (if not, ask 2–3 clarifying questions first)

## How to invoke

```
Workflow({ scriptPath: "<this skill directory>/workflow.js", args: "<refined question>" })
```

Resolve `<this skill directory>` from the installed `deep-research` skill path,
then weave any clarifying answers into the question string before passing it.

## Pipeline

```
Scope      (1, Opus)       — judge complexity → N angles w/ boundaries+lenses, ≥1 disconfirmation
Search     (N, Sonnet)     — one boundary-scoped WebSearch agent per angle
Fetch      (≤M, Sonnet)    — URL-dedup → fetch → extract claims w/ evidence tier
Verify     (~5–8, Sonnet)  — central claims only, 1 skeptic each; refuted → "contested", not killed
Critic     (1/round, Opus) — gaps/overstatement/one-sidedness → ≤2 targeted extra rounds, or saturated
Reasoning  (≤3, Opus)      — first-principles passes over the claim pool (empirical topics only)
Synthesize (1, Opus)       — tiered findings + contested block + honest caveats
```

### Dynamic sizing (set by the Opus scope agent's complexity verdict)

| complexity | angles | fetches/round | central-claim verify cap | extra rounds |
|---|---|---|---|---|
| simple | 2–3 | 6 | 4 | 0 |
| moderate | 3–5 | 12 | 6 | 1 |
| complex | 5–8 | 20 | 8 | 2 |

A `+Nk` token budget on the invocation also clamps the loop — extra rounds are skipped when
remaining budget drops below ~80k.

### Lens catalog (angles are drawn from these)

`broad-primary · mechanism · empirical-trials · contrarian-disconfirmation ·
heterogeneity-subgroups · practitioner-folk-origin · historical-why-belief-exists ·
steelman-opposite`

**Disconfirmation guarantee:** at least one angle is always `contrarian-disconfirmation` —
null results, failed replications, debunkings, failure conditions. Enforced in the scope
prompt AND in harness code (a fallback angle is injected if the planner skips it).

### Evidence tiers (GRADE-lite, on every extracted claim)

`rct_meta > rct > observational > mechanistic > expert_opinion > anecdote_folk`

Extraction also flags `isMechanisticInference` — the source's own "should work because…"
reasoning stated as if measured. The skeptic and critic both check for tier mismatch
(mechanism dressed as proof), and synthesis never launders a claim into a higher tier.

### Bounded saturation loop

Each round runs Search→Fetch→Verify on the current angle set, dedups new claims by
normalized text against everything already seen, then the Opus critic judges the pool.
If it reports `missingAngles` and the round budget allows, those angles become the next
round's targets (≤2 extra rounds by complexity tier). Otherwise the run finalizes; the
critic's overstatement/one-sidedness notes fold into the report's caveats.

### Verify semantics

Refuted ≠ deleted. A skeptic-refuted claim is **demoted** to a `contested[]` block surfaced
in the report — the reader sees the dispute. Supporting/tangential claims skip verification
entirely and lean on extraction quality plus the critic.

## Model mix (deliberate Opus override)

| Phase | Model |
|---|---|
| Scope, Critic, Reasoning, Synthesize | **Opus** |
| Search, Fetch, Verify | Sonnet |

This intentionally overrides the global "subagents are Sonnet-max" rule — user-authorized
for this skill. Decomposition quality, gap-judgment, and non-sycophantic synthesis drive the
whole run; retrieval and extraction stay on Sonnet. Dynamic sizing keeps simple queries cheap
(2–3 Sonnet searches, no reasoning phase, 0 extra rounds).

## Output

Structured report: `summary`, `findings[]` (claim + confidence + **evidence tier** + sources
+ evidence), `contested[]` (demoted claims with skeptic evidence), `reasoned[]`
(first-principles conclusions tagged `reasoned-from-cited-mechanism` with the claim ids they
lean on), `caveats` (including critic notes), `openQuestions[]`, full source list, per-round
log, and stats.
