---
name: epic-plan
description: Scope a feature, audit, or cleanup into a GitHub epic with child issues. Use when user invokes `/epic-plan "<topic>"` to turn an idea into a runnable epic. Pairs with `/epic-run` which executes the epic.
---

Turn a topic into a GitHub epic (tracking issue + child issues) ready for `/epic-run`. Stops: after step 0 (wait for round-1 answers), after step 3 (wait for "go").

## 0. Round 1 — shape the problem

Ask 3–5 sharp scoping questions before any research or scaffolding. Pick the ones that matter for *this* topic:

- What does success look like, concretely? (passing test, metric, user-visible behavior)
- What's explicitly **out** of scope?
- Which terms are ambiguous? Pin definitions now.
- What existing code/skill/tool already does some of this?
- What's the failure mode if we ship the obvious version?
- One epic or actually two?

**Stop. Wait for answers.** If the user says "you decide," state assumptions explicitly so they can be challenged.

## 0a. Research → round 2 → loop

After round-1 answers: targeted research (git log/grep, read relevant files, check current state). Surface concise findings (works/broken/missing/dead). Then ask round-2 follow-ups the research surfaced — integration seams, dead-code disposition, data-model gaps, surface-by-surface differences, fixture sharing, scope of "all". Loop research↔questions until ambiguities resolved. **Don't draft yet.**

## 0b. Scan prior followups

```bash
gh issue list --label epic-followups,epic-unfinished --state open --json number,title,body --limit 30
```

Surface bullets relevant to this topic and ask: fold-in / drop / leave. If >5 are sitting unaddressed, propose a "grab-bag" epic (`/epic-plan "grab-bag: clean out followups"`).

## 0c. External landscape — DEFAULT ON

**Fire `epic-research` (steps 1–3) on every epic.** Three parallel agents cost ~5 minutes; missing a peer pattern that obviates the work costs a whole epic. The default-on stance is deliberate — most "this is too small for research" calls turn out wrong in retrospect, and a five-minute "we're already ahead" is a perfectly fine result.

**Narrow opt-out.** Skip ONLY when the epic is:
- A pure typo / comment / version-bump (no code logic touched)
- A rollback of a specific commit ("revert #123")
- A doc-only edit with no design choice in flight

Everything else — bug fix, refactor, test cleanup, "internal" change, mechanical rename, "obvious" fix — gets research. Peer projects almost always exist (testing patterns, error handling, build pipelines, migration shims). If you're 90% sure no peer exists, fire the agents anyway — five minutes confirms it cheaply and the 10% case has bitten before.

**Do not ask the user "research worth it?"** — that question reliably gets "no" and gets regretted. The bar is the opt-out list above, not user permission. If the user explicitly says "skip research," fine — but don't pre-pitch the opt-out.

