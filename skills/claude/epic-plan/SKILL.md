---
name: epic-plan
description: Scope a topic too big for one issue into a GitHub epic — a tracker issue carrying a frozen contract plus right-sized child issues that execute via /issue → /resolve-issue. The value is the decomposition and an adversarial review of it, front-loaded by an expensive model before any code is written; the paperwork is trivial. Use when the user invokes /epic-plan TOPIC, resumes one (/epic-plan <tracker#>), or when a task has multiple deliverables or spans multiple sessions. NOT for a single scoped change (use /issue, which files one issue) or a one-PR fix (use /resolve-issue). Materializes the epic on GitHub autonomously once the reviewed decomposition is ready.
---

Turn a topic into a GitHub epic: one **tracker** issue carrying a frozen contract, plus **child** issues each sized for a single `/resolve-issue` session. Spend tokens up front getting the split right and stress-testing it — being wrong about the decomposition is the most expensive place to be wrong, and an adversarial review here is the cheapest place to catch it. Then hand the children to `/issue` and stop.

This skill OWNS scoping, research, decomposition, decomposition-review, and issue creation. It does NOT write code, run children, or open/merge child PRs — handoff ends at `/issue`.

**No approval gate: once the reviewed decomposition is ready, materialize it on GitHub immediately and report the plan + issue numbers in the same breath.** (Materialization is idempotent, so a user revision afterwards edits issues in place — a wrong decomposition costs an edit, not a restart.)

## Re-entry (run first, always)

- **`/epic-plan <number|tracker-URL>`** → an already-materialized epic. GitHub is the sole state store now — read it, never the cache:

  ```bash
  gh issue view <N> --json title,body,labels,comments
  gh issue list --label "epic:<slug>" --state all --json number,title,state,body
  ```

  First, **re-sync the tracker checklist** against actual child states — children close out of band and the checklist rots silently; tick merged/closed children via `gh issue edit <tracker> --body-file`. Then: a human comment or `needs-revision` label is a loop-back signal — re-run the review against the live tracker + children (there is no cache post-materialize), revise once, re-materialize idempotently. Carry the existing tracker forward; never restart or duplicate. Otherwise report status: which children shipped, which are runnable now, the next `/issue` wave.

  **Close-out:** when the last child merges, the epic isn't done — verify the *composed* result against the contract's Done criteria (`/verify`-style, end-to-end, not per-child green), suggest `/simplify-sweep` over the epic's commit range to catch cross-child duplication from parallel lanes, then close the tracker with a one-comment summary.
- **`/epic-plan <topic>`** → new epic (or a pre-materialize crash on the same topic). Derive a stable `<slug>` (kebab-case, ≤4 words); it keys the cache dir, the `epic:<slug>` label, and the idempotency markers. If `/tmp/epic-plan/<slug>/research.md` or `review.md` exists, a prior session got that far — reuse it only if the scope is unchanged, and re-enter past that phase.
- **`/epic-plan <number>` where the issue is NOT a tracker** (no `epic-plan:tracker` marker) → treat the issue as the topic seed: derive the slug from its title, note close-or-supersede in the new tracker body, continue as a new epic. This is the landing path for `/resolve-issue` bouncing an epic-shaped issue here.

Two early exits before any work:

- **Really one issue** (single deliverable, one `/resolve-issue` session) → stop, tell the user to run `/issue <topic>`.
- **Trivial epic** (2–3 obvious children, no unknowns, single repo) → skip Research and the review panel. Grill briefly, decompose, check the draft against the Hard rules yourself, then materialize immediately and report the same plan summary minus the blocker section: contract + child list + handoff command. Don't pay for the full machine on a topic that doesn't need it.

## 1. Scope → freeze the contract

Grill only where the answer changes the decomposition. Generate the questions *this* topic raises — no fixed checklist — ask one at a time with a recommended answer, and answer anything the codebase can answer yourself (fan out an `Explore` agent) instead of asking the user. Refuse to proceed while success criteria, boundaries, or key terms are `TBD`.

Output is a short **contract** that goes verbatim into the tracker and binds every child:

- **Definition of done** — concrete: a passing test, a metric, a user-visible behavior.
- **Out of scope** — name the *nearest adjacent thing* an agent would wrongly pull in ("audit backups" means backups, not a dashboard cleanup). This is the anti-scope-invention fence.
- **Constraints** — stack, conventions, interfaces that must not change.
- **Repos in play** — one, or several. Multi-repo epics: each child names its repo, and `depends-on` only orders children within one repo's `/issue` batch — cross-repo dependencies must be expressed as separate handoff waves ("run repo-A children, then repo-B"), since `/issue` operates on one repo at a time.

## 2. Research (front-loaded, skip on trivial epics)

Fan out self-contained briefs in **one message** — concurrent `explore-mid` agents (Sonnet, read-only), or `Explore` for a cheap single lookup. Each brief states its objective, an output cap (≤600 words), and a stop condition; agents share no state. Scale lanes to the topic:

- **Codebase recon** (always) — what exists, reusable patterns, entry points, cross-process consumers, non-obvious tests, the blast radius of the likely change.
- **External landscape** (only if user-facing or the domain is genuinely unclear) — how others solve this. Skip for purely-internal work.

```bash
git log --oneline -20
gh issue list --state open --json number,title --limit 30   # related open work — NOT a label query
```

Read the digests. Spawn **one** targeted gap wave only if a real gap surfaced — never a third. Synthesize a tight brief: works / broken / missing / recommendation. This feeds the decomposition — and the relevant slices of it feed each child's Context stanza (§5), so the executor never re-pays for the recon.

Cache the brief to `/tmp/epic-plan/<slug>/research.md` (crash-recovery before materialize; nothing else reads it).

## 3. Decompose into a child DAG

**How to slice:**

- **Vertically by capability, never by layer** — each child is demoable end-to-end ("imports work for one format"), not a stratum ("the DB schema"). Layer-children can't ship independently.
- **Child 1 is the walking skeleton** — the thinnest end-to-end path through the whole idea; later children thicken it. Prevents "4 green children, epic still doesn't work".
- **Disjoint file sets are a design goal** — overlap is a smell: first re-cut the boundary; serialize via `depends-on` only when the overlap is real (shared config, a genuinely central file). Overlapping siblings left unordered is a decomposition failure — `/issue` will not order them for you.
- **Derive children from the contract's Done-list** — each Done criterion traces to exactly one child that proves it. Untraceable criterion = missing child; child proving no criterion = invented scope.
- **When torn between decompositions, cut by risk** — the child that could invalidate the plan goes first, so a re-plan costs one PR, not four.
- **Genuine unknowns become spike children** — a time-boxed investigation whose deliverable is a decision posted to the tracker, not code. A spike gates the children it de-risks via `depends-on`. Don't bury an experiment inside an implementation child.

Each child:

- **Independently shippable** — one `/resolve-issue` session, one focused PR that delivers something observable.
- **Right-sized** — heuristics that trigger a *look*, not hard rules: files-touched > ~15, LOC delta > ~1000, > ~10 large reads. The real signal is how many distinct decisions the child forces — that's what blows a session, not line count. A child that itself needs decomposing is a **sibling epic — surface it to the user**, never a silent sub-orchestrator. An epic pushing past ~8 children is probably two epics — field data says completion velocity collapses above that.
- Carries: **scope**, **machine-checkable acceptance criteria**, **context** (the recon facts this child needs), **`depends-on`** by ordinal, **files likely touched**, a one-word **risk** (`text-only` | `visual` | `shared-state`; default `shared-state` when unsure — it drives proof expectations), and its repo for multi-repo epics.

## 4. Adversarial review of the decomposition (the core; skip on trivial epics)

First, a 30-second schema pre-check yourself: every child has scope, AC, deps, files, risk, context filled. Don't spend the panel on missing fields.

Review the **decomposition, not code**. Fan out **`opus-worker` critics concurrently** (one message) on the same draft, each role-locked ("your job is to find flaws, not validate the plan"), none seeing another's output. Diverse lenses, never identical refuters:

| Lens | Hunts for |
|---|---|
| **Completeness** | A missing child, journey, or failure mode the contract implies. |
| **Dependency-ordering** | A child consuming what a later child produces; cycles; file-overlap that should serialize but doesn't. |
| **Scope / altitude / value** | Two-job children to split; over-decomposition to merge; invented scope to cut; a child that delivers nothing observable on its own. |
| **Feasibility & testability** | Is each child one-session-sized on evidence, not vibes? Is each AC a command or observation that can pass or fail as written? Vague AC detonates at execution. |
| **Premortem** | "This epic shipped and failed. Reconstruct exactly how." The blind spot the author can't see. |

Synthesize once — **no loops**:

1. Union the findings; dedup by area (highest severity wins).
2. Severity by **impact, not vote count**: a finding that invalidates the DAG (wrong ordering, missing child, unbuildable child) is a **blocker** even if only one lens raised it — the lenses are orthogonal by design, so real defects often live in exactly one lens's domain. Everything else is advisory.
3. **One re-check per blocker** (`opus-worker`): where the claim is checkable against the repo (does the file overlap exist? does the consumer actually consume?), the re-check MUST verify against the code, not argue rhetorically. Only genuinely unverifiable claims (premortem-style) get the framing "a prior reviewer concluded X; find the flaw in that reasoning." Upheld blockers stand; refuted ones drop to advisory. Skip advisories — verifying a nit costs more than the nit.
4. **Revise the decomposition once** against the upheld blockers. Advisories are nudges, not gates.

Cache upheld blockers + revised DAG to `/tmp/epic-plan/<slug>/review.md`.

## Plan report (shown alongside materialization — no approval gate)

Materialize immediately after the revision; do not wait for approval. Alongside (or right before) creating the issues, show the user plainly — never a vague "looks good":

- the **raw upheld-blocker list** and how each was resolved in the revision,
- the **advisories** (carried as nudges, not fixed),
- the **revised plan**: tracker contract + the child list with deps, risk, files, and repo,
- the **handoff command**.

If the user then asks for revisions, loop back to the named phase and re-materialize idempotently (edit existing issues in place — the markers make this safe). The exception that still stops for input: an unresolved contract ambiguity that a decomposition can't paper over (a genuine AskUserQuestion case from §1) — resolve that before creating issues.

## 5. Materialize (direct `gh`, idempotent)

Every create searches by a stable marker first and skips what exists — re-running never duplicates, so a mid-materialize crash is safe to re-run. **Never pair titles to bodies via shell array indexing** (zsh arrays are 1-indexed; this has produced title/body off-by-one in the field) — write each child's title and body-file explicitly, one create command per child.

**Labels** (create if absent; `--limit 999` so pagination doesn't fool the check):

```bash
gh label list --limit 999 --json name | grep -q '"epic"'        || gh label create epic --color 5319e7 --description "Epic tracker"
gh label list --limit 999 --json name | grep -q '"epic:<slug>"' || gh label create "epic:<slug>" --color a371f7 --description "Child of epic <slug>"
```

**Tracker** — idempotency marker is the HTML comment; dup-check by title under the `epic` label:

```bash
gh issue list --label epic --search "Epic: <topic> in:title" --json number,title   # exists? reuse its number, skip create
# else: write the tracker body (template below) to /tmp/epic-plan/<slug>/tracker.md, then:
gh issue create --label epic --title "Epic: <topic>" --body-file /tmp/epic-plan/<slug>/tracker.md
```

Tracker body — exactly this, no PRD bloat:

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

(Fill `## Children` after the children exist; back-edit the tracker with real numbers via `gh issue edit <tracker> --body-file ...`.)

**Children** — idempotency marker is the first body line. For each child *k*: write its body to `/tmp/epic-plan/<slug>/child-<k>.md`, search for the marker, create only if absent:

```bash
gh issue list --label "epic:<slug>" --search '"epic-plan:child slug=<slug> ord=<k>"' --json number   # present? skip
gh issue create --label "epic:<slug>" --title "<child title>" --body-file /tmp/epic-plan/<slug>/child-<k>.md
```

Child body:

```
<!-- epic-plan:child slug=<slug> ord=<k> -->
## Scope
<what this child does; one PR's worth>

## Context
<3–5 recon facts this child needs to start cold: the reusable pattern at path X,
the non-obvious test guarding Y, the consumer that breaks if Z changes.
From §2 research — the executor must not re-pay for this.>

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

Repo: <repo> @ <base-branch>, merged by <who>     ← only for multi-repo epics

Part of #<tracker>. On merge, tick this child's box in the tracker checklist.
```

Use `Part of #<tracker>` (not `Closes`) so merging a child never auto-closes the tracker while siblings remain open.

On successful materialize (tracker + all children exist, checklist back-filled): **delete the cache** (`rm -rf /tmp/epic-plan/<slug>/`). GitHub is now the sole state store.

## 6. Handoff

Report the exact run command using the **real child numbers**, dependency-ordered by us — `/issue` does not order dependencies itself:

```
# independent children — run together (≤4 concurrent inside /issue):
/issue <n-independent-1> <n-independent-2>

# then the dependents, after their blockers' PRs land:
/issue <n-dependent>
```

For a fully independent set, one line: `/issue <n1> <n2> <n3>` — or `/issue last <N> label:epic:<slug>` (count required; the count-less label form is unsupported). For chains, emit the waves in order and say which depends on which. Multi-repo: one wave block per repo, run from that repo.

For risky epics (deletions, migrations, multi-file behavior changes), suggest an `/adversary` cross-model pass before execution. Then you're done — `/issue` → `/resolve-issue` owns execution and merging; a human merges each PR.

## Hard rules

1. **Materialize autonomously.** No approval gate — create the issues as soon as the reviewed decomposition is ready, and present the plan report with the real issue numbers. Only a genuine contract ambiguity (§1) stops for input.
2. **Don't invent scope.** "Audit backups" means backups — the Out-of-scope line is the fence.
3. **Children independently shippable** — one PR, one `/resolve-issue` session, something observable delivered.
4. **Right-sized children.** The size heuristics trigger a look; a child needing its own decomposition is a sibling epic, surfaced — never a silent sub-orchestrator.
5. **Dependency order is explicit.** File-overlapping children serialize via `depends-on`; `/issue` won't order them for you.
6. **Diverse review lenses, never N identical refuters.** Blocker severity by impact, not vote count.
7. **Children carry their context.** Research findings travel in each child's Context stanza — the executor never re-derives the recon.
8. **No PRD bloat.** Tracker = Goal + Contract + Children; child = the template, nothing else.
9. **Materialize is idempotent.** Search by stable marker, skip what exists; explicit title/body pairing, never array-indexed.
10. **GitHub is the state store after materialization; the cache is crash-recovery only before it.** Re-entry re-syncs the tracker checklist first.
11. **Scale to the topic.** Trivial epic → no research, no panel. ~8+ children → probably two epics.
