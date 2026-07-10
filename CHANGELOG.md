# Changelog

All notable changes to this project will be documented here.

## Unreleased

### Added
- `hooks/claude/stop-failure.sh`: StopFailure watchdog — logs API-error turn ends (rate limit, overload, server error) to `~/.claude/logs/stop-failures.jsonl` and rings the bell, so silently dying sessions leave a trace. Born from the 2026-07-10 hook audit.
- `docs/codex-subagent-model-routing.md`: install Codex custom-agent model/effort routing from the live model catalog and verify it from child rollout metadata, with cold-discovery and negative-control gates.
- `tools/transcript-archive/backup.py`: one-way daily archiver for Claude Code + Codex JSONL transcripts — strips embedded base64 blobs, never clobbers a larger copy with a smaller one, storage-agnostic (point `TRANSCRIPT_ARCHIVE_DIR` at any synced folder/disk/git repo). Includes a macOS launchd plist template.
- `blitz` skill (Claude): lightweight executor for ad-hoc lanes — parallel worktrees + adversarial review, no pipeline ceremony; boundaries documented against /issue and /ww.

### Changed
- Hook-audit fixes (2026-07-10): `pretool-bash.sh` Phase 3 now owns rtk rewriting alone (the duplicate standalone `rtk hook claude` settings entry double-rewrote and broke compound-predicate `find` commands that Phase 3 deliberately passes through) and short-circuits already-rewritten commands on rtk's exit-3 path; dead `advisor` hooks deleted; stale `MultiEdit` matchers dropped; `hooks/claude/README.md` corrected (anxiety-panel is project-scoped by design, not vestigial).
- `epic-plan` rewritten per the 2026-07-10 usage audit (per-child Context stanzas, impact-based blocker severity, feasibility/testability review lens, repo-grounded skeptic re-checks, tracker checklist re-sync, close-out verification, spike children); `simplify-sweep` slimmed (tidy-log.jsonl dropped — sweep commit tags are the state store; watchdog required at 3+ background batches); `docs/DECISIONS.md` gained the orchestration-lineup ruling (four entry points, no wave-loop orchestrator).

## 2026-06-20

### Changed
- Project is now **Claude-only**. Codex is fully phased out: the entire `skills/codex/` tree is archived under `deprecated/skills/codex/` and no longer installed. *(Reversed 2026-07-05 — see `docs/DECISIONS.md`; `skills/codex/` is live again and installed.)*
- Deprecated the `epic-run` pipeline (`epic-run`, `epic-research`, `epic-retro`) and the `epic-tools` CLI: all archived under `deprecated/`. They are not installed, not checked by `check-install.py`, and not symlinked by `install.sh`. See `deprecated/README.md`.
- Rebuilt `epic-plan` (Claude): lean, research-and-review-centric. Wide parallel research front-loads discovery; a 4-lens adversarial review validates the decomposition before issues are filed; child issues re-enter from GitHub state and execute via `/issue` → `/resolve-issue` (not `/epic-run`).
- `install.sh` and `check-install.py` updated to reflect Claude-only install: Codex loops and epic-tools wiring removed.

## Earlier (pre-2026-06-20)

