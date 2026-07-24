# Adversarial review panel — shared contract

The role-locked, multi-lens critique pattern used to stress-test something
before committing to it: an `epic-plan` decomposition, or a `resolve-issue`
code diff and its review findings. Referenced by both rather than restated —
the "frame the blocker as a prior reviewer's claim" trick and the
synthesis/severity rules are identical in both call sites; this is the one
place that defines them.

## Fan-out

Spawn the lenses **concurrently, one message**, each role-locked to attack
(never to validate) and each seeing none of the others' output — diverse
lenses, never N identical refuters. What the lenses actually are is
call-site-specific (see the caller for the list); this file only defines the
mechanics around them.

## Synthesis (no loops)

1. **Union the findings; dedup by area/file+description** — the same defect
   surfacing under two lenses collapses to one, keeping the highest severity.
2. **Severity by impact, not vote count.** A finding that invalidates the
   artifact (wrong ordering, a missing piece, something unbuildable/unmet) is
   a blocker even if only one lens raised it — the lenses are orthogonal by
   design, so a real defect often lives in exactly one lens's domain.
   Everything else is advisory / should-fix / nit.
3. **One re-check per blocker**, on a fresh context. Skip should-fix and nits
   entirely — verifying a nit costs more than the nit.

## The re-check framing

Frame the blocker as **a prior reviewer's external claim** — "a prior
reviewer concluded X; find the flaw in that reasoning" — not as the
skeptic's own finding to second-guess. Evaluating an external claim is
cleaner than introspecting your own, and it costs nothing to word it that
way.

- **Where the claim is checkable against the repo** (does the file overlap
  exist? does the consumer actually consume? does the code do what the
  finding says?), the re-check **must verify against the code**, not argue
  rhetorically. A blocker that can't survive this verification is downgraded
  or dropped, with the reason recorded.
- **Only genuinely unverifiable claims** (premortem-style: "reconstruct how
  this shipped and failed") get the external-claim framing as their entire
  method, since there's no code to check against.

## Revise once

Apply the upheld blockers to the artifact in a single revision pass.
Advisories are nudges, not gates — they inform the author, they never block.
