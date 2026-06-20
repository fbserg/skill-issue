---
name: refactor-dupes
description: "Duplication-driven refactor pipeline for a pointed directory: detect → architecture → refactor → review, as four role-separated fresh-context subagents exchanging typed handoffs. Detection shells out to jscpd (token clones) + lizard (complexity) and the LLM only triages; the architecture stage is allowed to rule LEAVE (anti-over-abstraction discipline) and gates on operator approval before any edit; refactor runs in a worktree behind an explicit brief; review fans out correctness / tests-assert / over-abstraction lenses. Orchestrator never reads code. Never merges — terminal is READY (draft PR) or BLOCKER. Triggers: /refactor-dupes <dir>, 'find and refactor duplication', 'DRY this up', 'collapse the copy-paste in X'."
---

# Refactor Dupes

Find duplicated logic in a target directory, decide which clusters are worth collapsing (and
which to leave alone), refactor the worthwhile ones cleanly, and verify nothing broke — as a
staged hand-off between four focused subagents, never one agent doing everything.

You — the session model — are the orchestrator. You hold no code context: you run the detector's
*summary* through subagents, pass typed handoff blocks between phases, gate on the operator, and
report. The structure keeps roles honest — the architecture agent never edits, the refactor agent
never reviews itself, the reviewer never fixes.

This skill is the discovery-seeded sibling of `resolve-issue`. `resolve-issue` starts from a known
issue; this one *scans for* the target. The two new things it adds: a duplication **detection
front door**, and an architecture stage allowed to say **"leave this duplication alone."**

## Hard rules (no judgment calls)

- **Never merge.** Terminal states are READY (draft PR, human merges) or BLOCKER. Nothing else.
- **Orchestrator holds no code context.** You never read repo files, run git, or run tests
  yourself. All code work happens inside subagents. Handoff blocks may name files and describe
  clusters/plans/findings in prose; they must never carry source lines, diffs, or pasted file
  bodies. This is what keeps your context clean across the pipeline — protect it.
- **Every phase subagent spawns via `agentType: "worker"`** (Sonnet at `effort: medium`). Name the
  agent type on every Agent call — `model: "sonnet"` alone silently inherits the session's low
  effort. Blocker-escalation in Step 4 uses `agentType: "opus-worker"`; everything else is `worker`.
- **Role separation:** the architecture agent writes no code; the refactor agent writes no review;
  the final review pass triggers no fixes.
- **Detection is tool-first.** The detect stage shells out to `jscpd` + `lizard` and the LLM
  *triages* the tool output — it never eyeballs files to "find" duplication. LLMs hallucinate
  clones and miss exact copies in files they weren't handed.
- **Worktree-or-abort.** The refactor subagent's first action asserts it is in its own
  `git worktree`, not the primary checkout: `git rev-parse --show-toplevel` must be a path listed
  by `git worktree list` and must not be the primary. If it finds itself in the primary, it aborts
  and does nothing — never edit, commit, or `git reset` the primary.
- **The operator gate is mandatory and pre-refactor.** No file is edited until the operator has
  approved the architecture brief. This is the steering gate; a post-diff review can only catch,
  not redirect.
- **Gates verbatim before READY.** Finalize runs the repo's real checks copied verbatim (from a
  lane-overrides block in CLAUDE.md/AGENTS.md if present, else the repo's documented gate
  commands), executed never paraphrased. READY is never allowed on unrun, red, or paraphrased gates.

## Handoff protocol

Every phase subagent ends its reply with exactly one block:

```
HANDOFF
KEY: value
KEY: value
END_HANDOFF
```

You carry forward only these blocks plus your own one-line summaries — never raw file contents or
diffs. Malformed or missing block → re-ask once for the block alone; if that fails, treat the
phase as failed. Scratch files live under `/tmp/refactor-dupes/<run>/`.

## Inputs

`/refactor-dupes <target_dir> [--min-tokens N]` — scan one directory. Default `--min-tokens 50`.
MVP scans a pointed directory and carries the single highest-value COLLAPSE cluster through to a
draft PR. (Multi-cluster batching, parallel worktree lanes, and `--resume` are deferred — see
**Deferred** at the bottom.)

## Step 1 — Detect (read-only subagent)

Spawn a read-only detector. Its job is to run the tools, normalize their output, apply the
rule-of-three floor, and hand back ranked clusters — **not** to propose fixes.

Commands (validated on this machine — `npx`/`node`/`lizard` are on PATH; `jscpd` resolves via
`npx --yes`):