### Added
- `tools/gmail-tools/bin/gmail-tools`: a deliberately draft-only Gmail CLI (search, read, label, attachments, multipart drafts) — a no-send proxy makes the send endpoint structurally impossible to call, so it's safe to hand to an agent. `uv` inline-deps, env-driven OAuth config.
- `issue` skill (Claude): triage router front door — assess (tier + Devin-style confidence) → claim (`gh issue edit --add-assignee @me`) → route to issue-do / resolve-issue / epic-plan, carrying the assessment forward so the executor doesn't re-assess. Re-runnable and resume-aware.
- `issue-do` skill (Claude): single-issue end-to-end runner — orchestrator plans, Sonnet executor implements in an isolated worktree, independent reviewer verifies; one verified PR out. Moved from a loose `~/.claude/skills/` copy into the repo and symlinked, matching the other skills.
- `tools/claude-spend/spend.py`: Claude Code per-project spend analyzer — per-session/per-skill token+cost rollup, cache-tier aware, long-context surcharge detection; stolen from hong (https://github.com/hyang0129/dot-claude)
- `epic-research` skill (Claude + Codex): pre-plan research with three parallel agent lanes
- `quick-research` skill (Codex): lightweight fan-out research for practical decisions
- `tidy` skill (Claude + Codex): anti-slop pass on changed code
- `skills/shared/` directory with canonical shared skill files

### Changed
- `issue` family collapsed to "always-resolve": `/issue` is now a thin front door (scope a rough idea, or dispatch one issue / a ≤4-concurrent batch to `/resolve-issue`) with no triage of its own; `/resolve-issue` self-scales by tier — a light path for tier-1 (single planner → one reviewer), the full pipeline for tier 2-3, and a stop-with-`/epic-plan` for a true epic — and gains two robustness invariants on its code-writing subagents (worktree-or-abort before any write; verbatim in-worktree gates from a repo `## Issue lane overrides` block before READY).
- `resolve-issue`: redesign from first principles — sequential by default with three fan-outs, each pinned to a named failure mode rather than added for parallelism's sake. (1) Tier-3 plan panel: 2–3 stance-diverse planners → synthesis, only when the solution space is genuinely contested (counters a plan that dead-ends). (2) Review panel: three perspective-diverse lenses (correctness / security & robustness / tests-actually-assert) run concurrently, then deduped (counters the blind spot a single reviewer gets when three concerns compete). (3) Blocker verification: one skeptic refutes each blocker before the fixer runs, so the fixer never "fixes" a phantom bug. Finalize gains a completeness gate — READY is forbidden on unrun/red checks or any unproven criterion. Fan-outs run as concurrent Agent calls (work headless); the Workflow tool is an optional accelerator, never required. No private agent-type identifiers; HANDOFF stays the single protocol. Mechanism (parallel lenses + structured output) smoke-tested earlier against a synthetic diff; not yet exercised against a real tier-3 issue.
- README and install docs now match the shipped skill set and avoid treating Markdown as an install script
- `check-install.py` now verifies every shipped Claude/Codex skill symlink, including the issue router family (`issue` / `issue-do` / `resolve-issue`) and `quick-research`
- `epic-plan` (Claude + Codex): refactored to 7-stage flow with one-question-at-a-time grilling and inlined external research (Stages 0–7)
- `zero`: default conflict resolution changed from auto-resolve to stop+ask; add `--auto-resolve` opt-in flag; add pre-push confirmation gate; detect default branch dynamically
- Remove stale `sweep` install/check documentation after the skill was dropped from the public bundle
- `dispatch.md`: replace `Skill({skill:"tidy"})` with reference to shipped tidy skill; make `advisor()` conditional on `advisorModel` setting; remove private `scripts/tests_for.py` path
- `epic-retro`: remove `$HOME/projects/*` hardcoded path and fix jq filter
- `epic-run`: trim Hard rails and add harness contract note
- `resolve-issue`: added issue claiming (`gh issue edit --add-assignee @me`) + a concurrent-run guard that was missing; a `--resume <N>` continuation path that re-enters the review cycle from a `CONTINUATION` comment emitted at the 3-cycle cap (so a big issue can take two attempts without restarting from zero); `opus-worker` escalation when Sonnet fails the same blocker twice; plan-comment-as-claim posted before the implementer branches; and an optional prior-art web-research lane for tier-3 questions about external/standard approaches. Accepts an `ASSESSMENT` block from the new `issue` router and skips its own assess step.
- `issue-do`: accepts the `issue` router's `ASSESSMENT` (skips re-deriving scope), claims the issue before dispatch, escalates to `opus-worker` after two failed Sonnet review rounds, treats executor silence/idle as failure rather than success (completion handshake — confirm a PR actually landed on GitHub), packages its plan as an epic-plan seed comment when it discovers the issue is multi-session (instead of discarding the work), and drops the stale `TIDY` flag that `dispatch.md` ignores.

### Fixed
- Add an install-contract check so shipped Claude/Codex skills and `epic-tools` cannot silently point at different checkouts
- Fix skill frontmatter so all shipped skills pass validation
- Remove stale completion-audit documentation from the current `epic-tools` surface
- `epic-tools revert` and `cleanup` now require `--yes` or interactive confirmation
- `codex/epic-run/SKILL.md`: replace `~/.claude/state` hardcoded path with runtime-neutral note
- LICENSE: change copyright from "Serg" to "skill-issue contributors"

### Removed
- `issue-do` skill — folded into `/resolve-issue`'s self-scaling tier-1 light path; it was never symlinked, so nothing installed it.
- Empty `grill-me/` directories (skill was never included)
- Empty `codex/epic-plan/references/` directory
- Extra `agents/README.md` from the Codex `epic-plan` skill package
- `issue-sweep` skill and its scripts (never shipped — added and removed within this unreleased window). Its one unique behavior, claiming the issue before work, is now built into the `issue` router and the `issue-do` / `resolve-issue` rungs.

## Initial public release (2026-05-22)

- `epic-plan`, `epic-run`, `epic-retro`, `zero` for Claude
- `epic-plan`, `epic-run`, `zero` for Codex
- `epic-tools` CLI
