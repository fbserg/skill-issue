---
name: adversary
description: "Cross-model adversarial review: dispatch Codex (gpt-5.5, fast tier) to attack a plan or diff before you commit to it. Use after /epic-plan, before risky merges/deletions, or whenever a second model's red-team pass is worth 2 minutes."
---

Send the artifact under review to **OpenAI Codex** for an adversarial pass. The point is
cross-model disagreement: Codex has different blind spots than Claude, and a critic that
didn't write the plan has no sunk cost in it. Codex runs read-only — it critiques, it
never edits.

## Routing

- **Artifact is a git diff, branch, or PR** (the common case — the diff about to merge,
  the current branch, `git diff <base>...HEAD`): route to the codex plugin's
  `/codex:adversarial-review`. Use `--background` for a large diff, `--wait` for a small
  one. The plugin owns target selection and execution — don't hand-roll this path.
- **Artifact is not a git diff** (a plan file, a decomposition doc, `~/.claude/plans/*.md`):
  the plugin can't target these. Use the hand-rolled path below.

## Hand-rolled path (non-diff artifacts only)

1. Write the artifact to `/tmp/adversary-$RUN-input.md` with
   `RUN=$(date +%Y%m%d-%H%M%S)`.

2. Dispatch Codex read-only on the fast tier (relieves the main-profile quota):

   ```bash
   codex exec --profile trusted-fast --sandbox read-only -C "$(git rev-parse --show-toplevel)" \
     -o /tmp/adversary-$RUN-out.md \
     "$(cat <<'PROMPT'
   You are a chaos engineer and adversarial reviewer. Your job is to break the plan
   below, not to improve it. Assume the author is competent and still wrong somewhere.

   Attack, in order:
   1. The deletion/rewrite blast radius: callers, module-level imports, dynamic references,
      config/scripts/cron that the author's grep would miss.
   2. Hidden state and lifecycle: what runs at import time, what persists on disk/DB, what
      breaks on the FIRST deploy (not in tests).
   3. The rollback story: if this lands and is wrong, what is the cost to revert, and what
      will have mutated by then?
   4. The verification gap: what the stated tests/acceptance criteria do NOT cover.
   5. One failure narrative: the most plausible concrete sequence ending in a revert commit.

   Read the repo as needed. Be specific (file:line), no hedging, no compliments. If you
   genuinely find nothing, say "no credible attack found" and state what you checked.
   PROMPT
   )

   $(cat /tmp/adversary-$RUN-input.md)" </dev/null
   ```

   Run it in the background with a 600s timeout if the session should stay free; otherwise
   foreground is fine — fast tier usually returns in 1–3 minutes.

3. **Triage the report, don't relay it.** Read `/tmp/adversary-$RUN-out.md`. For each finding:
   confirm it against the actual code (Codex hallucinates too), then either fix the plan,
   add the missing verification, or explicitly dismiss it with a one-line reason. Present the
   user a short table: finding → verdict (confirmed/dismissed) → action taken.

## Notes

- This intentionally crosses models; do NOT substitute a Claude subagent here.
- Read-only sandbox is load-bearing: the critic must not "helpfully" edit the tree.
- Skip for trivial diffs (docs, one-liners) — the lens only pays for plans, deletions,
  migrations, and multi-file behavior changes.
