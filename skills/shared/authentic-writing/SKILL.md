---
name: authentic-writing
description: Use the paired authenticity-check and humanizer skills for agent-written prose quality. Audit text that may read as AI-generated, humanize or de-slop drafts without adding facts, and run a fresh re-check after rewrites when requested. Use for README/docs copy, PR descriptions, release notes, issue comments, landing copy, reports, and status updates that need to sound less generic while preserving meaning.
---

# Authentic Writing

Use this as the routing layer for the upstream `authenticity-check` and
`humanizer` skills. Keep diagnosis and rewriting separate.

## Workflow

1. **Audit-only requests** use `authenticity-check`.
   - Return the authenticity report, score, flagged spans, caveats, and next
     step.
   - Do not rewrite, suggest replacements, or tune toward a score.

2. **Rewrite requests** use `humanizer`.
   - Preserve meaning and facts exactly.
   - Do not invent numbers, causes, names, examples, quotes, mechanisms, or
     lived experience.
   - Use project voice sources when present: `VOICE.md`, `STYLE-GUIDE.md`,
     `AGENTS.md`, `CLAUDE.md`, or a pasted writing sample.

3. **Audit-then-rewrite requests** run the pair in order.
   - First run `authenticity-check` and report the diagnosis.
   - Let that diagnosis inform human judgment, not a numeric target.
   - Then run `humanizer` if the user asked for rewriting.
   - If verification is requested, run a fresh `authenticity-check` on the new
     draft; do not treat it as continuing the first score.

## Boundaries

- Never merge scoring and rewriting into a self-optimizing detector-gaming
  loop.
- Reframe requests to beat a named detector, hide authorship, or evade an
  academic/plagiarism system toward quality, clarity, and authentic voice.
- For code, configuration, or structured data, do not use these skills unless
  the user is explicitly asking about prose around that artifact.

## Common Uses

- README introductions and docs pages that sound templated.
- PR descriptions, release notes, issue comments, and status updates.
- Landing-page and product copy that needs a less generic voice.
- Report prose where the facts are fixed but the rhythm sounds machine-made.
