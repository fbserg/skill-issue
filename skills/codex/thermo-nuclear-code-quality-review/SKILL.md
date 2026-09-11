---
name: thermo-nuclear-code-quality-review
description: Run an extremely strict maintainability review for abstraction quality, giant files, and spaghetti-condition growth. Use for a thermo-nuclear code quality review, thermonuclear review, deep code quality audit, or especially harsh maintainability review.
disable-model-invocation: true
---

# Thermo-Nuclear Code Quality Review

Use this skill for an unusually strict review focused on implementation quality, maintainability, abstraction quality, and codebase health.

Above all, this skill should push the reviewer to be **ambitious** about code structure. Do not merely identify local cleanup opportunities. Actively search for "code judo" moves: restructurings that preserve behavior while making the implementation dramatically simpler, smaller, more direct, and more elegant.

## Core Prompt

Start from this baseline:

> Perform a deep code quality audit of the current branch's changes.
> Rethink how to structure / implement the changes to meaningfully improve code quality without impacting behavior.
> Work to improve abstractions, modularity, reduce Spaghetti code, improve succinctness and legibility.
> Be ambitious, if there is a clear path to improving the implementation that involves restructuring some of the codebase, go for it.
> Be extremely thorough and rigorous. Measure twice, cut once.

## Review Dimensions

Do not approve merely because behavior seems correct or tests pass. For each dimension below, treat the "Blocks approval when" condition as a presumptive blocker unless the author can justify it clearly.

| Dimension | Red flag | Remedy | Blocks approval when |
|---|---|---|---|
| Ambitious restructuring / code-judo | Working code that leaves an obvious simplification undone; a refactor that moves complexity around without deleting it; "temporary" branching likely to become permanent debt. | Delete a whole layer of indirection instead of polishing it; reframe the state/model so conditionals disappear; collapse duplicate branches into one flow. | A plausible code-judo move would delete complexity the PR instead preserves, or there is a visible path to a dramatically simpler implementation. Good phrase: "i think there's a code-judo move here that makes this much simpler. can we reframe this so these branches disappear?" |
| 1k-line file growth | A file crosses 1000 lines because of this PR, especially when the new code could be split out. | Extract a helper or pure function; split the file into smaller focused modules. | The PR pushes a file from under 1000 lines to over 1000 lines, or skips an obvious decomposition, without a compelling structural reason. Good phrase: "this pushes the file past 1k lines. can we decompose this first?" |
| Spaghetti / ad-hoc conditionals | New conditionals bolted onto unrelated code paths; one-off booleans or nullable modes; narrow edge cases stuffed into an already busy function. | Replace condition chains with a typed model or explicit dispatcher; turn special-case logic into a simpler default flow. | The PR adds ad-hoc branching that makes an existing flow more tangled. Good phrase: "this adds another special-case branch into an already busy flow. can we move this behind its own abstraction?" |
| Thin wrappers / casts / optionality | Identity wrappers or generic "magic" handling that add indirection without clarity; unnecessary casts, `any`, `unknown`, or optional params that muddy the real contract. | Delete wrappers that don't meaningfully clarify the API; make type boundaries more explicit so the control flow simplifies. | The PR adds an unnecessary abstraction, wrapper, or cast-heavy contract that makes the design more indirect. |
| Canonical-helper reuse | Feature-specific logic leaking into general-purpose modules; copy-pasted logic instead of an extracted helper; a bespoke helper built where a canonical one already exists. | Reuse the existing canonical helper; move logic to the package/module/layer that already owns the concept. | The PR duplicates an existing helper or puts logic in the wrong layer despite a clear canonical home, or solves a local problem by scattering feature checks across shared code. |
| Sequential / non-atomic orchestration | Independent work serialized for no reason; related updates that can leave state half-applied. | Parallelize independent work; separate orchestration from business logic; restructure related updates into one atomic flow. | The change leaves state less atomic than necessary, or serializes clearly independent work, without justification. |

Do not be satisfied with "maybe rename this" feedback when the real issue is structural. Do not be satisfied with a merely cleaner version of a messy idea if a much simpler idea is plausible.

## Review Tone

Be direct, serious, and demanding about quality.
Do not be rude, but do not soften major maintainability issues into mild suggestions.
If the code is making the codebase messier, say so clearly.
If the implementation missed an opportunity for a dramatic simplification, say that clearly too.

## Output Expectations

Prioritize findings in this order:

1. Structural code-quality regressions
2. Missed opportunities for dramatic simplification / code-judo restructuring
3. Spaghetti / branching complexity increases
4. Boundary / abstraction / type-contract problems that make the code harder to reason about
5. File-size and decomposition concerns
6. Modularity and abstraction issues
7. Legibility and maintainability concerns

Do not flood the review with low-value nits if there are larger structural issues.
Prefer a smaller number of high-conviction comments over a long list of cosmetic notes.
