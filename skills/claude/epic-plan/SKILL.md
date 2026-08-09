---
name: epic-plan
description: "Scope a topic too big for one issue into a GitHub epic: a tracker issue with a frozen contract plus right-sized child issues. Use for /epic-plan TOPIC, resuming one (/epic-plan <tracker#>), or any multi-deliverable/multi-session task. NOT for a single scoped change. Materializes on GitHub autonomously."
---

Turn a topic into one **tracker** issue carrying a frozen contract plus
**child** issues each sized for a single `/resolve-issue` session. A wrong
decomposition is the most expensive place to be wrong, so tokens go into the
split and its adversarial review — never into code; handoff ends at the
executors. **No approval gate:** materialize the reviewed decomposition
immediately — it's idempotent, so a user revision afterwards edits issues in
place.

## Re-entry (run first)

- **Tracker number/URL** → already materialized; GitHub is the sole state
  store. Re-sync the tracker checklist against actual child states (children
  close out of band). `needs-revision` label or human comment → re-run the
  review against live state, revise once, re-materialize idempotently — never
  restart or duplicate. Otherwise report shipped / runnable-now / next wave.
  Last child merged → verify the *composed* result against the contract's
  Done criteria (end-to-end, not per-child green), suggest `/simplify-sweep`
  over the epic's range, close the tracker with a one-comment summary.
- **Topic** → new epic. A stable kebab `<slug>` (≤4 words) keys
  `/tmp/epic-plan/<slug>/`, the `epic:<slug>` label, and the idempotency
  markers. Reuse cached research/review from a crashed run only if scope is
  unchanged.
- **Non-tracker issue number** → treat as topic seed (the landing path for
  `/resolve-issue` bouncing an epic); note close-or-supersede in the tracker
  body.

Early exits: **really one issue** → `/issue <topic>`. **Trivial epic** (2–3
obvious children, no unknowns) → skip research and the panel, decompose,
materialize.

## Contract (freeze before decomposing)

Ask only questions whose answer changes the decomposition — one at a time,
each with a recommended answer; refuse to proceed on `TBD` success criteria,
boundaries, or key terms. The contract goes
verbatim into the tracker and binds every child:

- **Definition of done** — concrete: a passing test, a metric, a visible behavior.
- **Out of scope** — the nearest adjacent thing an agent would wrongly pull in.
- **Constraints** — stack, conventions, interfaces that must not change.
- **Repos in play** — multi-repo: each child names its repo; `depends-on`
  orders children within one repo, cross-repo ordering is separate waves.

## Research (skip on trivial epics)

Concurrent read-only recon agents in one message — codebase always; external
landscape only if user-facing or the domain is unclear. Synthesize
works / broken / missing / recommendation to
`/tmp/epic-plan/<slug>/research.md`; the relevant slices feed each child's
Context stanza so executors never re-pay for the recon.

## Decompose into a child DAG

- **Vertically by capability, never by layer** — each child demoable end to
  end.
- **Disjoint file sets are a design goal** — overlap means re-cut the
  boundary first; `depends-on` only when the overlap is real. Overlapping
  siblings left unordered is a decomposition failure.
- **Each Done criterion traces to exactly one child** — untraceable →
  missing child; child proving nothing → invented scope. Genuine unknowns →
  time-boxed spike children gating via `depends-on`.
- Each child: one `/resolve-issue` session; ~8 children max (completion
  velocity collapses above that).

## Adversarial review (skip on trivial epics)

Schema pre-check yourself (every child fully filled), then concurrent
`opus-worker` critics role-locked to find flaws, distinct lenses:
completeness, dependency-ordering, scope/altitude/value, feasibility &
testability, premortem. Synthesize once per
`docs/adversarial-review-panel.md` — no loops. Revise once against upheld
blockers; advisories are nudges.

## Materialize (direct `gh`, idempotent) + report

Every create searches for its stable marker first and skips what exists —
re-running never duplicates, so a mid-materialize crash is safe. **Never pair
titles to bodies via shell array indexing** (zsh is 1-indexed; measured
title/body off-by-one) — one explicit create per child. Labels `epic` and
`epic:<slug>` (create if absent; `--limit 999` so pagination doesn't fool the
check). Tracker — dup-check by title under `epic`:

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
`'"epic-plan:child slug=<slug> ord=<k>"'` under the `epic:<slug>` label,
create only if absent:

```
<!-- epic-plan:child slug=<slug> ord=<k> -->
## Scope
<one PR's worth>

## Context
<3–5 recon facts this child needs to start cold — the executor must not
re-pay for this.>

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
Report alongside materialization: upheld blockers and how each was resolved,
the revised plan (contract + child list with deps/risk/files/repo), and the
handoff. The one thing that stops for input: an unresolved contract
ambiguity.

## Handoff

Report the exact run commands with real child numbers, dependency-ordered by
us — the executors do not order dependencies. One child → `/issue <N>`; a
wave of independent children → `/blitz` with the issue numbers:

```
/blitz <n-independent-1> <n-independent-2>     # wave 1
/issue <n-dependent>                           # after wave 1's PRs land
```

Code-dependent waves that can't wait for merges: base the wave's branches on
a `stack/<epic>-<wave>` integration branch (children → wave branch → main,
merged in order) rather than stacking PRs on unmerged sibling branches, and
land each wave before opening the next — GitHub does not retarget a PR whose
unmerged base is rewritten, so every open PR above a revised base is a manual
rebase (measured: one epic stranded 19 open PRs on unmerged bases).

Multi-repo: one wave block per repo, run from that repo. Risky epics
(deletions, migrations, multi-file behavior changes) → suggest an
`/adversary` pass before execution. Then stop — executors own execution; a
human merges each PR.

## Hard rules

1. **Materialize autonomously.** No approval gate — only a genuine contract ambiguity stops for input.
2. **Don't invent scope.** "Audit backups" means backups — the Out-of-scope line is the fence.
3. **No PRD bloat.** Tracker = Goal + Contract + Children; child = the template, nothing else.
