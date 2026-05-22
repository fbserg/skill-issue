---
name: epic-retro
description: Mine closed epics into skill improvements. Invoke with /epic-retro [N].
---

The retrospective for the retrospectives. Reads what `/epic-run` and child PRs already produced — merged PR bodies/diffs, stuck open PRs, followup/unfinished labels — and produces a ranked, evidence-cited list of changes to `epic-plan` / `epic-run` / `dispatch.md`.

**Signal lives in PRs + followups + stuck-PR backlog.** PR/issue bodies are primary; comments are bonus signal.

**Speculation is fine.** Mark confidence (`observed`, `inferred`, `hunch`) — surface a wrong hunch rather than miss a right one.

## Inputs

Fetch the same sources in parallel via Bash. For each closed epic, also pull its merged child PRs:

| Source | Command | What it gives |
|---|---|---|
| Closed epics | `gh issue list --label epic --state closed --json number,title,closedAt,body --limit <N>` | Epic # → child# list (parsed from `## Children`) |
| Merged PRs | `gh pr list --state merged --json number,title,body,files,additions,deletions,closedAt --limit 200` | Title-prefix, `Closes #<child>`, scope shape |
| Stuck PRs | `gh pr list --label epic-<N> --state open --json number,title,headRefName` per closed epic | Open PRs that auto-merge never resolved — CI brittleness or conflict signal |
| Followups | `gh issue list --label epic-followups --state all --json number,title,body,closedAt --limit 50` | `~~strikethrough~~` = closed, plain = open |
| Unfinished | `gh issue list --label epic-unfinished --state all --json number,title,body --limit 50` | Partial ACs filed mid-epic — recurring patterns = systemic gap |

## Steps

### 1. Pull

<!-- Source: epic-retro 2026-05-05 — core-REST label fetch (5000/hr vs 30/hr); dropped gotchas.jsonl (unreferenced in steps 2-5) -->
Default: last 10 closed epics. `/epic-retro 20` overrides.

```bash
# Bulk epic fetch — label filter, core REST bucket, no search quota
gh issue list --label epic --state closed --json number,title,closedAt,body --limit <N>

# child numbers from epic body's "## Children" section
gh pr list --state merged --json number,title,body,files --limit 200 | jq '[.[] | select(.body | test("Closes #[0-9]+"))]'

# per closed epic — stuck PRs that auto-merge never resolved
gh pr list --label epic-<N> --state open --json number,title,headRefName
```

**Multi-repo.** If multiple repos are active in the time window, pass them with `--repos a,b,c` (e.g. `--repos owner/repo1,owner/repo2`). Run the pull steps per repo and merge findings. Cite as `<repo>#<epic>` in evidence cells.

### 2. Mine stuck-PR backlog

For each closed epic in the window, count open PRs labelled `epic-<N>`. For each stuck PR:

- **CI red**: PR has a failing status check. Cluster failure reasons by CI job name from PR body or `epic-tools epic-status <N> --json`. High count across epics = CI brittleness.
- **Merge conflicts**: PR body or PR status indicates conflict. Recurring across epics = ordering/isolation problem in dispatch.
- **Draft-stuck**: PR still in draft — worker exited before marking ready. Dispatch template gap.

High stuck-PR count across multiple distinct epics = systemic. Surface with epic# citations.

### 3. Mine merged PRs

For each merged child PR in the window:

- **Scope honesty**: PR `additions+deletions`. Bottom-quartile (<10 LOC) = trivial — was the child issue too small? Top-quartile (>500 LOC) = was the child too big / scope crept?
- **Title-prefix audit**: `feat|fix|chore|test|perf|refactor`. Count by prefix. Drift from epic-plan's intended split surfaces planner bias.
- **Body shape**: missing `## Test evidence` block → dispatch template gap. Missing `Closes #<n>` → ownership/auto-close gap.
- **Completion shape**: join local completion rows by child issue. Missing rows
  mean the run did not audit child completion. Token fields, when present, can
  hint at prompt bloat; zero-token rows are valid marker-only completions.

