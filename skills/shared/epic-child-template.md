# Epic child issue template

Shared template used by both Claude and Codex epic-plan skills.

```markdown
## Scope
<what this issue does, 1-3 sentences>

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
 - who merges (this agent | follow-up child | human)>

## Depends on
#<other-child-num>  <!-- omit if no deps -->

Part of #<epic-num>
```
