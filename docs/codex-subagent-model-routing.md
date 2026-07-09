# Codex subagent model routing

This runbook gives another Codex enough information to install task-specific subagent models and prove that the routing actually happened. It deliberately treats model self-reports as untrusted.

## What is portable

Current Codex documentation supports personal custom agents in `~/.codex/agents/` and project-scoped agents in `.codex/agents/`. Each standalone TOML file requires `name`, `description`, and `developer_instructions`; it may also set `model` and `model_reasoning_effort`.[1]

Model availability is account- and client-dependent. Inspect the installed model catalog before writing agent files. The public starting points are `gpt-5.6` for demanding work and `gpt-5.6-terra` for faster, lower-cost supporting work.[1] Note that the bare `gpt-5.6` slug the documentation recommends may not appear in `codex debug models` at all — on Codex CLI 0.144.0 the catalog exposes only the family variants (`gpt-5.6-sol`, `gpt-5.6-terra`, `gpt-5.6-luna`). When that is the case, skip the portable policy and go straight to the family-specific mapping.

Subagents inherit the parent turn's live sandbox and approval choices. Do not claim that an agent is read-only merely because its TOML contains `sandbox_mode = "read-only"`; verify the effective child policy from its rollout or with a harmless permission probe.[1]

## Routing policy

Use this portable policy unless the live catalog exposes more specific models:

| Agent | Work | Portable model | Effort |
|---|---|---|---|
| `explorer` | Search, mapping, inventory, narrow factual checks | `gpt-5.6-terra` | `low` |
| `worker` | Focused implementation and tests | `gpt-5.6-terra` | `medium` |
| `reviewer` | Diagnosis, correctness, architecture, adversarial review | `gpt-5.6` | `high` |
| `deep_reviewer` | Hard ambiguous investigations and high-risk final review | `gpt-5.6` | `xhigh` |

If `codex debug models` lists `gpt-5.6-luna`, `gpt-5.6-terra`, and `gpt-5.6-sol` with the required effort levels, the intended family-specific mapping is:

| Agent | Model | Effort |
|---|---|---|
| `explorer` | `gpt-5.6-luna` | `low` |
| `worker` | `gpt-5.6-terra` | `medium` |
| `reviewer` | `gpt-5.6-sol` | `high` |
| `deep_reviewer` | `gpt-5.6-sol` | `xhigh` |

Never install a model or effort value absent from the live catalog.

## Installation instructions for Codex

Give the following task to Codex:

> Configure personal subagent routing using the official standalone-agent format. First record `codex --version` and inspect `codex debug models`. Create `~/.codex/agents/explorer.toml`, `worker.toml`, `reviewer.toml`, and `deep_reviewer.toml`. Every file must contain `name`, a decision-oriented `description`, `developer_instructions`, `model`, and `model_reasoning_effort`. Use only models and effort levels present in the live catalog. Use the routing policy in this document. Do not add undocumented feature flags. Preserve unrelated configuration. Validate with `codex exec --strict-config`, then run the cold verification below.

Descriptions are routing instructions for the parent agent, so make the boundaries explicit.[1] Developer instructions define how the child behaves after selection.[1]

Keep global orchestration conservative:

```toml
[agents]
max_threads = 6
max_depth = 1
```

Codex defaults to six concurrent open agent threads and one level of child agents; deeper nesting increases cost and unpredictability.[1][2]

## Objective verification

A configuration passes only if all five gates pass.

### 1. Syntax and catalog gate

- `codex exec --strict-config` starts without a configuration error.
- Every configured model exists in `codex debug models`.
- Every configured effort appears in that model's `supported_reasoning_levels`.

### 2. Cold discoverability gate

Start a fresh, persisted Codex session. Do not reuse the installation conversation. Do not mention internal tool names.

Use this prompt:

> This is an explicit subagent test. Delegate one narrow repository-mapping question to the configured explorer. Wait for the child and return its exact response plus the child thread ID. Do not do the exploration in the parent. Do not claim success unless a child actually starts.

Pass only when the event stream contains a completed spawn event with a nonempty child thread ID. A parent answer, a `wait` call with no child IDs, or a claim that an agent ran is not proof.

### 3. Recorded configuration gate

Do not use `--ephemeral`; the child rollout is the evidence. Find the rollout whose filename ends with the child thread ID, then inspect its `turn_context` records.

```sh
child_id="<child thread ID>"
rollout=$(rg --files ~/.codex/sessions | rg "$child_id\\.jsonl$")
jq -c 'select(.type == "turn_context") | {
  model: .payload.model,
  effort: .payload.effort,
  sandbox: .payload.sandbox_policy.type,
  multi_agent_version: .payload.multi_agent_version
}' "$rollout"
```

Pass only when `model` and `effort` equal the agent file. The effective sandbox must match the parent turn's live permission policy unless the installed release demonstrably honors a narrower agent override.[1]

### 4. Four-role matrix gate

Run a fresh parent that explicitly asks for one child of each configured role. Give each child a unique response marker. Require all four child IDs and markers, then inspect every child rollout as above.

Expected matrix:

```text
explorer      -> configured fast model / low
worker        -> configured balanced model / medium
reviewer      -> configured strong model / high
deep_reviewer -> configured strong model / xhigh
```

### 5. Negative-control gate

Temporarily move one custom agent file out of the discovery directory, start another fresh session, and request that exact agent. The request must fail or fall back visibly; it must not produce the same supposedly configured child metadata. Restore the file afterward.

This proves the successful test used the custom agent rather than an inherited default or accidental model match.

## Shareability standard

Publish the setup only with:

- the Codex version;
- sanitized agent TOML files;
- the live model/effort matrix used for the test;
- cold-test parent and child IDs;
- extracted child `turn_context` evidence;
- explicit notes for any client-specific failures;
- at least three successful cold runs per role if claiming reliable automatic routing.

Do not publish internal tool names as required user instructions. A fresh Codex should route from the agent descriptions and a normal delegation request. If it works only after naming an implementation-specific spawn function, configuration assignment is verified but discoverability has failed.

## Known result on Codex CLI 0.144.0

Testing on 2026-07-09 produced a split result:

- Personal standalone-agent discovery passed. An explicitly selected `reviewer` child recorded `gpt-5.6-sol`, `high`, and the parent's live `read-only` sandbox in its persisted `turn_context`.
- The cold natural-language gate failed. The parent emitted `wait` with no child IDs, then claimed a fabricated child path. No spawn event existed.
- Project-scoped standalone discovery also failed in the clean temporary probe with `unknown agent_type`, despite being part of the documented surface. Similar tool-backed custom-agent discovery failures have been reported upstream.[3]
- The bare `gpt-5.6` slug from the documentation's recommendation was absent from this client's `codex debug models` catalog, so the portable policy table was uninstallable as written; the family-specific mapping was used instead.

Therefore this document is a verified installation and test procedure, not evidence that automatic routing works on every current client. A different machine or newer release must pass its own cold gate before claiming success.

## Sources

1. [OpenAI Codex: Subagents](https://developers.openai.com/codex/subagents) (308-redirects to `learn.chatgpt.com/docs/agent-configuration/subagents`)
2. [OpenAI Codex configuration schema](https://github.com/openai/codex/blob/main/codex-rs/core/config.schema.json)
3. [OpenAI Codex issue #15250: custom subagents inaccessible from tool-backed sessions](https://github.com/openai/codex/issues/15250)