### 4. Mine followups + unfinished

- **Followups recurrence**: cluster `epic-followups` titles by first 3 words. ≥2 occurrences across distinct epics = systemic.
- **Unfinished AC patterns**: same clustering on `epic-unfinished` titles. High-signal systemic gaps.
- **Open-vs-closed ratio**: many open followups = triage backlog (process problem); many closed-as-strikethrough = acceptable noise.

### 5. Bucket

Group findings into action targets — the file the improvement would land in.

- **`epic-plan/SKILL.md`** — child-boundary mistakes, missing `## Demo` / `## Out of scope`, ACs that turned load-bearing, planner scope-creep.
- **`epic-run/SKILL.md`** (this repo: `skill/SKILL.md`) — orchestrator lifecycle: dispatch ordering, auto-merge edge cases, fan-out cap tuning, resume logic.
- **`epic-run/dispatch.md`** (this repo: `skill/dispatch.md`) — subagent prompt template gaps, model-pick errors, branch-name collisions, exit-checklist holes.
- **`bin/epic-tools`** — the script's verbs (`parse-epic`, `epic-status`, `verify-pr`): new detectors, dead code, rollup-output tweaks.

A finding can land in 2 buckets if it argues for changes in both.

### 6. Synthesize (THE OUTPUT)

Lead with narrative, then the ranked table.

**`## What worked`** — 3–5 plain-prose bullets. Patterns that shipped cleanly, planner moves that paid off, dispatch shapes that scaled. Citations welcome but not required for this section. Don't pad — if only two things worked, name two.

**`## What didn't`** — 3–5 plain-prose bullets. Things that got stuck, gates that didn't fire, claims louder than delivery. Same citation latitude.

Then the ranked table. Highest-evidence first:

```
| Rank | Bucket | Proposed change | Evidence | Cost | Verdict |
|---|---|---|---|---|---|
| 1 | epic-run/SKILL.md | Increase default dep-poll timeout to 90s | stuck PRs in epics 41,47 — timeout race | 5min | do |
| 2 | epic-plan/SKILL.md | Add explicit `## Sibling repo` template requirement | followups #173 #208 (×3 cluster) | 15min | do |
| 3 | bin/epic-tools | Add merge-conflict detection to epic-status --json output | stuck PRs across epics 47,53,61 (conflict state) | 20min | do |
```

**Cost rule of thumb:** under 30min = `do`. 30min–2h = `propose, ask`. >2h = `surface`. Never skip a finding because it's expensive — surface it.

**Verdict**: `do` / `ask` / `surface` / `kill` (kill = delete a section/template, not add).

### 7. Apply or surface

For `do` rows: ask user "apply rows 1, 2, 4? (y/list)" — never silently. After approval, edit each file with one-line `Source: epic-retro <date>` provenance comment.

For `ask` and `surface`: just print, don't act.

### 8. Self-audit

End the report with: "Findings reviewed: <count>. Proposed: <X> do, <Y> ask, <Z> surface, <W> kill. Of last run's `do` rows, <P>/<Q> still show up in this run's findings (unstuck) — review whether the prior fix actually shipped."

Closes the meta-loop.

## Notes

- **Read-only by default.** Step 7 is the only place that mutates files, and it's gated on user approval.
- **Cost discipline.** Defaults to 10 epics, parallel fetches, no LLM calls beyond synthesis. Aim for <5 min wall-clock + ~80 tool calls — don't cap so tight you skip a repo.
- **Don't double-count.** A finding cited in a stuck-PR cluster, then again in a followup issue, then in a PR body, is ONE finding with three citations — not three.
- **Trust the data over priors.** If a pattern never recurs across epics, don't surface it. If a stuck-PR cluster recurs, escalate it — don't dismiss as one-off.
