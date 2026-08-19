# Per-lane decision files

Stub kept so this directory exists in git even when empty — never treated as
a lane file by `scripts/merge-decisions.py` (see `STUB_FILENAMES`).

A lane with a ruling to record writes `<lane-or-branch-slug>.md` here, using
the same entry format as `docs/DECISIONS.md` (one or more
`## YYYY-MM-DD — Title` sections). It never edits `docs/DECISIONS.md`
directly — see that file's "Recording a new ruling" section for why, and
`scripts/merge-decisions.py` for the close-out merge step.
