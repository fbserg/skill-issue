---
name: adversarial-review
description: Red-team a plan or diff before risky work lands. Use for "adversary", "adversarial review", "red-team this", risky deletions, migrations, or multi-file rewrites. Read-only.
---

# Adversarial Review

Attack the plan or diff the user gives, else the branch diff. Look for what breaks on first deploy, what the checks miss, and what is costly to undo. Confirm each finding against the repo and cite it. If nothing credible turns up, say so. Do not edit files or commit.
