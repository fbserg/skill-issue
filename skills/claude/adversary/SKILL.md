---
name: adversary
description: "Cross-model red-team: have Codex attack a plan or diff before you commit to it. Use before risky merges, deletions, or migrations."
---

Get a second model to attack a plan or diff. Codex runs read-only and never edits.

- **Diff, branch, or PR** → `/codex:adversarial-review`.
- **Anything else** → write it to a file, then:

```bash
codex exec --sandbox read-only -C "$(git rev-parse --show-toplevel)" -o "$OUT" \
  "Break this plan. Find what fails on first deploy, what the checks miss, and what is costly to undo. Cite file:line. No padding.

$(cat "$IN")" </dev/null
```

Check each finding against the code before you act on it. Report only what survives.
