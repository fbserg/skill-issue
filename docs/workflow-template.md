# Workflow script template

Copy-paste starting point for a new `Workflow` script. Matches the real
harness idioms used in `skills/claude/deep-research/workflow.js`: top-level
`export const meta`, `phase()`, `await agent(prompt, opts)`,
`await parallel([...])`, `await pipeline(...)`, `log()`, `budget`. No
`Date.now`/`Math.random` (non-deterministic across replays), no filesystem
calls in the script itself — state lives in the returned object and in
`log()` lines, not on disk.

## Contract

Each clause below traces to a measured failure; the template encodes the
fix, not just the rule.

1. **`agentType` on every `agent()` call, always.** A bare `agent()` inherits
   the *session's* effort — several top-cost transcripts show a low-effort
   parent silently downgrading every spawn. Route every call through one
   local helper (`run`, below) instead of calling `agent()` directly. Pick
   the agent type per `docs/subagent-model-effort.md`: `bulk` for mechanical
   fan-out, `worker` as the default, `opus-worker` only for a single
   escalation or convergence step — never a blanket fan-out.
2. **Capability pre-check before fan-out.** A 6-agent wave launched with an
   agent type that had no MCP tools came back empty, not errored — a missing
   tool fails silent. Declare `REQUIRED_TOOLS` per lane kind and run one
   cheap probe agent per distinct `(agentType, tool-set)` that calls
   `ToolSearch` to confirm the tools resolve, before spending the wave.
3. **Rate-limit fallback, not a retry loop.** `agent()` returns `null` for a
   dead or skipped agent (rate limits included) — after a session-limit hit,
   one transcript repeated the same error 4 times and produced nothing.
   Count consecutive nulls; N in a row stops launching more and returns
   `{status:'rate_limited', inflight:[...], done:[...]}` so the caller can
   persist in-flight state and hand back to a human. Never retry blind.
4. **Name zero-output lanes in the wave summary.** A 17-lane harvest had one
   silently empty lane, found only by parsing raw output JSON afterward.
   After each wave, `log()` `wave N: k ok, m empty (ids), z null (ids)`.
   Empty is schema-defined per script — e.g. zero `findings` AND no `notes`
   — not just falsy.
5. **No polling from the caller.** Workflow scripts themselves don't poll,
   but one transcript made 13,144 `wait_agent` calls at 30s anyway by
   looping on the *caller* side. Run the Workflow in the background and rely
   on the completion notification, or a `Monitor` per
   `docs/lane-watchdog.md` — never a `TaskOutput`-style wait loop.

**Structured output:** pass `schema` on `agent()` calls that need a shape
(`PROBE_SCHEMA` / `ITEM_SCHEMA` below) with a `required` array — schemas
without `required` let partial results through the return-value contract
silently. Two `StructuredOutput` schema failures were measured in an
email-classify sample; the fix that held was a tighter schema plus a golden
test in the calling repo, not a looser one — schema failures retry at the
tool layer, they are not this script's problem to swallow.

## Template

```js
export const meta = {
  name: 'TEMPLATE',
  description: 'Capability-checked fan-out with a rate-limit stop and a named wave summary. Replace before shipping.',
  whenToUse: 'Starting point only — adapt phases, schemas, and REQUIRED_TOOLS to the real task.',
  phases: [
    { title: 'Probe', detail: 'One cheap agent per (agentType, tool-set) confirms required tools resolve before spending the wave' },
    { title: 'Wave',  detail: 'Fan out via parallel(); null/empty lanes are named in the summary, not silently dropped' },
  ],
}

// Contract #1: every spawn names agentType — bare agent() inherits the
// session's often-low effort (docs/subagent-model-effort.md).
const run = (prompt, opts = {}) => agent(prompt, { agentType: 'worker', ...opts })

// Contract #2: declare required tools per lane kind before fan-out.
const REQUIRED_TOOLS = { worker: ['Read', 'Write', 'Bash'] }
const PROBE_SCHEMA = { type: 'object', required: ['ok', 'missing'], properties: {
  ok: { type: 'boolean' }, missing: { type: 'array', items: { type: 'string' } },
}}

phase('Probe')
for (const [agentType, tools] of Object.entries(REQUIRED_TOOLS)) {
  const probe = await run(
    'Call ToolSearch to confirm each of these resolves: ' + tools.join(', ') + '. ' +
    'ok=true only if every tool was found; else ok=false with missing listed.\n\nStructured output only.',
    { agentType, label: 'probe:' + agentType, phase: 'Probe', schema: PROBE_SCHEMA }
  )
  if (!probe || !probe.ok) {
    log('Probe failed for ' + agentType + ': ' + (probe ? probe.missing.join(', ') : 'no result — treat as missing'))
    return { status: 'capability_check_failed', agentType, missing: probe ? probe.missing : ['unknown'] }
  }
}
log('Probe: all required tools resolved for ' + Object.keys(REQUIRED_TOOLS).join(', '))

// Contract #3: consecutive-null tracking — stop launching, don't retry blind.
let consecutiveNulls = 0
const NULL_STOP_THRESHOLD = 3
function noteResult(result) {
  consecutiveNulls = result === null ? consecutiveNulls + 1 : 0
  return consecutiveNulls < NULL_STOP_THRESHOLD
}

const ITEM_SCHEMA = { type: 'object', required: ['findings'], properties: {
  findings: { type: 'array', items: { type: 'string' } }, notes: { type: 'string' },
}}
const isEmpty = r => Array.isArray(r.findings) && r.findings.length === 0 && !r.notes

const items = [{ id: 'a' }, { id: 'b' }, { id: 'c' }] // replace with real lane inputs
const done = []

phase('Wave')
const results = await parallel(items.map(item => () =>
  run('Do the lane task for ' + item.id + '.\n\nStructured output only.',
    { label: 'lane:' + item.id, phase: 'Wave', schema: ITEM_SCHEMA }
  ).then(r => ({ item, r, keepGoing: noteResult(r) }))
))

// Contract #4: name every zero-output lane, don't just count it.
const ok = [], empty = [], nulls = []
for (const { item, r, keepGoing } of results) {
  if (r === null) nulls.push(item.id)
  else if (isEmpty(r)) empty.push(item.id)
  else { ok.push(item.id); done.push({ id: item.id, ...r }) }
  if (!keepGoing) {
    log('wave 1: stopping — ' + NULL_STOP_THRESHOLD + ' consecutive nulls (possible rate limit)')
    return { status: 'rate_limited', inflight: items.map(i => i.id).filter(id => !done.some(d => d.id === id)), done }
  }
}
log('wave 1: ' + ok.length + ' ok, ' + empty.length + ' empty (' + empty.join(',') + '), ' + nulls.length + ' null (' + nulls.join(',') + ')')

return { status: 'ok', done }
```