When fired: follow `epic-research` steps 1–3 (ground in our code using 0a's findings, dispatch three agents in parallel, synthesize). **Skip epic-research's step 4 handoff** — synthesis flows directly back into this skill as prior art for child issues (step 4's `## Prior art` block).

After synthesis, if findings raise new ambiguities — competitor does X, parity / explicit non-goal / leapfrog? — do **round 3** questions. Otherwise proceed to step 1.

## 1. Pre-draft checks

**Measure live state, don't just read.** If the topic is about a live system: actually run the suite / profile / check the last cron run / run the dep analyzer. Reading code alone misses live state.

**Capability-gap probe (CRITICAL).** Run the deliverable's hot path end-to-end against unmodified code with a hypothetical fixture and report what fails. If the epic's outcome is "X test runs green," literally try to write that test against current main, even as 5 dummy lines. Whatever blocks it is a *child*, not "out of scope, file follow-up." Test: imagine pasting `gh pr merge --squash` on the last child and immediately running the deliverable's command. If you can't see it working — what's missing is a missing child.

**Skeleton-shipping smell.** If every child's AC will ship behind a skip-gate, feature flag, or `pytest.skip("blocked on #N")`, the epic isn't done — it's deferred. Pull the unblocker in, or pause the epic.

**Mini-epic check.** If any child needs 3+ parallel workers, spans UI+backend+data, requires migration+shim+cleanup phases, or changes a public API — stop and propose splitting it into its own sibling epic.

**Cross-repo check.** Any child touching a sibling project (paths outside this repo, sibling-path imports, branches that land on a different remote) needs a `## Sibling repo` block (template in step 4) — the orchestrator can't auto-merge a remote it doesn't own.

## 1a. Surface walk (optional — fire when integration risk is unclear)

Spawn an `Explore` subagent to walk the affected surface end-to-end. Brief it with your draft shape; ask for a tight bulleted dossier covering entry points, cross-process consumers, live state, and non-obvious tests. Demand `file:line` refs, cap under 800 words. Fold findings back into children.

Skip when single-file or you already know the surface.

## 2. Draft the plan in chat

Numbered list. Each item: self-contained (one session), clear AC, files likely touched, deps on earlier items.

**Cross-child AC smell.** If A's AC bullet names a file/function B will create, the boundary is wrong — re-phrase A's AC to "function is importable" or merge them.

**Epic-level demo AC (`## Demo` in epic body, not children).** Single command + expected outcome the orchestrator runs after the last merge. Example: "After all children merge, `pytest -m slow tests/test_canonical_plan_visual.py` exits 0 and produces `tests/.regen/canonical.png` matching the committed baseline." Forces the plan to actually deliver, not just sum up children whose ACs `partial` cleanly. After all children merge, the orchestrator runs this command on `origin/<DEFAULT_BRANCH>` HEAD; non-zero exit triggers `epic-tools revert <N>`.

**Size heuristic:** Files-touched > ~15 OR LOC delta > ~1000 OR > ~10 large-file reads → split. One session = one focused PR. Compacted context = lost decisions.

## 3. Iterate with user

Add, drop, reorder. Stop and ask if scope is unclear. **Do NOT create issues until user says go.**

## 4. Create epic + child issues

**Tracker** (`gh issue create --label epic --title "Epic: <topic>"`):

```markdown
## Goal
<2-3 sentences>

## Demo
<single end-to-end command + expected outcome — see step 2>

## Test command
<command-the-orchestrator-runs-as-Gate-A; default `pytest -q`>

## Children
<filled after children created>
```

**Child issue body:**

```markdown
## Scope
<1-3 sentences>

## Acceptance criteria
- <testable bullet>
- <testable bullet>
<!-- Prefer "section/field equivalence" over "byte-identical" / sha256 for refactors
     of file-producing code. Whitespace, key ordering, and embedded timestamps drift
     even when behavior is identical, so byte-equality fails spuriously and pushes
     verifiers to weaken the assertion under pressure. -->

## Proof
<REQUIRED for visual/shared-state, OMIT for text-only.
 Visual: screenshot/GIF. Shared-state: before/after of the affected route, table row,
 or transcript proving the surface behaves correctly.>

## Out of scope
- <thing an agent might be tempted to also do but shouldn't>

## Files likely touched
- path/to/file.py

## Prior art
<existing helper, pattern, sibling issue worth checking before inventing — omit if none>

## Sibling repo
<REQUIRED if child touches a sibling project. State:
 - which repo (path on disk + remote)
 - branch convention to push to
 - who merges (this agent | follow-up child | human)
 If "this agent" — add an AC bullet requiring the sibling-repo PR opened AND merged.
 Pushed branch is not done. -->

## Depends on
#<other-child-num>  <!-- omit if no deps -->

Part of #<epic-num>
```

**Carry-overs.** If a child folds an open issue you expect to fall out incidentally (existing bug the refactor moots), tag the line in `## Children` as `(carry-over, expected to resolve incidentally)` — close report distinguishes "shipped" vs "fell out."

**Live-state mutators.** Phrase ACs as "verify the target state, migrating any non-conforming records." A dry-run with zero records is then a valid PASS — concurrent producers often render the migration a no-op.

After children created, edit tracker to fill `## Children` with `- [ ] #N — <title>` lines.

## 5. Report

One line. The run command: `/loop /epic-run <epic-num>` (self-paced loop — orchestrator ticks every ~20 min, drives epic to merged + post-merge gates without further input).

## Rules

- **Don't invent scope.** "Audit backups" means backups, not "and clean up the dashboard while we're here."
- **`## Out of scope` is a smell test.** Each bullet: would removing it break the deliverable? If yes, it's on the critical path — pull in. Out-of-scope = adjacent things the agent might be tempted to also do, not load-bearing prerequisites.
- **Order matters.** File-overlapping items are sequential — note in `Depends on`.
- **No PRD ceremony.** Tracker stays lean (Goal + Demo + Test command + Children); children carry scope, AC, out-of-scope.
- **The user runs `/epic-run` separately.** This skill ends when issues are created.
- **No silent sub-orchestrators.** Genuine sub-decomposition → escalate to a sibling epic.

## Labels

If `epic` doesn't exist: `gh label create epic --color "5319e7" --description "Tracking issue for a multi-issue epic"`.
Topic-specific: `gh label list | grep epic:` for existing convention. Create `epic:<slug>` if topic warrants and apply to tracker + every child.
