## 2026-11-03 — Skill diet: usage-review deleted, epic-plan and red-team skills shrunk

**Decision:** Delete `skills/claude/usage-review` (0 uses since it went
user-typed-only on 2026-10-14), superseding the 2026-08-19 "kept" ruling.
Shrink `epic-plan`, `adversary`, and Codex `adversarial-review` to short briefs
and drop the epic-plan review panel and `blitz` adversarial review. Owner
direction: newer models do better with goals than with scripted procedure.

**Reopen when:** epic-plan output shows duplicated issues, layer-sliced
children, or missed scope that the old panel would have caught.

## 2026-11-03 — resolve-issue cut to a brief; --full pipeline deleted

**Decision:** `resolve-issue` keeps only its guards (worktree, untrusted issue
text, comment re-poll, draft-until-mergeable, never merge) and, in Codex, the
PatchCue protocol v1 text verbatim. The `--full` pipeline, negative control,
mandatory failing-test-first, stub draft PR, and self-review ceremony are gone.
Supersedes the `--full` parts of the earlier resolve-issue rulings.

**Reopen when:** PatchCue runs or `/resolve-issue` PRs start shipping
regressions that a discriminating test would have caught.
