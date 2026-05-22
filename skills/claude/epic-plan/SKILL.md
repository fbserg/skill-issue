---
name: epic-plan
description: Scope a feature, audit, or cleanup into a GitHub epic with child issues. Use when user invokes `/epic-plan "<topic>"` to turn an idea into a runnable epic. Pairs with `/epic-run` which executes the epic.
---

Turn a topic into a GitHub epic (tracking issue + child issues) ready for `/epic-run`.

**Required:** GitHub CLI (`gh`) authenticated. Subagent dispatch for Stage 3 external research.

## Stage 0 — Topic capture

User invokes `/epic-plan "<topic>"`. No questions yet. Record the topic.

## Stage 1 — Scoping grill

Ask **one question at a time** with a recommended answer. After each answer, decide whether the next question is still needed. Stop when decision branches are resolved.

Questions to draw from (ask only what matters for this topic):

- What does success look like, concretely? (passing test, metric, user-visible behavior)
  *Recommended: [state what the most obvious AC would be]*
- What's explicitly **out** of scope?
  *Recommended: [state the nearest adjacent thing an agent might add]*
- Which terms are ambiguous? Pin definitions now.
  *Recommended: [state the most natural interpretation]*
- What existing code/skill/tool already does some of this?
  *Recommended: [grep for it; if found, answer yourself instead of asking]*
- What's the failure mode if we ship the obvious version?
  *Recommended: [state the most likely way the happy path skips a hard case]*
- One epic or actually two?
  *Recommended: [state one if the goal is coherent; two if there are independent themes]*

**Codebase-answerable questions:** before asking, `grep` or `Explore` for the answer. If the codebase answers it, state the finding and move on — don't ask.

If the user says "you decide," state assumptions explicitly so they can be challenged.

## Stage 2 — Local research

After Stage 1: targeted research on the repo. Surface concise findings (works / broken / missing / dead).

```bash
git log --oneline -20
gh issue list --label epic-followups,epic-unfinished --state open --json number,title,body --limit 30
```

Walk relevant files, grep for affected symbols, check live state when the topic touches a live system (run the test suite, profile, check last cron run). Surface what's working, what's broken, and what's missing. Don't draft yet.

If >5 unaddressed followup/unfinished issues surface, propose a "grab-bag" epic (`/epic-plan "grab-bag: clean out followups"`).

## Stage 3 — External research

Fire three parallel agents on every epic. Three parallel searches cost ~5 minutes; missing a peer pattern costs a whole epic. Skip only for: pure typo/comment/version-bump, rollback of a specific commit, doc-only edit with no design choice in flight.

**Do not ask "research worth it?"** — that question reliably gets "no" and gets regretted.

Ground each agent with 3–10 bullets about our current codebase shape (file paths, key abstractions, constraints) from Stage 2's findings, then dispatch all three in a single message:

**Agent 1 — Direct competitors:** Who else solves this exact job for this exact user? Reddit/HN/forums for honest user voice. For each: deliverable, mechanism, pricing, target user, ahead-or-behind on which axes. Goal: leapfrog territory or catch-up?

**Agent 2 — Tech-stack peers:** Best-of-breed projects (open + commercial) using the same technical approach, even for a different deliverable. Identify 2–3 exemplars worth studying and 2–3 we're already ahead of. Cite specific patterns with repo paths, not vague categories.

**Agent 3 — GitHub deep search:** ~10–15 targeted `gh search code`/`gh search repos` queries. For top 10–15 hits: repo, stack, what they generate, relevant file structure with paths and line counts, multi-variant handling. Flag anything materially better than our approach.

After all three return, synthesize: where we sit (leapfrog/parity/catch-up), comparison table, ideas worth stealing (with source + refactor path), patterns to avoid, smallest next move.

If findings raise new ambiguities — competitor does X, parity / explicit non-goal / leapfrog? — proceed to Stage 4 to resolve them. Otherwise go to Stage 5.

## Stage 4 — Gap/scope grill

Ask **one question at a time** with a recommended answer. Draw from:

