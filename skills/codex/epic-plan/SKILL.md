---
name: epic-plan
description: Scope a feature, audit, cleanup, or multi-step repo change into a lean GitHub epic with child issues. Use when the user invokes $epic-plan, asks to plan an epic, or wants an idea decomposed into runnable GitHub issues for later execution by $epic-run.
---

# Epic Plan

Turn an idea into a GitHub tracking issue plus small child issues that a future
Codex runner can execute.

## Stage 0 — Topic capture

User invokes `$epic-plan "<topic>"`. No questions yet. Record the topic.

## Stage 1 — Scoping grill

Ask **one question at a time** with a recommended answer. After each answer, decide whether the next question is still needed. Stop when decision branches are resolved.

Questions to draw from (ask only what matters for this topic):

- What does success look like, concretely? (passing test, metric, user-visible behavior)
  *Recommended: [state the most obvious AC]*
- What's explicitly out of scope?
  *Recommended: [state the nearest adjacent thing a worker might add]*
- Which terms are ambiguous? Pin definitions now.
  *Recommended: [state the most natural interpretation]*
- What existing code/skill/tool already does some of this?
  *Recommended: [grep for it; if found, answer yourself instead of asking]*
- What's the failure mode if we ship the obvious version?
  *Recommended: [state the most likely way the happy path skips a hard case]*
- One epic or actually two?
  *Recommended: [one if goal is coherent; two if there are independent themes]*

**Codebase-answerable questions:** before asking, grep or read for the answer. If the codebase answers it, state the finding and move on — don't ask.

If the user says "you decide," state assumptions explicitly so they can be challenged.

## Stage 2 — Local research

After Stage 1: inspect relevant files, history, tests, CI, or live state. Measure when the topic depends on reality: run tests for test epics, profile for performance epics, inspect cron/backup status for ops epics. Surface concise findings before drafting.

If target repo Actions are disabled, plan for explicit local proof because `$epic-run manual-merge` will not have CI.

```bash
git log --oneline -20
gh issue list --label epic-followups,epic-unfinished --state open --json number,title,body --limit 30
```

If >5 unaddressed followup/unfinished issues surface, propose a "grab-bag" epic.

## Stage 3 — External research

Fire three parallel agents on every epic. Three searches cost ~5 minutes; missing a peer pattern costs a whole epic. Skip only for: pure typo/comment/version-bump, rollback of a specific commit, doc-only edit with no design choice in flight.

**Do not ask "research worth it?"** — that question reliably gets "no" and gets regretted.

Ground each agent with 3–10 bullets about the current codebase shape from Stage 2's findings, then spawn all three in a single dispatch:

**Agent 1 — Direct competitors:** Who else solves this exact job for this exact user? For each: deliverable, mechanism, target user, ahead-or-behind on which axes.

**Agent 2 — Tech-stack peers:** Best-of-breed projects using the same technical approach. Identify 2–3 exemplars worth studying. Cite specific patterns with repo paths.

**Agent 3 — GitHub deep search:** ~10–15 targeted searches. For top hits: repo, stack, relevant file structure. Flag anything materially better than our approach.

After all three return, synthesize: where we sit, ideas worth stealing (with refactor path on our side), patterns to avoid, smallest next move.

If findings raise new ambiguities, proceed to Stage 4. Otherwise go to Stage 5.

## Stage 4 — Gap/scope grill

Ask **one question at a time** with a recommended answer:

