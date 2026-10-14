## 2026-10-14 — Context diet: /issue deleted for Claude, usage-review hidden from the model

**Decision:** `skills/claude/issue` is deleted. It was an alias for
`/resolve-issue <N>` plus "file the issue first", which needs no skill. Use
`/resolve-issue <N>` directly. The Codex `issue` front door is unchanged.
`usage-review`, `zero` and `simplify-sweep` stay installed but are set to
`user-invocable-only` in `skillOverrides` (etc `configs/*/claude/settings.json`),
so they cost no listing tokens and still run when typed. This narrows the
2026-08-19 usage-review ruling to "kept, user-typed only". Descriptions of
blitz, resolve-issue and epic-plan were shortened.

**Evidence:** 60 days of oracle-dev transcripts: `issue` 5 invocations,
`resolve-issue` 11, `blitz` 10, `epic-plan` 13, `usage-review` 0. Owner asked
for the cut on 2026-10-14.

**Reopen when:** free-text issue filing goes wrong without the scoping step.