- For each "ideas worth stealing" finding: parity / explicit non-goal / leapfrog?
  *Recommended: [state the one that serves the user's stated goal]*
- Capability-gap probe: run the deliverable's hot path end-to-end against unmodified code with a hypothetical fixture. Whatever blocks it is a child, not "out of scope." What's blocking?
  *Recommended: [state what the most obvious blocker would be]*
- Skeleton-shipping smell: if every child's AC ships behind a skip-gate or feature flag, the epic isn't done — it's deferred. Is there a missing unblocker child?
  *Recommended: [name it if you see it, or say "no smell"]*
- Mini-epic check: if any child needs 3+ parallel workers, spans UI+backend+data, or changes a public API — stop and propose splitting.
  *Recommended: [split / don't split]*

Stop when scope is settled.

## Stage 5 — Draft the plan in chat

Numbered list. Each item: self-contained (one session), clear AC, files likely touched, deps on earlier items.

**Cross-child AC smell.** If A's AC bullet names a file/function B will create, re-phrase A's AC to "function is importable" or merge them.

**Risk tag.** Assign exactly one:
- `text-only`: docs, comments, prompts, config trims, mechanical renames.
- `visual`: UI, rendered documents, screenshots, or anything judged by sight.
- `shared-state`: DB, daemon behavior, schemas, auth, deploy paths, public APIs, cross-project artifacts, or anything where green local tests may miss risk.
Default to `shared-state` when uncertain.

**Epic-level demo AC (`## Demo` in epic body).** Single command + expected outcome the orchestrator runs after the last merge. Forces the plan to actually deliver, not just sum up children. After all children merge, the orchestrator runs this command on `origin/<DEFAULT_BRANCH>` HEAD; non-zero exit triggers `epic-tools revert <N>`.

**Size heuristic:** files-touched > ~15 OR LOC delta > ~1000 OR > ~10 large-file reads → split. One session = one focused PR.

**Surface walk (optional).** Spawn an `Explore` subagent to walk the affected surface when integration risk is unclear. Brief it with the draft shape; ask for entry points, cross-process consumers, live state, and non-obvious tests. Cap under 800 words. Skip when single-file or you already know the surface.

## Stage 6 — Confirmation grill

Ask **one question at a time** with a recommended answer:

- Should child N be split / merged with another?
  *Recommended: [state your judgment]*
- Is this ordering correct given file-overlap constraints?
  *Recommended: [state the right order]*
- Any child that's secretly a sibling epic?
  *Recommended: [name it if so, else "no"]*

Stop when user says "go."

**Do NOT create issues until user says go.**

## Stage 7 — Materialize epic

### Tracker (`gh issue create --label epic --title "Epic: <topic>"`)

```markdown
## Goal
<2-3 sentences>

## Risk
<text-only|visual|shared-state>

## Demo
<single end-to-end command + expected outcome — see Stage 5>

## Test command
<command-the-orchestrator-runs-as-Gate-A; default `pytest -q`>

## Children
<filled after children created>
```

### Child issue body

```markdown
## Scope
<1-3 sentences>

## Acceptance criteria
- <testable bullet>
- <testable bullet>

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

**Carry-overs.** If a child folds an open issue you expect to fall out incidentally, tag the line in `## Children` as `(carry-over, expected to resolve incidentally)`.

**Live-state mutators.** Phrase ACs as "verify the target state, migrating any non-conforming records."

After children created, edit tracker to fill `## Children` with `- [ ] #N — <title>` lines.

### Labels

If `epic` doesn't exist: `gh label create epic --color "5319e7" --description "Tracking issue for a multi-issue epic"`.
Topic-specific: `gh label list | grep epic:` for existing convention.

### Report

One line: The run command: `/epic-run <epic-num>` (or `/loop /epic-run <epic-num>` for unattended runs if your harness supports scheduled wakeups).

## Rules

- **Don't invent scope.** "Audit backups" means backups, not "and clean up the dashboard while we're here."
- **`## Out of scope` is a smell test.** Each bullet: would removing it break the deliverable? If yes, it's on the critical path — pull in.
- **Order matters.** File-overlapping items are sequential — note in `Depends on`.
- **No PRD ceremony.** Tracker stays lean; children carry scope, AC, out-of-scope.
- **The user runs `/epic-run` separately.** This skill ends when issues are created.
- **No silent sub-orchestrators.** Genuine sub-decomposition → escalate to a sibling epic.

## Labels

If `epic` doesn't exist: `gh label create epic --color "5319e7" --description "Tracking issue for a multi-issue epic"`.
Topic-specific: `gh label list | grep epic:` for existing convention. Create `epic:<slug>` if topic warrants and apply to tracker + every child.
