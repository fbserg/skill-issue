# Codex builder lane — shared contract

The write-phase pattern for handing a plan to Codex as the builder while a
Claude lane-runner owns git/PR mechanics and verification. Referenced by
`/resolve-issue` (Step 1 implementer, Step 3 fixer) and by `/codex-go`
(which predates this doc and carries its own fuller shell-script version —
`codex-go.md` lives outside this repo, unversioned, so it isn't wired to
reference this file directly; keep the two in sync by hand if either
changes).

## Canary before dispatch

`codex exec --skip-git-repo-check "print ok and exit"` — healthy returns
"ok" in ~3s. Fails or times out → don't dispatch into a dead backend; fall
back to a plain Sonnet builder (note the fallback in the handoff) or stop
and report, per the caller's own fallback rule.

## The task file — self-contained, no memory of this chat

Write to a scratch path (caller-specific). It needs: goal, files to touch,
**exact symbols/helpers to reuse with signatures** (the highest-leverage
part — names the functions/utilities instead of letting Codex reinvent
them), steps, how to verify. Copy in any repo-specific rulings (CLAUDE.md
invariants) that bind the diff — Codex reads only AGENTS.md on its own, so a
CLAUDE.md-only rule never reaches it unless transcribed here.

Include, verbatim, every time:

- **No-git block:** *"Do NOT git add/commit/push/reset/checkout/stash or
  create branches. Edit and test only; leave changes unstaged."* (
  `--full-auto` commits on its own otherwise, muddling attribution on a busy
  branch — committing is the orchestrator's job.)
- **Contradiction-stop block:** *"If the spec contradicts itself or two
  requirements cannot both hold: STOP, write the contradiction and your
  recommended resolution, implement NOTHING."* (Verified: a seeded conflict
  produces a written dispute and zero code, not a silently-resolved guess.)
- **No-tests rule** (implementer only — a separate agent authors tests):
  code only, no test files.
- **Sandbox-has-no-network warning**, with the repo's offline escape hatch —
  socket-bind/DNS/network tests fail spuriously inside the sandbox; without
  this the self-report means nothing.

## Launch with a watchdog

Background dispatch, default 1200s timeout, per the cadence and remediation
rules in `docs/lane-watchdog.md`.

## Verify for real — never trust Codex's self-report

Measured failure modes: it fixes the reported case and misses the symmetric
one; it dismisses its own regressions as "environmental." Run the plan's
verify step yourself, probe neighboring/symmetric cases, reproduce any
claimed failure before accepting the result. A contradiction-stop → surface
it in the handoff, implement nothing yourself either — that's a plan defect,
not a builder failure to route around.

## Commit discipline

Commit exactly what the plan/finding list called for — diff first, never
`git add -A` blindly.
