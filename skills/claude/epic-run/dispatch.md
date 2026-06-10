# Dispatch — subagent procedure

Included in each child prompt. Orchestrator does not load this file.

Vars: `<N>`, `<child>`, `<slug>`, `<RUN_ID_SUFFIX>`,
`<DEFAULT_BRANCH>`, `<PYTHON>`, `<EPIC_TOOLS>`, `<TIDY>`, `<GH_USER>`,
`<MODE>`. `<EPIC_TOOLS>` is absolute; don't `which` it.

```
Execute issue #<child> of epic #<N> in an isolated worktree from
origin/<DEFAULT_BRANCH>. Preserve unrelated changes and touch only this child.

## Issue scope
<body field from parse-epic output — no extra fetch needed>
```

Setup:

```bash
PYTHON=<PYTHON>
GH_USER=<GH_USER>
MODE=<MODE>
export GIT_EDITOR=true
REPO=$(git remote get-url origin | sed -E 's#.*github.com[:/]([^/]+/[^/.]+)(\.git)?#\1#')
```

If `gh` hits `GraphQL: API rate limit already exceeded`, use REST:
`gh api repos/$REPO/issues/<n>`, `.../labels -X POST`, `.../pulls/<n>`,
`repos/$REPO/issues?labels=<l>&state=all`, and `.../check-runs`.

## Workflow

0. **Bootstrap before any other action.**

   Follow the repo's bootstrap docs (CLAUDE.md `## Worktree bootstrap` section, or README install instructions) when present. Use lockfile auto-detection only as a fallback:

   Run `CLAUDE.md` `## Worktree bootstrap` fenced `bash` block if present.
   Else auto-detect:

   ```bash
   [ -f uv.lock ]           && uv sync --frozen
   [ -f poetry.lock ]       && poetry install --sync --no-interaction
   [ -f pyproject.toml ] && [ ! -f uv.lock ] && [ ! -f poetry.lock ] && uv sync
   [ -f pnpm-lock.yaml ]    && pnpm install --frozen-lockfile
   [ -f package-lock.json ] && npm ci
   [ -f yarn.lock ]         && yarn install --frozen-lockfile
   [ -f .pre-commit-config.yaml ] && pre-commit install --install-hooks
   ```

   Retry one bootstrap failure. Two failures → `STATUS=fail
   REASON=bootstrap-failed`; do not proceed.

1. `git fetch origin && git checkout -b epic-<N>-<child>-<slug>-<RUN_ID_SUFFIX> origin/<DEFAULT_BRANCH>`.
   Dependencies are already merged; never wait on them.
2. Read every file listed in "Files likely touched" before editing.
3. Implement only this issue. Run focused tests only, e.g.
   `<PYTHON> -m pytest -q tests/test_<area>.py` or the equivalent focused test command for the changed files. Never run the full tree.
4. If `<TIDY>=yes`, dispatch a tidy review subagent (Sonnet) before committing — never invoke the tidy skill inline; a hook
   blocks writer-grading-self. Give the subagent the diff scope and the lens doc at `skills/claude/tidy/SKILL.md`, apply its
   high-confidence fixes, and re-run focused tests if anything changed. Skip when `<TIDY>=no`.
5. `git diff --stat`; reject foreign files. Commit once with `git commit -m/-F`;
   message references `(#<child>)`. Never amend or open an editor.
6. `git push -u origin <branch>`.
7. Write a PR body from the template. Create the PR:
   `<EPIC_TOOLS> pr-create --epic <N> --title "<prefix>: <title> (#<child>)" --body-file "$PR_BODY" --head <branch> --base <DEFAULT_BRANCH>`.
   Prefix is `chore|test|fix|feat`.
8. Verify ownership:
   `<EPIC_TOOLS> verify-pr --epic <N> --child <child> --pr $PR --claimed-sha <sha> --author "$GH_USER"`.
   Failure goes to Bail.
9. Risk-gated verifiers. Run test-integrity and AC verifiers only for behavior
   changes, shared helpers, multi-file changes, or tests that could weaken
   coverage. Skip for tiny docs, comments, and mechanical edits. When run, the
   test-integrity verifier fails on weakened/skipped/hollow/missing tests; the
   AC verifier fails unless every accepted criterion passes.
10. Stop at a verified PR. Do not queue auto-merge, merge directly, push to
    main, or ask the user to merge. The orchestrator owns all merge actions in
    both normal and `manual-merge` modes.
11. Optional PR notes. Add `## Notes` only for non-blocking adjacent observations:
    duplicate helpers, suspicious test gaps, drift, or cleanup ideas. Anything
    required for this child acceptance criteria must be fixed or returned as
    `STATUS=fail REASON=<short>`, never hidden in notes.
12. Reply exactly:
    `STATUS=ok PR=$PR SHA=<full-sha>` or `STATUS=fail REASON=<short>`.

## Hard rails

- Touch only your issue, PR, and branch (`epic-<N>-<child>-*`, author you).
- Never push to main, deploy, restart daemons, close issues, or edit sibling
  branches.
- Diff must trace to the issue scope.

## Bail

Bootstrap exits non-zero twice → exit immediately with
`STATUS=fail REASON=bootstrap-failed`. No PR, no comment.

For `verify-pr`, integrity, or AC failure: comment on PR and exit failed.

If focused tests stay red after two diagnosis attempts, bail immediately.
Bail after three unchanged pytest repeats, five edits to one file without convergence, or confusing git state. For confusing git, paste
`git status` and `git branch -vv`; exit `STATUS=fail REASON=worktree-corruption`.

## PR body template

```markdown
## Summary
<≤2 bullets>

## Test evidence
`<last 3 lines of pytest output>`

## Notes
- Optional non-blocking adjacent observation.

Closes #<child>
```
