# Schema reference

Labels, branch names, and PR title conventions used by the epic workflow.

## Labels

| Label | Created by | Meaning |
|---|---|---|
| `epic` | `epic-plan` | Tracking issue for a multi-issue epic |
| `epic-<N>` | `epic-run` / `epic-tools pr-create` | Applied to every child PR of epic N |
| `epic-<N>-running` | `epic-run` orchestrator | Run lock — epic is currently being executed |
| `epic-<N>-failed` | `epic-run` orchestrator | Child issue or PR failed and needs attention |
| `epic-<N>-ci-retried` | `epic-run` orchestrator | CI was flaky; one retry was attempted |
| `epic-followups` | manual / `epic-retro` | Follow-up issues filed during or after an epic |
| `epic-unfinished` | manual / `epic-retro` | Partial ACs filed mid-epic |

## Branch names

| Pattern | Created by | Meaning |
|---|---|---|
| `epic-<N>-<child>-<slug>-<suffix>` | child agent | Child issue work branch |
| `worktree-agent-<suffix>` | orchestrator | Orchestrator worktree branch |
| `revert-epic-<N>-<suffix>` | `epic-tools revert` | Revert PR branch |

Where:
- `<N>` is the epic issue number
- `<child>` is the child issue number
- `<slug>` is a short kebab-case descriptor from the issue title
- `<suffix>` is 8 hex chars from `openssl rand -hex 4`

## PR titles

Child PR titles follow the format: `<prefix>: <title> (#<child>)` where prefix is `chore|test|fix|feat|perf|refactor`.

Epic issue title format: `Epic: <topic>`

## `epic-tools` completion audit

When telemetry is enabled, each child completion emits a marker line:

```
EPIC_RUN_USAGE run_id=<suffix> epic=<N> child=<child>
```

This is appended to a local audit file and ingested by `epic-tools usage-ingest-*`. Token counts are optional best-effort extras; rows without token counts are valid.

## Issue body sections

### Epic tracker
- `## Goal` — 2–3 sentence description
- `## Risk` — `text-only` | `visual` | `shared-state`
- `## Demo` — single end-to-end command + expected outcome (Claude version only)
- `## Test command` — command the orchestrator runs as a gate
- `## Children` — `- [ ] #N — <title>` checklist

### Child issue
- `## Scope` — 1–3 sentences
- `## Acceptance criteria` — testable bullets
- `## Proof` — screenshot/artifact (required for visual/shared-state)
- `## Out of scope` — adjacent temptations
- `## Files likely touched` — file paths
- `## Prior art` — existing helpers (optional)
- `## Sibling repo` — cross-repo info (required when applicable)
- `## Depends on` — `#<issue>` (optional)
- `Part of #<epic-num>` — closes-relationship
