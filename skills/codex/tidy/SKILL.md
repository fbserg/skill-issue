---
name: tidy
description: Code-quality review: fix LLM slop and over-engineering. Run before commits.
user-invocable: true
---

# tidy — anti-slop pass on changed code

All code in this user's repos is LLM-written. The default failure mode isn't bugs, it's **over-writing**: phantom abstractions, defensive theater, comment slop, scaffolding for futures that won't arrive, control-flow ceremony. This skill hunts that aggressively.

## Scope

Changed lines only — `git diff` against the base branch (or staged + unstaged if not on a feature branch). Read nearby context when needed, but don't review unchanged code.

## The four lenses

Run these over the diff. Most fixes should come from lens 1 or 2. Keep moving; this is a pre-commit cleanup pass, not a full audit.

1. **Delete junk** — comment slop, tombstones, fake compatibility, unused exports, `_deprecated` / `_unused` renames, feature flags for one-off changes, defensive try/catch, null checks against values that can't be null, fallbacks for cases that can't happen. Delete it.
2. **Flatten ceremony** — helpers used once, options-bags with one option, classes wrapping two functions, factories for one concrete type, ceremonial names (`UserAuthenticationServiceManager` for a 12-line file), nested ternaries, 3+ levels of `if`/`else`, deep early-exit pyramids. Inline, rename locally, or flatten.
3. **Reuse existing things** — new code that duplicates an existing helper, business rule, route string, schema shape, env var name, error message, validation rule, SDK type, or project utility. Prefer the existing path. If the reuse crosses files or changes public shape, surface it with `file:line` instead of fixing.
4. **Protect behavior/tests** — simplification must not change public behavior, serialized output, generated text, API shape, file formats, CLI output, user-visible copy, or test intent unless the task explicitly asked for that. Flag obvious test bloat: five tests for a getter, mocking your own code, asserting framework behavior, or tests that pass without exercising the change.

## Output contract

For each auto-fix, emit:

```
[SEVERITY conf N] path:line — short summary
  fix: fixed
```

For each surfaced finding, emit:

```
[SEVERITY conf N impact high|med|low effort small|med|large] path:line — short summary
  fix: what to do
```

**Severity:**
- **CRITICAL** — slop that ships a bug or misleads a future reader (wrong-named helper, dead error path masking real failures)
- **IMPORTANT** — clear over-writing the user would want gone (phantom abstraction, defensive theater)
- **NIT** — style-level (redundant comment, ceremonial wrapper, mild nesting)

**Confidence (1–10):**
- 9–10: verified — read the surrounding code, confirmed the claim
- 7–8: high-confidence pattern match
- 5–6: plausible, show with caveat ("if X is true, then…")
- <5: drop unless CRITICAL

Show 7+. Demote 5–6 to a "maybe" subsection. Drop <5 unless CRITICAL.

## Fix policy

**Auto-fix aggressively when local and high-confidence:**
- Delete comment slop, tombstones, dead scaffolding, fake compatibility, useless defensive checks, and rethrow-only try/catch.
- Inline single-use helpers when the call site is obvious.
- Flatten contained control flow inside one function without changing signature or behavior.
- Replace bespoke code with an existing helper when the helper is in the same file or the import path is already present.
- Remove or merge obviously redundant tests only when the remaining test still exercises the changed behavior.

**Surface, don't fix:**
- Cross-file reuse misses
- Business-rule, schema, route, env var, or error-message dedupe
- Public renames, signature changes, import graph reshaping, or generated output changes
- Test bloat where coverage intent is a judgment call
- Control-flow changes that touch multiple functions or change behavior shape
- Anything confidence <8

## Reporting

Keep the report short. Group findings in this order:

**Fixed** — auto-applied changes. One line each.

**Flagged** — judgment calls or larger changes. Include impact + effort. One line each.

**Looks bad but is fine** — patterns that pattern-matched as slop but were intentional after reading context. One line each. Suppresses re-flagging on the next run.

**Open questions** — findings that hinged on "if X is true." Phrase as a question, not a low-confidence finding.

Then a one-line tally: `tidy: N fixed, M flagged`. If nothing found, say so — don't pad.
