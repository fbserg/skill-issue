---
name: epic-plan
description: "Scope a multi-deliverable or multi-session topic into a GitHub tracker issue plus child issues. /epic-plan TOPIC or /epic-plan <tracker#> to resume. Not for one scoped change."
---

Turn a topic into one **tracker** issue plus **child** issues, each sized for
one `/resolve-issue` session. GitHub is the only state store. Write no code.

## Entry

- **Tracker number** → re-sync its checklist with live child states and report
  what shipped and what can run next. On a human correction, revise in place.
  When the last child lands, check the whole result against the tracker's Done
  line, then close it.
- **Topic, or a non-tracker issue as seed** → new epic with a short kebab `<slug>`.
- **Really one issue** → file it and hand off to `/resolve-issue <N>`.

## Plan

Research as much as the topic needs. Ask a question only when two readings give
different trackers. Then write:

- **Contract:** Done (concrete), Out of scope, Constraints, Repos.
- **Children:** vertical slices, each one PR and demoable. Every Done item maps
  to a child. Keep file sets disjoint where you can and mark real dependencies.

## Materialize

Create the issues with no approval gate. Reruns must not duplicate: make the
first body line `<!-- epic-plan:tracker slug=<slug> -->` or
`<!-- epic-plan:child slug=<slug> ord=<k> -->` and search for the exact marker
before each create. Use one explicit create per child. Labels `epic` and
`epic:<slug>`. Children say `Part of #<tracker>`, never `Closes`.

- Tracker: Goal, Contract, child checklist with deps.
- Child: Scope, a few context facts, acceptance criteria, deps, likely files.

## Handoff

Report the contract, the children, and run commands in dependency order:
`/blitz <independent…>` per wave, `/resolve-issue <N>` for single children. Then stop.

## Hard rules

1. **Materialize autonomously.** Only a real contract ambiguity stops for input.
2. **Don't invent scope.** "Audit backups" means backups — the Out-of-scope line is the fence.
3. **No PRD bloat.** Tracker = Goal + Contract + Children; child = the template, nothing else.