- For each "ideas worth stealing": parity / explicit non-goal / leapfrog?
  *Recommended: [state the one that serves the user's stated goal]*
- Capability-gap probe: run the deliverable's hot path end-to-end against unmodified code with a hypothetical fixture. Whatever blocks it is a child, not "out of scope."
  *Recommended: [state what the most obvious blocker would be]*
- Skeleton-shipping smell: if every child's AC ships behind a skip-gate, there's a missing unblocker child.
  *Recommended: [name it if you see it, or say "no smell"]*
- Mini-epic check: if any child needs 3+ parallel workers or spans multiple independent workstreams, propose splitting.
  *Recommended: [split / don't split]*

Stop when scope is settled.

## Stage 5 — Draft the plan in chat

Numbered work items. Each item must be self-contained, have testable acceptance criteria, name likely touched files, and list dependencies.

**Risk tag.** Assign exactly one:
- `text-only`: docs, comments, prompts, config trims, mechanical renames.
- `visual`: UI, rendered documents, screenshots, or anything judged by sight.
- `shared-state`: DB, daemon behavior, schemas, auth, deploy paths, public APIs, or anything where green local tests may miss risk.
Default to `shared-state` when uncertain.

Split an item if likely touched files exceed about 15, the change looks over about 1000 LOC, or it would require reading more than about 10 large files.

If GitHub writes are blocked because the agent is in Plan Mode, the final `<proposed_plan>` is the handoff artifact. Include GitHub-ready tracker and child issue bodies directly in the plan. Child bodies must preserve the research context a fresh/weaker runner would otherwise lose.

## Stage 6 — Confirmation grill

Ask **one question at a time** with a recommended answer:

- Should child N be split / merged?
  *Recommended: [state your judgment]*
- Is this ordering correct given file-overlap constraints?
  *Recommended: [state the right order]*
- Any child that's secretly a sibling epic?
  *Recommended: [name it if so, else "no"]*

Stop when user explicitly says to proceed. **Do not create issues until then.**

## Stage 7 — Materialize epic

Create the tracker first, then children, then backfill the tracker's child checklist once child numbers are known.

### Tracker template

```markdown
## Goal
<2-3 sentences>

## Risk
<text-only|visual|shared-state>

## Children
- [ ] #N - <title>

## Plan
- <one line per child>
```

Use title `Epic: <topic>` and label `epic`. Create the label if missing:

```bash
gh label create epic --color "5319e7" --description "Tracking issue for a multi-issue epic"
```

### Child template

```markdown
## Scope
<what this issue does, 1-3 sentences>

## Acceptance criteria
- <testable bullet>
- <testable bullet>

## Proof
<Required for visual/shared-state epics; omit for text-only.
Visual: screenshot/GIF showing the rendered change.
Shared-state: before/after route, table row, transcript, or other artifact
proving the affected surface behaves correctly.>

## Out of scope
- <thing an agent may be tempted to also do but should not>

## Files likely touched
- path/to/file.py

## Prior art
<existing helper, pattern, sibling issue, or omit section if none>

## Depends on
#<other-child-num>

Part of #<epic-num>
```

## Rules

- Keep the tracker lean. Put operational detail in child issues.
- In Plan Mode, make child issues exhaustive enough that the next context can
  create and run the epic without rediscovering the planning research.
- Parent/program epics are only lightweight checklists of runnable epics plus
  dependencies and a done condition. Do not put implementation detail there.
- Keep runnable epics small: prefer 3-5 child issues; tolerate 6-7 with clear
  ordering; split 8+ direct children into a parent epic.
- Preserve ordering. Items with file overlap or logical dependency must be
  sequential and named in `## Depends on`.
- Do not invent adjacent cleanup. Scope follows the user's goal.
- Use topic labels only when they add value. Check `gh label list` for existing
  `epic:<slug>` conventions before creating one.
- End with one line: `Run with: $epic-run <epic-num> with Codex workers`.
  If repo Actions are disabled, use:
  `Run with: $epic-run <epic-num> manual-merge with Codex workers`.
- If GitHub writes were blocked by Plan Mode, end instead with:
  `After exiting Plan Mode: create the tracker and child issues exactly from this plan, then run: $epic-run <epic-num> with Codex workers`.
  If repo Actions are disabled, use:
  `After exiting Plan Mode: create the tracker and child issues exactly from this plan, then run: $epic-run <epic-num> manual-merge with Codex workers`.
