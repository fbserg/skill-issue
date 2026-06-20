---
name: epic-plan
description: Scope a feature, audit, or cleanup into a GitHub epic of child issues that execute via /issue → /resolve-issue. Front-loads wide parallel research, runs a multi-lens adversarial review of the decomposition before anything is created, and re-enters from GitHub state. Use when the user invokes /epic-plan TOPIC, or when a task is too big for one issue — multiple deliverables or multiple sessions. Not for a single issue (use /issue) or a one-PR change (use /resolve-issue).
---

Turn a topic into a GitHub epic: a tracking issue plus child issues, each sized for one
`/resolve-issue` session. The value is in the research and the review — not the paperwork. Spend
tokens up front, lock the guardrails, then let `/issue` execute. **Do not create any issue until the
user says go.**

The expensive judgment is front-loaded on purpose: research and a decomposition review are the
cheapest place to be wrong. Cheaper, faster models execute the children later, inside the guardrails
this skill freezes into the epic.

## Roles

- **Research** → concurrent `explore-mid` agents (one message, several `Agent` calls).
- **Plan review** → concurrent `opus-worker` critics. Opus judges, Sonnet builds.
- A Workflow may stand in for the fan-outs if available — not required; concurrent `Agent` calls are
  the baseline.

## Re-entry gate

GitHub is the checkpoint store; this skill keeps no local ledger. On invocation:

- **Given an existing epic number** (`/epic-plan 47`, or a tracker URL) → read the tracker body,
  labels, and comments. Resume from the recorded phase: each phase posts a tracker comment tagged
  `<!-- epic-plan: <phase> -->`. A human comment or a `needs-revision` label is a loop-back signal —
  re-enter at the phase it targets (usually research or review), don't restart.
- **Given a topic** → new epic. Continue below.
- **The topic is really one issue** (single deliverable, one session) → stop and hand to `/issue`.
- **Trivially small epic** (2–3 obvious children, no unknowns) → skip Phases 2 and 4; grill briefly,
  decompose, materialize.

## Phase 1 — Scope and lock the contract

Grill only where it changes the decomposition. Generate the questions the topic actually raises — no
fixed checklist — and ask one at a time with a recommended answer. Answer anything the codebase can
answer (fan out an `Explore` agent) instead of asking.

Refuse to proceed on vague scope. If success criteria, boundaries, or key terms are still `TBD`, pin
them now. The output of this phase is a short **contract** — the non-negotiables that constrain every
child:

- **Definition of done** — concretely (passing test, metric, user-visible behavior).
- **Out of scope** — name the nearest adjacent thing an agent would wrongly pull in.
- **Constraints** — stack, conventions, interfaces that must not change.

This contract goes verbatim into the tracker body so executors inherit it.

## Phase 2 — Wide research (front-loaded)

Fan out self-contained research briefs in one message. Each brief states its objective, allowed tools,
an output cap (≤600 words), and a stop condition — agents share no state. Default lanes, scaled to the
topic (drop or add as warranted):

- **Codebase recon** — what already exists, reusable patterns, entry points, cross-process consumers,
  non-obvious tests.
- **Repo history / prior art** — closed epics, `epic-followups` / `epic-unfinished` issues, related
  skills, where the repo is heading.
- **External landscape** — how others solve this (web). Only when the surface is user-facing or the
  domain is unclear.

```bash
git log --oneline -20
gh issue list --label epic-followups,epic-unfinished --state open --json number,title,body --limit 30
```

Read the digests; spawn **one** targeted gap wave only if a real gap surfaced. Synthesize a tight brief:
works / broken / missing / prior-art / recommendation. If >5 stale followup/unfinished issues surface,
offer a grab-bag epic instead.

## Phase 3 — Decompose into a child DAG

Draft the children as a dependency graph. Each child:

- Self-contained, one `/resolve-issue` session, one focused PR.
- Carries scope, **machine-checkable** acceptance criteria, `depends-on` (by ordinal: `Child 2`),
  files likely touched, and a one-word risk (`text-only` | `visual` | `shared-state`; default
  `shared-state` when unsure — it drives proof expectations downstream).
- Sized to fit: files-touched > ~15, LOC delta > ~1000, or >~10 large reads → split.

Order matters: file-overlapping children are sequential — encode it in `depends-on`. A child that needs
its own decomposition is a sibling epic, not a silent sub-orchestrator — surface it.

## Phase 4 — Multi-lens plan review (the core)

Review the **decomposition**, not code. Fan out four critics concurrently, each on the *same* draft,
each role-locked ("your job is to find flaws, not validate"), none seeing another's output — diverse
lenses, never four identical refuters:

| Lens | Hunts for |
|---|---|
| **Completeness** | Missing journey, failure mode, or child the contract implies. |
| **Dependency-ordering** | A child consuming an artifact a later child produces; cycles; file-overlap that should serialize. |
| **Scope / altitude** | Two-job children to split; over-decomposition to merge; invented scope to cut. |
| **Premortem** | "This epic shipped and failed. Reconstruct exactly how." The failure the author can't see. |

Synthesize in one pass — no loops:

1. Collect the union of findings; dedup by area.
2. Flagged by **2+ lenses → blocker**; by one → advisory.
3. **One skeptic re-check per blocker** (`opus-worker`): "Critic claims X. Is it real? Show evidence."
   Upheld blockers stand; refuted ones drop to advisory.
4. Revise the decomposition once against the upheld blockers (advisories are nudges).

Show the user the raw upheld-blocker list, the advisories, and the revised plan. Never a vague "looks
good." This is the gate the user approves.

## Phase 5 — Materialize (direct `gh`, idempotent)

Only after the user says go. Re-runnable without duplicating: before creating anything, search for an
existing tracker/child by a stable marker and skip what already exists.

- **Tracker** — `gh issue create --label epic --title "Epic: <topic>"`. Body carries `## Goal`, the
  frozen `## Contract` (done / out-of-scope / constraints), and a `## Children` checklist filled after
  the children exist.
- **Children** — one issue each, labeled `epic:<slug>` (create the label if absent). Body: scope,
  machine-checkable acceptance, `Depends on #N`, files likely touched, and **proof expectations** for
  `visual`/`shared-state` work (screenshot/GIF, or before/after artifact). End each with `Part of #<tracker>`.
- Each materialize step posts a tracker comment tagged `<!-- epic-plan: materialize -->` so a resumed
  run knows it ran.

Labels: `gh label create epic --color 5319e7 ...` if missing; `gh label list | grep epic:` for the
slug convention.

## Phase 6 — Handoff

Report one run command:

```
/issue label:epic:<slug>          # batch-execute all children
```

`/issue` runs ≤4 children concurrently and does **not** dependency-order, so for a chain, run the
blocker children first, then the dependents (`/issue <n1> <n2>`). For risky epics (deletions,
migrations, multi-file behavior changes), suggest an `/adversary` cross-model pass before execution.
This skill ends here — `/issue` → `/resolve-issue` owns execution and merging.

## Hard rules

- **Don't invent scope.** "Audit backups" means backups, not a dashboard cleanup along the way.
- **Order matters.** File-overlapping children are sequential — say so in `depends-on`.
- **No PRD bloat.** The tracker carries Goal + Contract; children carry scope + AC. Nothing else.
- **No silent sub-orchestrators.** A child that needs decomposing is a sibling epic — surface it.
- **Diverse lenses, never N identical refuters** — same-prompt panels converge and add nothing.
- **GitHub state is the checkpoint.** Resumable from tracker body + labels + tagged comments; no local ledger.
- **Don't create issues until the user says go.**
