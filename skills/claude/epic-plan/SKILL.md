---
name: epic-plan
description: "Scope a topic too big for one issue into a GitHub epic: a tracker issue with a frozen contract plus right-sized child issues that execute via /issue → /resolve-issue. The value is the decomposition and its adversarial review, front-loaded before any code. Use for /epic-plan TOPIC, resuming one (/epic-plan <tracker#>), or any multi-deliverable/multi-session task. NOT for a single scoped change (/issue) or one-PR fix (/resolve-issue). Materializes on GitHub autonomously."
---

Turn a topic into a GitHub epic: one **tracker** issue carrying a frozen
contract, plus **child** issues each sized for a single `/resolve-issue`
session. Spend tokens up front getting the split right — a wrong decomposition
is the most expensive place to be wrong, and an adversarial review here is the
cheapest place to catch it. This skill owns scoping, research, decomposition,
review, and issue creation; it never writes code or runs children — handoff
ends at `/issue`.

**No approval gate:** once the reviewed decomposition is ready, materialize it
on GitHub immediately and report the plan + issue numbers in the same breath.
Materialization is idempotent, so a user revision afterwards edits issues in
place — a wrong decomposition costs an edit, not a restart.

## Re-entry (run first, always)

- **`/epic-plan <number|tracker-URL>`** → already materialized; GitHub is the
  sole state store (`gh issue view <N> ...`; `gh issue list --label
  "epic:<slug>" --state all ...`). Re-sync the tracker checklist against
  actual child states first (children close out of band; tick via `gh issue
  edit --body-file`). A human comment or `needs-revision` label → re-run the
  review against the live tracker + children, revise once, re-materialize
  idempotently — never restart or duplicate. Otherwise report status: shipped
  children, runnable-now children, the next `/issue` wave. **Close-out:** when
  the last child merges, verify the *composed* result against the contract's
  Done criteria (end-to-end, not per-child green), suggest `/simplify-sweep`
  over the epic's commit range, close the tracker with a one-comment summary.
- **`/epic-plan <topic>`** → new epic. Derive a stable `<slug>` (kebab-case,
  ≤4 words); it keys the cache dir (`/tmp/epic-plan/<slug>/`), the
  `epic:<slug>` label, and the idempotency markers. Cached `research.md` /
  `review.md` from a crashed prior run → reuse only if scope is unchanged.
- **`/epic-plan <number>` on a non-tracker issue** → treat it as the topic
  seed (the landing path for `/resolve-issue` bouncing an epic); note
  close-or-supersede in the new tracker body.

Two early exits: **really one issue** → stop, point at `/issue <topic>`.
**Trivial epic** (2–3 obvious children, no unknowns) → skip research and the
panel, grill briefly, decompose, materialize immediately.

## 1. Scope → freeze the contract

Grill only where the answer changes the decomposition — questions generated
from *this* topic, one at a time with a recommended answer; anything the
codebase can answer, answer yourself. Refuse to proceed on `TBD` success
criteria, boundaries, or key terms. Output is a short **contract**, verbatim
into the tracker, binding every child:

- **Definition of done** — concrete: a passing test, a metric, a visible behavior.
- **Out of scope** — name the *nearest adjacent thing* an agent would wrongly
  pull in. This is the anti-scope-invention fence.
- **Constraints** — stack, conventions, interfaces that must not change.
- **Repos in play** — for multi-repo epics each child names its repo, and
  `depends-on` only orders children within one repo's batch; cross-repo
  ordering is expressed as separate handoff waves.

## 2. Research (skip on trivial epics)

Fan out concurrent read-only research agents in one message — codebase recon
always (what exists, reusable patterns, blast radius, non-obvious tests);
external landscape only if user-facing or the domain is unclear. Each brief:
objective, ≤600-word cap, stop condition. One targeted gap wave at most.
Synthesize a tight brief — works / broken / missing / recommendation — cached
to `/tmp/epic-plan/<slug>/research.md`. The relevant slices feed each child's
Context stanza, so executors never re-pay for the recon.

## 3. Decompose into a child DAG

- **Vertically by capability, never by layer** — each child demoable
  end-to-end, not a stratum. **Child 1 is the walking skeleton** — the thinnest
  end-to-end path; later children thicken it.
- **Disjoint file sets are a design goal** — overlap is a smell: re-cut the
  boundary first; serialize via `depends-on` only when the overlap is real.
  Overlapping siblings left unordered is a decomposition failure.
