# writing-references

Single source of truth for the criteria shared by the `humanizer` and
`authenticity-check` skills: `tell-patterns.md`, `do-not-flag.md`,
`voice-matching.md`. Both skills reach these via relative symlinks in their
own `references/` dirs, so their SKILL.md paths are unchanged.

Upstream: vendored from [aihxp/humanizer](https://github.com/aihxp/humanizer)
(MIT), which is the canonical source for these files upstream too
(authenticity-check re-vendors them). Local copies were byte-identical apart
from a sync-obligation header, so they were collapsed here. When re-vendoring
a new upstream release, update these files once from humanizer's
`references/` and leave the symlinks alone.