```bash
RUN=/tmp/refactor-dupes/$(date +%s); mkdir -p "$RUN"
# Token clones (Type-1/2). JSON is the machine feed; ignore tests + vendored trees.
npx --yes jscpd --reporters json --min-tokens 50 --min-lines 5 --silent \
  --ignore "**/tests/**,**/*.test.*,**/node_modules/**,**/.venv/**,**/*.generated.*" \
  --output "$RUN/" <target_dir>
# Complexity ranking → near-miss (Type-3) second-pass candidates jscpd misses.
lizard <target_dir> -s cyclomatic_complexity 2>/dev/null | sort -k2 -rn | head -20
```

Parse `"$RUN/jscpd-report.json"` (`duplicates[]`, each with `firstFile`/`secondFile`
name+`start`/`end`, `lines`, `fragment`). Then:

- **Rule-of-three floor:** drop clusters < ~10 lines. Group clone *pairs* that share a fragment
  into one logical cluster and count occurrences; drop clusters with < 3 occurrences unless a pair
  is large and clearly copy-pasted.
- **Type-3 second pass:** for the top handful of highest-CCN functions from lizard, read just
  those functions and judge whether any look like near-miss copies of each other (renamed /
  one-extra-branch variants the token tool won't catch). Add them as `clone-type: 3` clusters.
- **Drop generated/vendored noise:** lockfiles, `.vale` vocab lists, `_enums`/`db.types`/`*.generated.*`
  and any Do-Not-Edit-table outputs are never refactor targets.

Handoff `CLUSTERS` — one line per cluster: `id`, files+line-ranges, occurrence count,
`clone-type` (1/2/3), rough LOC footprint, jscpd similarity %. Rank by `occurrences × LOC`.
If zero clusters survive the floor, hand back `CLUSTERS: none` and stop — report a clean tree.

## Step 2 — Architect (read-only subagent) — the go/no-go

Input: the `CLUSTERS` block (the orchestrator picks the top cluster for MVP and names it). The
agent reads the duplicated regions and rules on each, applying the discipline questions
(Sandi Metz "duplication is cheaper than the wrong abstraction"; Kent Dodds AHA / rule-of-three):

1. **Do the copies evolve together or independently?** Diverged (different conditionals, different
   edge-case handling) → they were always different things wearing the same clothes → **LEAVE**.
2. **Would the abstraction need flags to handle the variants?** One boolean param = yellow flag;
   two = red → **LEAVE**. "The abstraction is wrong if you must pass it a flag telling it what to do."
3. **Is it test duplication?** Explicit repetitive test setup usually beats a DRY helper → **LEAVE**
   unless the duplication is large and mechanical.
4. **Does the cluster cross a deliberate boundary?** Parallel code that exists *because* two
   modules must not depend on each other is intentional → **LEAVE**, never collapse it into a
   shared merge. (Heartwood: `snag` and `burl` never import each other; cross-app behavior belongs
   in a shared package, not a fusion of the two copies. Check the repo's own boundary docs.)
5. **Rule of three is the floor, not automatic permission.** Frequency is necessary, not sufficient.

Output per cluster: `verdict` ∈ `COLLAPSE | LEAVE | NEEDS-HUMAN`, a one-paragraph rationale, and —
for COLLAPSE only — a **brief** that *enumerates the exact files, the exact abstraction to extract
(name + where it should live), and the target call-site signature*. The brief must be specific
enough that the refactor agent follows it without inventing scope: scope creep ("Aggressive
Implementation" — extending beyond intent while regressing) is the documented #1 refactor-agent
failure, and an enumerated brief is what constrains it.

Handoff `VERDICTS` (per cluster: verdict + one-line rationale), `BRIEF` (per COLLAPSE: files,
abstraction, signature, call-site list).

## Operator gate (the steering point)

Present the `VERDICTS` and any COLLAPSE `BRIEF` to the operator — `AskUserQuestion` (or a plain
confirm for a single cluster). The operator approves which briefs proceed. **Nothing is edited
before this.** NEEDS-HUMAN clusters are surfaced here for a ruling, never auto-refactored. If the
operator approves nothing, stop and report the verdicts — a clean "leave it all" is a valid outcome.

## Step 3 — Refactor (worker subagent, in a worktree)

Spawn one `worker`. Input: the approved `BRIEF` only (not the detector's or architect's reasoning).

- **First action: worktree-or-abort** (hard rule). Create the worktree if needed:
  `git worktree add <dir> -b refactor/dupes-<slug>`.
- For a code repo, push an empty initial commit and open a **stub draft PR** (`Draft: refactor
  duplication — <slug>`, brief summary) before editing — a durable marker exists for the whole phase.
- If the repo has a bootstrap / lane-overrides block (CLAUDE.md / AGENTS.md), run it verbatim first.
- **Follow the brief exactly:** extract the named abstraction into the named location, repoint
  every listed call site. Do not collapse anything not in the brief; do not "improve" adjacent code.
- **Write a state-tracking artifact** `"$RUN/changelog.md"`: one line per file touched and what
  changed. Re-read it before each call site — this is the fix for the documented multi-file
  refactor failure where the agent loses track of what it has already changed.
- Run the repo's fast test loop to confirm green before handing off. Commit (one commit, message
  references the cluster); push.

Handoff `WORKTREE`, `BRANCH`, `PR_URL`, `ABSTRACTION` (name + location), `SITES_REPOINTED`
(count + list), `CHANGELOG_PATH`, `DEVIATIONS_FROM_BRIEF`, `TEST_RESULT`.

## Step 4 — Review cycle (read-only fan-out + fixer; default one cycle)

Mirror `resolve-issue` Step 3 with one duplication-specific lens. Spawn three reviewer lenses
concurrently over the full PR diff, each fresh context:

- **correctness** — behavior preserved at every repointed call site; the abstraction handles each
  original variant; return values and edge inputs unchanged.
- **tests-actually-assert** — existing tests still exercise the merged paths; **negative-control**
  the abstraction (break its body, confirm at least one test fails, restore). A refactor whose
  tests survive the abstraction being broken has tests that assert nothing.
- **over-abstraction** (the new lens) — did the extraction introduce flag params or wrong coupling?
  Did it collapse something that should have been LEAVE? Did complexity/size *grow*? (AI review is
  documented as over-permissive on complexity growth — this lens is the counterweight.)

Each emits findings `F-<cycle>-<n>` with severity (blocker / should-fix / nit), file, concrete
description. **Dedup across lenses** by file+description, keeping highest severity. Handoff
`FINDINGS`, `VERDICT` (approve / needs-fixes).

- **Blocker verification** (read-only, only if blockers): one skeptic per blocker, framed as
  refuting a *prior reviewer's external claim* ("a prior reviewer concluded X; find the flaw").
  A blocker that can't survive refutation is downgraded with the reason recorded. Handoff `VERIFIED`.
- **Fixer** (fresh `worker`, only if findings remain): address each finding or decline nits with a
  reason; commit; push. Handoff `RESOLVED`. **Opus escalation:** a *blocker* that survives a second
  fix cycle (same finding back after Sonnet tried once) runs on `agentType: "opus-worker"` before
  spending another cycle.
- **Intent validator** (read-only): diff pre-review HEAD vs post-fix HEAD; confirm only the
  findings were addressed and nothing drifted. Handoff `INTENT_OK` (yes/no + drift).

Cap at three cycles, then BLOCKER. The final review of the last cycle is read-only — whatever it
finds is reported, never fixed in this run.

## Step 5 — Finalize

One `worker`: rebase onto the current base, then **run the repo's real checks verbatim** (lane
overrides / CLAUDE.md gate commands if present, else pytest / ruff / npm test / make check) —
never paraphrased. Completeness pass: abstraction correct, every repointed site covered, every
check green. Anything unproven is a BLOCKER, not a footnote. Assemble the PR body and mark the PR
ready (`gh pr ready`).

PR body: **What changed** (the duplication collapsed, the abstraction added) · **Call sites
repointed** (the list) · **Left intentionally duplicated** (any LEAVE/NEEDS-HUMAN clusters + why)
· **Test evidence** (counts, negative-control line) · **Review summary** (findings + resolutions)
· **Merge instructions** (per repo convention, for the human — never executed).

Handoff `STATE` (READY | BLOCKER), `PR_URL`, `CHECKS`, `BLOCKER_DETAIL`.

## Final report

Report to the operator: target dir, clusters found and how each was ruled (COLLAPSE/LEAVE/
NEEDS-HUMAN with one-line reason — nothing hidden), the abstraction extracted and sites repointed,
PR URL and state, test/negative-control result, review findings and resolutions. On BLOCKER, name
what's unresolved. Then clean up the worktree (`git worktree remove`) — branch and PR remain.

## Deferred (not in MVP)

Multi-cluster batching (churn-balanced, à la `simplify-sweep`); parallel refactor lanes in
separate worktrees; a `dupe-scan` helper tool (single-file stdlib Python, `epic-tools` pattern)
that runs jscpd+lizard and emits normalized cluster JSON so the detector doesn't hand-roll the
shell-out; a `--resume` path; GitHub-issue seeding. Build these only when the MVP has earned them.
