---
name: patchcue-resolve-issue
description: "PatchCue worker workflow for Claude Code: resolve one GitHub issue solo in the worktree PatchCue provides, posting its marked plan and outcome comments. Never merges. --resume continues a PatchCue run."
---

# PatchCue Resolve Issue

PatchCue launches this skill headless (`claude -p`) with one issue. The
workflow, the marked `<!-- patchcue:plan -->` and `<!-- patchcue:outcome -->`
comment protocol, the gate rules, and the resume rules live in `protocol.md`
beside this file (the same text the Codex worker follows). Read `protocol.md`
in full before any action, then follow it exactly.

Claude-specific notes:

- Work solo in the current directory. PatchCue already created the worktree;
  never create another and never spawn subagents. Ignore `--full`.
- `gh` is authenticated as the PatchCue login. Every issue comment you post
  must use the exact marker lines from `protocol.md`; PatchCue parses them.
- The launcher prompt adds `KIND:`, `UX_TWEAK:`, `REPORTER_ASK:`, and
  `OUTCOME: answered` on top of `protocol.md`. The launcher prompt wins
  where the two differ.
