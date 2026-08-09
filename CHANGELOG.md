# Changelog

All notable changes to this project will be documented here.

## Unreleased

- Stacked-epic guidance in claude `epic-plan` (Handoff) and `blitz` (posture):
  code-dependent waves base on a `stack/<epic>-<wave>` integration branch
  merged in order, landing each wave before opening the next, instead of
  stacking PRs on unmerged sibling branches — GitHub doesn't retarget PRs on
  an unmerged rewritten base. Prompted by a real epic stranding 19 open PRs
  on unmerged bases.
- Codex mirror joins the issue-lane diet (DECISIONS 2026-08-07): the long
  pipeline now requires an explicit user-typed `--full` on BOTH trees.
  `skills/codex/resolve-issue` defaults to one solo end-to-end pass in a
  worktree; the tiered assess/plan/implement/independent-test/review structure
  moved behind `--full` (kept inline — `docs/` doesn't install to `~/.codex`),
  and the codex `issue` front door only passes `--full` through when typed.
  Carried gates (amendment re-poll, negative control, draft-state finalize)
  unchanged and still green under `generate-codex-skills.py --check`. Stale
  INDEX.md rows still describing the pre-diet "self-scaling" claude
  issue/resolve-issue reconciled at the same time.
- New Claude skill `usage-review`: review a body of AI-assistant transcripts
  (own local Claude Code / Codex CLI sessions, or a shared exporter-markdown
  archive) into a red-teamed report. Ships the pipeline tools (quant, command
  scan, summarize, stratified sample, render, risky digest, rubric grader,
  digest, secret scan) plus parametrized lane and red-team Workflow scripts and
  the calibrated methodology. Privacy contract enforced in `pipeline.py`: corpus
  read-only, work dir refused inside any git repository (work tree, bare or .git dir), `.gitignore *` written,
  secret scan before sharing; the only egress is what the grader/lanes send to
  the user's own model provider.
- claude-spend freshness tripwires: the vendored pricing snapshot is now
  stamped with `_meta.vendored_at` (vendor_pricing.py), the generator requires
  the stamp and freezes it into `pricing_generated.py`, and spend.py's summary
  prints an actionable staleness warning past 120 days. Together with the
  existing family-fallback report (new model IDs announce themselves) and
  dated overrides (announced flips like Sonnet 5's Sep 1 encoded ahead of
  time), pricing staleness is now self-announcing on every axis — no cron, no
  runtime fetch. Also fixed hooks/claude/README.md's quality-suite stage count
  (said four, lists five).
- Mirror-sync fix (#28): `hooks/claude/expensive_model_edit_guard.py` and
  `hooks/claude/edit_guard_backstop.py` deleted from the published mirror —
  they were already dead in the live hook set per the 2026-07-24 DECISIONS.md
  subtraction-pass ruling, but the mirror still shipped and advertised both,
  which misled an outside contributor into filing an issue against dead code.
  README.md, hooks/claude/README.md, and INDEX.md hook counts/tables
  reconciled against the actual `hooks/claude/` inventory (mirror hook count
  was Nine, actual is Seven; INDEX.md also dropped a phantom
  `sessionstart-context.sh` row that pointed at a file that never existed in
  this mirror).
- Watchdog fix + mechanized delegation guard + subtraction pass: replaced the deprecated, subagent-unavailable `TaskOutput` remediation check with `claude agents --json`; made watchdog remediation kill-before-restart via `TaskStop`; seed each lane's pulse file at dispatch instead of on the lane's own first write (closes the highest-probability, zero-detection wedge: dead before first pulse); namespaced pulse dirs per batch id; consolidated the previously duplicated and contradictory watchdog contract (issue: 5min/12min, blitz: 60s/2-interval) into one canonical `docs/lane-watchdog.md`, raising the stale threshold to 20min (measured ~44% false-positive rate at 12min). Added `tools:` frontmatter to `worker`/`bulk`/`opus-worker` omitting `Agent`, and a new `lane` agent type (keeps `Agent`) for the sanctioned `/issue` batch exception; `/issue` batch dispatch now uses `agentType: "lane"`. Deleted `skills/shared/ww`, `skills/claude/transcript-backup`, and `skills/shared/authentic-writing` (zero measured invocations / pure restatement of already-global rules). Collapsed `/issue` Single mode into a literal `/resolve-issue <N>` alias. Collapsed `/resolve-issue`'s tier-1/2/3 system to light/full/epic, gating the plan panel and review-lens count on their own conditions instead of a tier number. Extracted the duplicated-and-drifting Codex-builder-lane contract (`docs/codex-builder-lane.md`) and adversarial-review-panel contract (`docs/adversarial-review-panel.md`) into shared files referenced by `/resolve-issue`, `/epic-plan`, `/issue`, `/blitz`, and `/simplify-sweep`. Fixed `adversary`'s `--profile trusted-fast` (no-op: zero `[profiles.*]` blocks in `~/.codex/config.toml`) and the stale "no GitHub writes until GO" claim in README/INDEX for `epic-plan` (GO gate removed in b4d2754). Added `scripts/check-refs.py`, a reference-drift guard (slash commands, agent types, tool names, model ids), wired into `scripts/check-install.py`.
- `vale/`: added the `AItells` vale package — a canonical, three-severity-tier (error/warning/suggestion) AI-tells prose style merging the house `etc` style (base, verbatim), curated high-precision rules from the `ammil-industries/vale-signs-of-ai-writing` upstream, and a trimmed subset of the 44-rule `heartwood/burl` reference pack. 23 rule files, deduped so no token appears in more than one rule, with known false-positive traps (bare "elevated"/"navigate"/"beacon"/"harness"/"gateway", solo "significant"/"important", plain tricolons at warning+) encoded as exclusions. Ships `vale/build.sh` (zips into `vale/AItells.zip`, matching the upstream package's internal layout) and `vale/README.md` (wiring via `Packages =` + `vale sync`, tier/`MinAlertLevel` guidance, per-rule disable).
- `transcript-archive` hardening: atomic writes (temp file + fsync + `os.replace()`, no more disk-full/crash leaving a truncated destination permanently invisible to the mtime-skip guard); a machine-identity handshake (`.transcript-archive-identity` in the archive + a local nonce record) that catches machine-id collisions and unmounted/wrong-destination NAS mounts, both of which previously exited 0 while silently corrupting or fabricating archive history — new `--adopt-archive` flag for the two legitimate one-sided-mismatch cases; `install.sh`'s default machine-id changed from bare hostname to `<os-username>-<short-hostname>` (bare hostname was the most collision-prone default on a team) and it now refuses (before registering the schedule) if the destination already carries a mismatched identity; symlinked source subtrees (e.g. a symlinked project dir under `~/.claude/projects`) are now followed via `os.walk(followlinks=True)` with cycle detection instead of being silently skipped by pathlib's glob; a raw-copy source with an unchanged-or-newer mtime but different size (a restored/reverted file) now re-copies instead of skipping forever; long destination paths (measured 407+ chars in practice) now get a per-file `WARN long-path` log line since OneDrive silently refuses to sync past ~400 chars. README gains an "Analyzing the archive" section and expanded failure-modes documentation. Follow-up hardening: the identity handshake's own writes are no longer unguarded — an unwritable `XDG_STATE_HOME`/archive volume now exits(2) with an honest refusal (rolling back the archive-side identity file if only the local-side write failed) instead of an uncaught traceback and a half-completed handshake; each run sweeps orphaned `*.tmp` files left by a hard-killed atomic write (age > 1h) instead of letting them accumulate silently forever; `install.sh --help` corrected to match the actual `<os-username>-<short-hostname>` machine-id default.
- `transcript-archive`: optional `--compress` (gzip, deterministic, ~3.7x measured on a real archive) with automatic plain<->`.gz` format migration and an `install.sh --compress` pass-through.
- `transcript-archive` v2: multi-machine namespaced archive layout (`<machine-id>/claude/...`, `<machine-id>/codex/...`), a JSON-aware image tombstoning policy replacing the v1 base64 regex (which was silently corrupting thinking-block signatures, JWTs, embedded PDFs, and SVG paths), `~/.claude/tasks` now archived (Claude Code's cleanup sweep purges it too, upstream #51779), and a `--force` repair flag for re-running over v1-corrupted archives. Adds `install.sh` (renders the launchd plist / writes the cron line, runs the first dump in the foreground) and a `/transcript-backup` skill as the primary setup path.
- Updated Codex `blitz` to batch fixes before hosted CI, avoid cosmetic-only CI restarts, and permit locally cleared stacked lanes while preserving dependency-ordered, final-head-checked merges.
- Added the runtime-native Codex `blitz` skill and retired the stale Codex `issue-wave` registration; Codex now matches the four-entry-point orchestration decision.
- Synced current Claude-side workflow lessons into the Codex epic/issue lifecycle and made shared `zero` canonical for both runtimes to prevent future drift.

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
