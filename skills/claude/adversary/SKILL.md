---
name: adversary
description: "Cross-model adversarial review: dispatch Codex to attack a plan or diff before you commit to it. Use after /epic-plan, before risky merges/deletions, or whenever a second model's red-team pass is worth 2 minutes."
---

Send the artifact under review to **OpenAI Codex** for an adversarial pass.
The point is cross-model disagreement: Codex has different blind spots than
Claude, and a critic that didn't write the plan has no sunk cost in it. Codex
runs read-only — never substitute a Claude subagent, and never let the critic
edit the tree. Skip for trivial diffs; the lens pays for plans, deletions,
migrations, and multi-file behavior changes.

## Routing

- **Git diff / branch / PR** → the codex plugin's `/codex:adversarial-review`
  (`--background` for a large diff, `--wait` for a small one). The plugin owns
  target selection — don't hand-roll this path.
- **Anything else** (a plan file, a decomposition doc, `~/.claude/plans/*.md`)
  → the hand-rolled path below.

## Hand-rolled path (non-diff artifacts only)

`RUN=$(mktemp -d)`, write the artifact to `$RUN/input.md`, then dispatch
read-only (foreground is fine — 1–3 min; background with a 600s timeout if the
session should stay free):

```bash
codex exec --sandbox read-only -C "$(git rev-parse --show-toplevel)" \
  -o $RUN/out.md \
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

$(cat $RUN/input.md)" </dev/null
```

**Triage the report, don't relay it.** For each finding: confirm against the
actual code (Codex hallucinates too), then fix the plan, add the missing
verification, or dismiss with a one-line reason. Present a short table:
finding → confirmed/dismissed → action taken.
