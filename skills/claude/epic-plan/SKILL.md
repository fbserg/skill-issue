---
name: epic-plan
description: Scope a feature, audit, or cleanup into a GitHub epic with child issues. Use when user invokes /epic-plan TOPIC to turn an idea into a runnable epic. Pairs with /epic-run which executes the epic.
---

Turn a topic into a GitHub epic (tracking issue + child issues) ready for `/epic-run`.

**Required:** GitHub CLI (`gh`) authenticated.

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
- Should any child be split or merged with another? (ask after seeing the draft)
  *Recommended: [state your judgment]*
- Is the ordering correct given file-overlap constraints? (ask after seeing the draft)
  *Recommended: [state the right order]*
- Any child that's secretly a sibling epic? (ask after seeing the draft)
  *Recommended: [name it if so, else "no"]*

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

## Stage 3 — External research (optional)

If the landscape is unclear and this affects a user-facing surface, suggest `/epic-research <topic>` before drafting. Otherwise proceed directly to Stage 4.

## Stage 4 — Draft the plan in chat

Use the canonical plan-file format so the output is directly usable with `epic-tools plan-to-epic`:

```
## Child N — <title>

### Scope
<1-3 sentences>

### Acceptance criteria
- <testable bullet>

### Depends on
Child M  <!-- ordinal ref; "none" if no deps -->

### Files likely touched
- path/to/file.py

### Risk
<text-only|visual|shared-state>
```

Each child: self-contained (one session), clear AC, files likely touched. For deps, use the `### Depends on` subsection with ordinal refs (`Child 1`, `Child 2`, etc.) — **never bold inline text** like `**Depends on:** #1`. The parser requires the section header.

**Risk tag.** Assign exactly one:
- `text-only`: docs, comments, prompts, config trims, mechanical renames.
- `visual`: UI, rendered documents, screenshots, or anything judged by sight.
- `shared-state`: DB, daemon behavior, schemas, auth, deploy paths, public APIs, cross-project artifacts, or anything where green local tests may miss risk.
Default to `shared-state` when uncertain.

For shared-state or visual work, include proof expectations in the relevant child
issues. `/epic-run` relies on per-PR verification and CI in normal mode; it does
not run an extra epic-level demo gate after the last merge.

**Size heuristic:** files-touched > ~15 OR LOC delta > ~1000 OR > ~10 large-file reads → split. One session = one focused PR.

**Surface walk (optional).** Spawn an `Explore` subagent to walk the affected surface when integration risk is unclear. Brief it with the draft shape; ask for entry points, cross-process consumers, live state, and non-obvious tests. Cap under 800 words. Skip when single-file or you already know the surface.

## Stage 5 — Materialize epic

### Tracker (`gh issue create --label epic --title "Epic: <topic>"`)

```markdown
## Goal
<2-3 sentences>

## Risk
<text-only|visual|shared-state>

## Children
<filled after children created>
```

### Child issue body

```markdown
## Scope
<1-3 sentences>

**Risk:** <text-only|visual|shared-state>

## Acceptance criteria
- <testable bullet>

## Proof
<Required for visual/shared-state work; omit for text-only.
Visual: screenshot/GIF showing the rendered change.
Shared-state: before/after route, table row, transcript, or other artifact
proving the affected surface behaves correctly.>

## Files likely touched
- path/to/file.py

## Depends on
#<other-child-num>  <!-- omit if no deps -->

Part of #<epic-num>
```

**Live-state mutators.** Phrase ACs as "verify the target state, migrating any non-conforming records."

After children created, edit tracker to fill `## Children` with `- [ ] #N — <title>` lines.

### Labels

If `epic` doesn't exist: `gh label create epic --color "5319e7" --description "Tracking issue for a multi-issue epic"`.
Topic-specific: `gh label list | grep epic:` for existing convention. Create `epic:<slug>` if topic warrants and apply to tracker + every child.

### Report

One line: The run command: `/epic-run <epic-num>` (or `/loop /epic-run <epic-num>` for unattended runs if your harness supports scheduled wakeups).

## Rules

- **Don't invent scope.** "Audit backups" means backups, not "and clean up the dashboard while we're here."
- **Order matters.** File-overlapping items are sequential — note in `Depends on`.
- **No PRD ceremony.** Tracker stays lean; children carry scope, AC, out-of-scope.
- **The user runs `/epic-run` separately.** This skill ends when issues are created.
- **No silent sub-orchestrators.** Genuine sub-decomposition → escalate to a sibling epic.

**Do NOT create issues until user says go.**