- **Derive children from the Done-list** — each criterion traces to exactly one
  child; an untraceable criterion is a missing child, a child proving nothing
  is invented scope. **When torn, cut by risk** — the child that could
  invalidate the plan goes first. **Genuine unknowns become spike children** —
  time-boxed, deliverable is a decision on the tracker, gating via `depends-on`.
- Each child: independently shippable in one `/resolve-issue` session;
  right-sized by decision count, not just LOC (a child that itself needs
  decomposing is a sibling epic — surface it); ~8 children max (completion
  velocity collapses above that). Carries scope, machine-checkable acceptance
  criteria, context, `depends-on`, files likely touched, risk
  (`text-only`|`visual`|`shared-state`), and repo for multi-repo epics.

## 4. Adversarial review of the decomposition (skip on trivial epics)

Schema pre-check yourself first (every child fully filled). Then fan out
`opus-worker` critics concurrently on the draft, role-locked to find flaws,
distinct lenses: **completeness** (missing child/journey/failure mode),
**dependency-ordering** (cycles, consuming later work, unserialized overlap),
**scope/altitude/value** (two-job children, over-decomposition, invented
scope), **feasibility & testability** (one-session-sized on evidence; every AC
passes or fails as written), **premortem** ("this epic shipped and failed —
reconstruct how"). Synthesize once per `docs/adversarial-review-panel.md` —
no loops. Revise once against upheld blockers; advisories are nudges. Cache to
`/tmp/epic-plan/<slug>/review.md`.

## 5. Materialize (direct `gh`, idempotent) + report

Every create searches for its stable marker first and skips what exists —
re-running never duplicates, so a mid-materialize crash is safe. **Never pair
titles to bodies via shell array indexing** (zsh is 1-indexed; measured
title/body off-by-one) — one explicit create per child.

Labels (create if absent; `--limit 999` so pagination doesn't fool the check):
`epic` and `epic:<slug>`. Tracker — dup-check by title under `epic`, body to
`/tmp/epic-plan/<slug>/tracker.md`:

```
<!-- epic-plan:tracker slug=<slug> -->
## Goal
<one paragraph>

## Contract
**Done:** ...
**Out of scope:** ...
**Constraints:** ...

## Children
- [ ] #<n1> <title>  (deps: none)
- [ ] #<n2> <title>  (deps: #<n1>)
```

(Back-fill `## Children` with real numbers via `gh issue edit --body-file`.)

Children — marker is the first body line; search
`'"epic-plan:child slug=<slug> ord=<k>"'` under the `epic:<slug>` label, create
only if absent, body per child:

```
<!-- epic-plan:child slug=<slug> ord=<k> -->
## Scope
<one PR's worth>

## Context
<3–5 recon facts this child needs to start cold — from §2; the executor must
not re-pay for this.>

## Acceptance criteria
- [ ] <machine-checkable>

## Depends on
#<n>          (or: none)

## Files likely touched
<paths>

## Risk & proof
<text-only | visual | shared-state>. For visual/shared-state a before→after
artifact is required in the child's PR.

Repo: <repo> @ <base-branch>     ← only for multi-repo epics

Part of #<tracker>. On merge, tick this child's box in the tracker checklist.
```

`Part of #<tracker>`, never `Closes`, so a child's merge can't auto-close the
tracker. On success delete the cache — GitHub is now the sole state store.

Report alongside materialization — never a vague "looks good": the upheld
blockers and how each was resolved, the advisories, the revised plan (contract
+ child list with deps/risk/files/repo), and the handoff command. User
revisions loop back to the named phase and re-materialize idempotently. The
one thing that still stops for input: an unresolved contract ambiguity (§1).

## 6. Handoff

Report the exact run command with real child numbers, dependency-ordered by
us — `/issue` does not order dependencies:

```
/issue <n-independent-1> <n-independent-2>     # wave 1
/issue <n-dependent>                           # after wave 1's PRs land
```

Multi-repo: one wave block per repo, run from that repo. For risky epics
(deletions, migrations, multi-file behavior changes) suggest an `/adversary`
pass before execution. Then stop — `/issue` → `/resolve-issue` owns execution;
a human merges each PR.

## Hard rules

1. **Materialize autonomously.** No approval gate — create the issues as soon as the reviewed decomposition is ready. Only a genuine contract ambiguity (§1) stops for input.
2. **Don't invent scope.** "Audit backups" means backups — the Out-of-scope line is the fence.
3. **No PRD bloat.** Tracker = Goal + Contract + Children; child = the template, nothing else.
