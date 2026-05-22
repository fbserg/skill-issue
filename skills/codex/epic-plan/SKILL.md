---
name: epic-plan
description: Scope a feature, audit, cleanup, or multi-step repo change into a lean GitHub epic with child issues. Use when the user invokes $epic-plan, asks to plan an epic, or wants an idea decomposed into runnable GitHub issues for later execution by $epic-run.
---

# Epic Plan

Turn an idea into a GitHub tracking issue plus small child issues that a future
Codex runner can execute.

## Workflow

1. Shape the problem before planning.
   Ask 3-5 sharp questions that matter for this topic, then stop for answers
   unless the user explicitly told you to decide. Pin success criteria,
   exclusions, ambiguous terms, existing related code, likely failure mode, and
   whether the request is really one epic or several.

2. Research the current state.
   After round-one answers, inspect relevant files, history, tests, maps, CI,
   or live state. Measure when the topic depends on reality: run tests for test
   epics, profile for performance epics, inspect cron/backup status for ops
   epics, and so on. If target repo Actions are disabled, plan for explicit
   local proof because `$epic-run manual-merge` will not have CI. Surface
   concise findings before drafting.

3. Ask round-two questions only if research exposed real ambiguity.
   Focus on integration points, old behavior, data-model gaps, edge cases,
   deployment hooks, and what "all" means. Do not draft while important scope
   remains unresolved.

4. Assign exactly one risk tag:
   - `text-only`: docs, comments, prompts, config trims, mechanical renames.
   - `visual`: UI, rendered documents, screenshots, or anything judged by sight.
   - `shared-state`: DB, daemon behavior, schemas, auth, deploy paths, public APIs,
     cross-project artifacts, or anything where green local tests may miss risk.
   Default to `shared-state` when uncertain.

5. Check whether the epic shape is too large.
   Default to one runnable epic with 3-5 implementation children. Six or seven
   children is acceptable after checking sequencing risk. If the plan wants 8+
   children, multiple themes, or multiple independent workstreams, make a
   shallow parent epic whose children are smaller runnable epics. Do not nest
   deeper than parent epic -> runnable epic -> child issue.

6. Check whether any child is too large.
   Escalate to a sibling epic instead of creating a giant child when an item
   spans UI plus backend plus data, requires migration plus compatibility plus
   cleanup, changes shared architecture, needs 3+ parallel workers, or cannot
   fit in one Codex context window.

7. Draft the plan in chat.
   Use numbered work items. Each item must be self-contained, have testable
   acceptance criteria, name likely touched files, and list dependencies. Split
   an item if likely touched files exceed about 15, the change looks over about
   1000 LOC, or it would require reading more than about 10 large files.

   If GitHub writes are blocked because the agent is in Plan Mode, the final
   `<proposed_plan>` is the handoff artifact. Include GitHub-ready tracker and
   child issue bodies directly in the plan. Child bodies must preserve the
   research context a fresh/weaker runner would otherwise lose: discovered repo
   facts, relevant files, existing helpers/patterns, implementation approach,
   edge cases, dependencies, acceptance criteria, proof commands, and explicit
   out-of-scope boundaries. Do not rely on hidden transcript context.

8. Iterate with the user.
   Add, drop, split, or reorder. Do not create issues until the user explicitly
   says to proceed.

9. Create GitHub issues with `gh`.
   Create the tracker first, then children, then backfill the tracker's child
   checklist once child numbers are known.

## Tracker Template

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

## Child Template

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
