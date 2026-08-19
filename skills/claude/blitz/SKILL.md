---
name: blitz
description: Lightweight executor for multiple ad-hoc lanes — fast, parallel, adversarial — without the /issue → /resolve-issue pipeline. Use when the user invokes /blitz or wants an unfiled batch run fast. Not a planner (that's /epic-plan).
---

Boundary: one filed issue → `/issue`. Any batch — filed or ad-hoc → here
(`/issue` batch mode was deleted; DECISIONS.md 2026-08-07). For a filed
issue's lane, the card includes the issue number and its acceptance criteria.

You're the orchestrator; you don't implement. First action: one `ToolSearch`
selecting `Monitor,SendMessage,TaskStop` plus whatever else the batch needs —
not reloaded piecemeal mid-batch (measured: 5+ redundant reloads/session).
Posture:

- **Worker/bulk are the default.** Lanes, reads, extraction, mechanical steps
  → `worker`/`bulk`; `opus-worker` only after a `worker` has failed the
  subtask, or for a deliberate read-only judgment panel — never bare
  `general-purpose`/`Plan`/`Explore` (measured: a 152-agent Opus fan-out cost
  $5.1k where a Sonnet bakeoff scored within a few points;
  `docs/subagent-model-effort.md`).
- **Capability pre-check before fan-out.** Confirm the agent type actually
  carries the tools the task needs (measured: a 6-agent Drive/Gmail wave
  launched with an agent type that had no MCP tools and came back empty).
- **Fan out now.** Independent lanes in parallel worktrees, one lane per
  disjoint file set; serialize only genuine overlap.
- **Cluster before you cut cards.** Linked items (parent/follow-up, "after
  #N", same surface) go in one lane or sequential waves — file-scope checks
  can't catch semantic duplication (measured: #690/#749 raced to two
  overlapping merged PRs).
- **Dependent waves stack on an integration branch.** When wave N+1's code
  builds on wave N's unmerged PRs, base the wave on `stack/<epic>-<wave>`
  (children → wave branch → main, merged in order); land each wave before
  opening the next — GitHub won't retarget PRs on an unmerged rewritten base
  (measured: one epic stranded 19 open PRs on unmerged bases).
- **Spine files are single-writer.** Check churn (`git log --name-only`)
  first: the repo's most-touched shared files go to at most ONE lane per wave
  (measured: 98/100 sampled PRs overlapped a <24h-prior PR's files).
- **Lane cards, not broadcasts.** Each lane gets a scoped brief — file scope,
  acceptance gate, only the rulings that bind it (check CLAUDE.md AND
  AGENTS.md — AGENTS.md-only rulings exist) — never the full root prompt
  re-sent (measured: ~15x context inflation). A lane's first action: restate
  its scope and confirm no overlap with sibling cards.
- **Micro-work gets no lane.** A ≤~50-line fix with green targeted checks
  commits straight to the integration branch where the repo permits; batch
  several into one commit train.
- **Adversarial review before believing anything.** Distinct lenses,
  role-locked to refute, verified against the repo — applies to plans, diffs,
  and your own conclusions.
- **Findings return batched, never as issue confetti.** One batched finding
  list per review lane; at most one follow-up issue per surface (measured: 42
  follow-up issues filed in one day from a single wave).
- **3+ background lanes → arm the watchdog** per `docs/lane-watchdog.md` —
  lanes die silently; this skill doesn't restate the contract (heartbeat,
  1-lane mode, and the TERMINAL-line teardown check live there).
- **Rate-limit fallback.** Hit a fleet/session rate limit → stop polling,
  write in-flight state to the pulse dir, hand back to the human (measured:
  after a session-limit hit the parent repeated the same error 4x and did
  nothing).
- **Wave-completion summary names zero-output lanes.** Don't just report the
  wave as done — call out any lane that returned empty (measured: a 17-lane
  harvest's portal lane was silently empty, found only by parsing raw output
  JSON).
- **Long polls, never tight loops.** `Monitor`, or an until-loop, per
  `docs/lane-watchdog.md`, poll interval ≥60s (measured: 13,144 `wait_agent`
  calls at 30s in one batch).
- **Workflow-based lanes** follow `docs/workflow-template.md`.
- **Fast through gates.** No re-confirming between phases; push each lane to
  done (commit, PR, human merges). Per-lane gate ladder: targeted checks →
  one batched preflight → one expensive full gate — a gate failing twice
  without a new diagnosis is a blocker report, not a third run. Before any PR
  opens: the branch rebases clean against main and every sibling already
  pushed. Stop only for real scope changes or destruction.
