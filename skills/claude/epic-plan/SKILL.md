---
name: epic-plan
description: Scope a topic too big for one issue into a GitHub epic — a tracker issue carrying a frozen contract plus right-sized child issues that execute via /issue → /resolve-issue. The value is the decomposition and an adversarial review of it, front-loaded by an expensive model before any code is written; the paperwork is trivial. Use when the user invokes /epic-plan TOPIC, resumes one (/epic-plan <tracker#>), or when a task has multiple deliverables or spans multiple sessions. NOT for a single scoped change (use /issue, which files one issue) or a one-PR fix (use /resolve-issue). Creates nothing on GitHub until the user says GO.
---

Turn a topic into a GitHub epic: one **tracker** issue carrying a frozen contract, plus **child** issues each sized for a single `/resolve-issue` session. Spend tokens up front getting the split right and stress-testing it — that is the whole point. Being wrong about the decomposition is the most expensive place to be wrong; an adversarial review here is the cheapest place to catch it. Then hand the children to `/issue` and stop.

This skill OWNS scoping, research, decomposition, decomposition-review, and issue creation. It does NOT write code, run children, or open/merge child PRs — handoff ends at `/issue`. There is no orchestrator here (that was `epic-run`, deprecated). Do not reference epic-run, epic-tools, epic-research, or epic-retro; they are gone.

**The one hard gate: create nothing on GitHub until the user explicitly says GO.**

## Design notes (tensions resolved)

- **T1 — Resumability vs. "no issues until GO".** The expensive phases (scope, research, decompose, review) run before any GitHub artifact exists, so GitHub cannot checkpoint them without violating invariant #1. Stance: **honest scoping, plus a thin crash-recovery cache for the two expensive artifacts only.** The single durable correctness store is GitHub, after GO (invariant #9 — nothing downstream ever reads the cache). But the audit's own value thesis is that the front-loaded research + 4-critic review is *expensive*, and a pre-GO crash on a large epic forces redoing exactly that. So after the research synthesis and after the review revision — the two costly outputs, and only those — write them to `/tmp/epic-plan/<slug>/{research.md,review.md}`. Cheap phases (scope, decompose) are not cached; redoing them is trivial. On `/epic-plan <topic>` for a topic whose cache dir already exists, offer to reuse the cached research/review **only if the scope/contract is unchanged** — if scope shifted, the cached analysis is stale, so re-run. The cache is deleted on successful materialize. No draft-tracker-early hack (that buys a recovery path by breaking the GO gate). No per-phase state machine, no `--resume` wildcard scan, no slug-confirmation dance — the user re-invokes with the same topic, we key off the slug.
- **T2 — Orphaned labels.** Dropped. `epic-followups` / `epic-unfinished` had no live producer after `epic-run`/`epic-retro` were deprecated. No grab-bag mode, no query for them.
- **T3 — Handoff grammar.** `/issue`'s documented batch grammar is a *count selector* (`last N`, `oldest N`, or explicit numbers) with *stacking modifiers* (`oldest`, `mine`, `label:X`). A bare `/issue label:epic:<slug>` has no count selector — it is NOT a documented standalone form. So the **primary handoff is explicit child numbers** (`/issue <n1> <n2>`), which `/issue` documents verbatim and which we can emit because we created the children. The bare-label gesture is offered only in its documented stacked form, with a count: `/issue last <N> label:epic:<slug>`.
- **T4 — Cross-repo children.** Kept, conditionally. A child landing in a non-tracker repo carries a one-line **Repo:** field (repo + base branch + who merges). Omitted entirely for single-repo epics — no empty ceremony. Prior-art block stays dropped (the executor researches).
- **T5 — Bounded spend.** Research briefs carry an output cap + stop condition + share no state. Review is **one** synthesis pass, **one** skeptic re-check per blocker (can downgrade), **one** revision of the plan. No loops anywhere. Trivial epics skip research and the review panel entirely.

## Re-entry (run first, always)

GitHub is the state store after GO; the cache is crash-recovery only, before GO.

- **`/epic-plan <number|tracker-URL>`** → an already-materialized epic. Read the tracker and its children:

  ```bash
  gh issue view <N> --json title,body,labels,comments
  gh issue list --label "epic:<slug>" --json number,title,state,body
  ```

  A human comment or a `needs-revision` label is a loop-back signal — re-run the review on the current children against it, revise once, re-materialize idempotently (§Materialize skips what exists). Carry the existing tracker forward; do not restart, do not duplicate. Otherwise the epic is complete — re-report the handoff command.
- **`/epic-plan <topic>`** → new epic (or a pre-GO crash on the same topic). Derive a stable `<slug>` (kebab-case, ≤4 words) from the topic. If `/tmp/epic-plan/<slug>/research.md` or `review.md` already exists, a prior session got that far — offer to reuse it (only if scope is unchanged; see T1) and re-enter past that phase rather than re-pay. Otherwise start fresh. Continue at the early exits.

The slug is the spine of every later identity check: the cache dir, the `epic:<slug>` label, and the idempotency markers all key off it. Pick it once, reuse it everywhere.

Two early exits before any work:

- **Really one issue** (single deliverable, fits one `/resolve-issue` session) → stop, tell the user to run `/issue <topic>`. Don't build an epic for one PR.
- **Trivial epic** (2–3 obvious children, no unknowns, single repo) → skip Research and the review panel; grill briefly, decompose, run a single self-review against the Hard rules, jump to the GO gate. Don't pay for the full machine on a topic that doesn't need it (invariant #10).

## 1. Scope → freeze the contract

Grill only where the answer changes the decomposition. Generate the questions *this* topic raises — no fixed checklist — ask one at a time with a recommended answer, and answer anything the codebase can answer yourself (fan out an `Explore` agent) instead of asking the user. Refuse to proceed while success criteria, boundaries, or key terms are `TBD`.

Output is a short **contract** that goes verbatim into the tracker and binds every child:

- **Definition of done** — concrete: a passing test, a metric, a user-visible behavior.
- **Out of scope** — name the *nearest adjacent thing* an agent would wrongly pull in. (Invariant #2: "audit backups" means backups, not a dashboard cleanup.) This is the anti-scope-invention fence.
- **Constraints** — stack, conventions, interfaces that must not change.
- **Repos in play** — one, or several (drives the T4 child `Repo:` lines).

## 2. Research (front-loaded, skip on trivial epics)

Fan out self-contained briefs in **one message** — concurrent `explore-mid` agents (Sonnet, read-only), or `Explore` for a cheap single lookup. Each brief states its objective, allowed tools, an **output cap (≤600 words)**, and a **stop condition**; agents share no state. Scale lanes to the topic:

- **Codebase recon** (always) — what exists, reusable patterns, entry points, cross-process consumers, non-obvious tests, the blast radius of the likely change.
- **External landscape** (only if user-facing or the domain is genuinely unclear) — how others solve this (web / `gh search code`). Skip for purely-internal work.

```bash
git log --oneline -20
gh issue list --state open --json number,title --limit 30   # related open work — NOT a label query
```

Read the digests. Spawn **one** targeted gap wave only if a real gap surfaced — not a reflex, and never a third wave. Synthesize a tight brief: works / broken / missing / recommendation. This feeds the decomposition; it does not go into any issue body.

**Cache the synthesized brief** to `/tmp/epic-plan/<slug>/research.md` (crash-recovery only; nothing reads it downstream).

## 3. Decompose into a child DAG

Draft the children as a dependency graph. Each child:

- **Independently shippable** — one `/resolve-issue` session, one focused PR (invariant #3).
- **Right-sized** (invariant #4) — split if files-touched > ~15, LOC delta > ~1000, or > ~10 large reads. A child that *itself* needs decomposing is a **sibling epic — surface it to the user**, never a silent sub-orchestrator.
- Carries: **scope**, **machine-checkable acceptance criteria**, **`depends-on`** by ordinal (`Child 2`), **files likely touched**, a one-word **risk** (`text-only` | `visual` | `shared-state`; default `shared-state` when unsure — it drives proof expectations), and which repo only if it lands in a non-tracker repo (T4).
- **File-overlapping children must serialize** (invariant #5) — encode it in `depends-on`. `/issue` does not dependency-order, so this ordering is the executor's only guardrail.

## 4. Adversarial review of the decomposition (the core; skip on trivial epics)

Review the **decomposition, not code** — this is the value. Fan out **four `opus-worker` critics concurrently** (one message) on the same draft, each role-locked ("your job is to find flaws, not validate the plan"), none seeing another's output. Diverse lenses, never four identical refuters (invariant #6):

| Lens | Hunts for |
|---|---|
| **Completeness** | A missing child, journey, or failure mode the contract implies. |
| **Dependency-ordering** | A child consuming what a later child produces; cycles; file-overlap that should serialize but doesn't. |
| **Scope / altitude** | Two-job children to split; over-decomposition to merge; invented scope to cut (invariant #2). |
| **Premortem** | "This epic shipped and failed. Reconstruct exactly how." The blind spot the author can't see. |

Synthesize once — **no loops**:

1. Union the findings; dedup by area (file + description, highest severity wins).
2. Flagged by **2+ lenses → blocker**; by one lens → advisory.
3. **One skeptic re-check per blocker** (`opus-worker`): frame as an external claim — "a prior reviewer concluded X; find the flaw in that reasoning — is it real?" Upheld blockers stand; refuted ones drop to advisory. (T5: this lets review *shrink*, not only accrete. Skip advisories — verifying a nit costs more than the nit.)
4. **Revise the decomposition once** against the upheld blockers. Advisories are nudges, not gates.

**Cache the upheld-blocker list + the revised DAG** to `/tmp/epic-plan/<slug>/review.md`.

## GO gate (the approval that unlocks creation)

Show the user plainly — never a vague "looks good":

- the **raw upheld-blocker list** and how each was resolved in the revision,
- the **advisories** (carried as nudges, not fixed),
- the **revised plan**: tracker contract + the child list with deps, risk, files, and repo,
- the **handoff command**.

**No issue is created on GitHub before the user explicitly says GO** (invariant #1 — the hardest boundary in the skill). A "looks good" is not GO unless it clearly approves creation; if ambiguous, ask. On GO, proceed to Materialize. On a revision request, loop back to the named phase (the cache still holds the rest).

## 5. Materialize (direct `gh`, idempotent)

Only after GO. **Idempotent** (invariant #8): every create searches by a stable marker first and skips what exists — re-running never duplicates, so a mid-materialize crash is safe to re-run.

**Labels** (create if absent; `--limit 999` so the check isn't fooled by label-list pagination):

```bash
gh label list --limit 999 --json name | grep -q '"epic"'        || gh label create epic --color 5319e7 --description "Epic tracker"
gh label list --limit 999 --json name | grep -q '"epic:<slug>"' || gh label create "epic:<slug>" --color a371f7 --description "Child of epic <slug>"
```

**Tracker** — idempotency marker is the HTML comment in the body; dup-check by title under the `epic` label. Build the body from the template below, **write it to the cache file, then create from it**:

```bash
gh issue list --label epic --search "Epic: <topic> in:title" --json number,title   # exists? reuse its number, skip create
# else: write the tracker body (template below) to /tmp/epic-plan/<slug>/tracker.md, then:
gh issue create --label epic --title "Epic: <topic>" --body-file /tmp/epic-plan/<slug>/tracker.md
```

Tracker body — **no PRD bloat** (invariant #7), exactly:

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

(Fill the `## Children` checklist after the children exist; back-edit the tracker with the real numbers via `gh issue edit <tracker> --body-file ...`.)

**Children** — idempotency marker is `<!-- epic-plan:child slug=<slug> ord=<k> -->` as the first body line. For each child *k*: build its body from the template, **write it to `/tmp/epic-plan/<slug>/child-<k>.md`**, search the epic's children for the marker, and create only if absent:

```bash
gh issue list --label "epic:<slug>" --search '"epic-plan:child slug=<slug> ord=<k>"' --json number   # present? skip
# else: write child k's body (template below) to /tmp/epic-plan/<slug>/child-<k>.md, then:
gh issue create --label "epic:<slug>" --title "<child title>" --body-file /tmp/epic-plan/<slug>/child-<k>.md
```

Child body — scope + AC + deps/proof, nothing else:

```
<!-- epic-plan:child slug=<slug> ord=<k> -->
## Scope
<what this child does; one PR's worth>

## Acceptance criteria
- [ ] <machine-checkable>
- [ ] <machine-checkable>

## Depends on
#<n-of-blocking-child>          (or: none)

## Files likely touched
<paths>

## Risk & proof
<text-only | visual | shared-state>. For visual/shared-state: a screenshot/GIF or
before→after artifact is required in the child's PR.

Repo: <repo> @ <base-branch>, merged by <who>     ← only for multi-repo epics (T4)

Part of #<tracker>
```

Use `Part of #<tracker>` (not `Closes`) so merging a child never auto-closes the tracker while siblings remain open.

On successful materialize (tracker + all children exist, checklist back-filled): **delete the cache** (`rm -rf /tmp/epic-plan/<slug>/`). GitHub is now the sole state store (invariant #9).

## 6. Handoff

Report the exact run command using the **real child numbers**, dependency-ordered by us (T3 — `/issue` does not order). This skill does not execute children, write code, or open/merge PRs.

```
# independent children — run together (≤4 concurrent inside /issue):
/issue <n-independent-1> <n-independent-2>

# then the dependents, after their blockers' PRs land:
/issue <n-dependent>
```

For a fully independent set, one line: `/issue <n1> <n2> <n3>`. For chains, emit the waves in order and say which depends on which. As a documented alternative for an all-independent epic, the bare-label form works *only with a count* — `/issue last <N> label:epic:<slug>` (N = child count); the count-less `/issue label:epic:<slug>` is not a form `/issue` documents, so don't emit it.

For risky epics (deletions, migrations, multi-file behavior changes), suggest an `/adversary` cross-model pass before execution. Then you're done — `/issue` → `/resolve-issue` owns execution and merging; a human merges each PR.

## Hard rules

- **No issues until the user says GO.** The plan is presented and approved first. (Invariant #1.)
- **Don't invent scope.** "Audit backups" means backups — the Out-of-scope line is the fence. (Invariant #2.)
- **Children independently shippable** — one PR, one `/resolve-issue` session each. (Invariant #3.)
- **Right-sized children.** >15 files / >1000 LOC / >10 large reads → split. A child needing its own decomposition is a sibling epic, surfaced — never a silent sub-orchestrator. (Invariant #4.)
- **Dependency order is explicit.** File-overlapping children serialize via `depends-on`; `/issue` won't order them for you. (Invariant #5.)
- **Diverse review lenses, never N identical refuters.** Same-prompt panels converge and add nothing. (Invariant #6.)
- **No PRD bloat.** Tracker = Goal + Contract + Children; child = Scope + AC (+ deps/files/proof). Nothing else. (Invariant #7.)
- **Materialize is idempotent.** Search by stable marker, skip what exists — re-runs never duplicate. (Invariant #8.)
- **GitHub is the state store after GO; the cache is crash-recovery only before GO.** Nothing downstream reads the cache; losing it costs a re-run, never correctness. (Invariant #9.)
- **Scale to the topic.** Trivial epic → no research, no review panel. Large/risky → full pipeline. (Invariant #10.)
