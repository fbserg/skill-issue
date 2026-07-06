# Pinning model & effort for subagents

**Problem:** subagents inherit the *session's* effort level by default. If your main thread runs at low effort (common when an expensive model orchestrates), every `Task`/`Agent` spawn, every Workflow `agent()` call, and every built-in agent type (`general-purpose`, `Explore`, `Plan`, `claude`) silently runs at **low effort** too — even if you pass `model: "sonnet"`. Passing a model alone does NOT fix effort.

**Solution:** define named agent types with both `model` and `effort` pinned in frontmatter, and route ALL delegation through them.

## Agent definitions (`~/.claude/agents/*.md`)

```markdown
---
name: worker
description: Default delegate for implementation, review, and research that needs writes.
model: sonnet
effort: medium
---

You are a focused worker agent. Do the work yourself with your own tools — do not
spawn subagents. Implement, test, and verify the task end-to-end. Your final message
is returned to the orchestrator as raw data: report exactly what you did, what you
observed (test output, file paths, errors), and anything left unresolved.
```

The two load-bearing lines are `model:` and `effort:` — frontmatter pins both regardless of what the parent session runs at.

## A working tier set

| Type | Model / effort | Use for |
|---|---|---|
| `bulk` | haiku / low | Mechanical fan-out: bulk reads, summaries, transforms. High volume, low judgment. |
| `worker` | sonnet / medium | Default delegate: implementation, review, research with writes. |
| `explore-mid` | sonnet / medium | Read-only research fan-out when depth matters (tools restricted to read/search). |
| `opus-worker` | opus / medium | Two narrow uses: (1) escalation — a single stuck subtask after Sonnet failed; (2) a single high-leverage **convergence step** (final synthesis, judge-panel verdict, one critical fix) where one call carries the result. Never first attempts, never blanket fan-outs. |

Restrict tools where it helps, e.g. read-only research:

```yaml
tools: Bash, Glob, Grep, Read, WebFetch, WebSearch, LSP, ToolSearch
```

## Rules that make it stick

- **Every spawn names a custom type.** Built-in `general-purpose` / `Plan` / `claude` inherit session effort — use `worker` instead. Built-in `Explore` is acceptable only for cheap lookups where low effort is fine.
- **Workflow scripts:** bare `agent()` runs at low effort. Always pass `agentType`:

  ```js
  await agent(prompt, { agentType: 'worker' })   // or 'bulk' / 'opus-worker'
  ```

- **Headless caveat:** `claude --agent X -p` does **NOT** apply frontmatter effort — the pin only works for subagent spawns from a live session.
- **Don't blanket-upgrade a fan-out to Opus.** `opus-worker` is for exactly one call: either escalating a single stuck subtask, or running a single convergence step (synthesis, panel verdict, one critical fix) where one call carries the whole result. Never re-run Sonnet on the same failure, never start a fresh task at Opus, never use it for per-item grading fan-outs.
- **System prompts end with a return-contract.** Subagent final messages go to the orchestrator, not a human — instruct them to return raw findings/results, and forbid them from spawning their own subagents.

## Verifying what actually ran

Check the frontmatter directly — it's the source of truth:

```bash
head -8 ~/.claude/agents/worker.md
```

To confirm at spawn time, the Agent tool's available-types listing reflects the registry; if a type isn't listed, the frontmatter never loaded (bad YAML, wrong directory).

## Install

Ready-made definitions for all four types live in this repo under `agents/`. `scripts/install.sh` now symlinks them into `~/.claude/agents/` automatically alongside the skills — no manual copy step needed. Then add a CLAUDE.md rule so the orchestrator routes through them, e.g.:

> Delegation goes through named agent types: `bulk` (haiku/low) for mechanical fan-out, `worker` (sonnet/medium) as the default delegate, `opus-worker` (opus/medium) only as escalation for a single stuck subtask, `explore-mid` (sonnet/medium) for research fan-out when depth matters. These carry `effort: medium` so subagents don't inherit the main thread's low effort — passing `model:` alone is not sufficient.
