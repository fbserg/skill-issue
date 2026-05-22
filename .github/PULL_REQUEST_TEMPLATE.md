## What

<!-- One sentence: what does this PR change? -->

## Why

<!-- Why is this change needed? Link to an issue if applicable. -->

## Tested

<!-- How did you test this? For skill changes: describe the invocation and outcome. For epic-tools: paste the relevant --help output or test run. -->

- [ ] Skill tested end-to-end in Claude Code / Codex
- [ ] `python3 -m py_compile tools/epic-tools/bin/epic-tools` passes (if epic-tools changed)
- [ ] No private paths or account names introduced (`grep -rE '/Users/[a-z]+|fbserg' .` returns nothing)
