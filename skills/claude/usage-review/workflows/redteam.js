// usage-review red team: one refuter per claim cluster, then one adjudicator per cluster with contested parts.
// Invoke from Claude Code:
//   Workflow({ scriptPath: "<skill dir>/workflows/redteam.js",
//              args: { base: "<work dir>", who: "<one sentence>", tz: "+0000",
//                      clusters: [{cluster, hint, claims: [..]}] } })   // shape: examples/claims.example.json
// Every value comes from args; nothing here names a person, a machine or a path.
export const meta = {
  name: 'usage-review-redteam',
  description: 'Adversarial verification of AI-usage review claims, then adjudication of contested ones',
  phases: [{ title: 'Refute', detail: 'one refuter per claim cluster' }, { title: 'Adjudicate', detail: 'one adjudicator per cluster with contested parts' }],
}
if (!args || !args.base || !Array.isArray(args.clusters) || !args.clusters.length) {
  throw new Error('args must be {base, who, tz, clusters:[{cluster, hint, claims:[...]}]} — see examples/claims.example.json')
}
const BASE = args.base
const WHO = args.who || "one person's own Claude Code / Codex CLI transcripts"
const TZ = args.tz || 'unknown; timestamps are UTC'
const RAW = 'the raw transcripts under ~/.claude/projects and ~/.codex/sessions (read-only; jsonl, can be tens of MB — use grep/python)'
const VERDICT = { type: 'object', properties: {
  cluster: { type: 'string' },
  verdicts: { type: 'array', items: { type: 'object', properties: {
    claim: { type: 'string' }, verdict: { type: 'string', enum: ['verified', 'partially', 'refuted', 'unverifiable'] },
    evidence: { type: 'string', description: 'file(s) + line/quote or the numbers you recomputed' },
    correction: { type: 'string', description: 'if partially/refuted: what the claim should say' } }, required: ['claim', 'verdict', 'evidence', 'correction'] } },
  notes: { type: 'string' } }, required: ['cluster', 'verdicts', 'notes'] }
const DECISION = { type: 'object', properties: { cluster: { type: 'string' }, decisions: { type: 'array', items: { type: 'object', properties: {
  claim: { type: 'string' }, side: { type: 'string', enum: ['report', 'refuter', 'both'] }, final_wording: { type: 'string' }, evidence: { type: 'string' } },
  required: ['claim', 'side', 'final_wording', 'evidence'] } } }, required: ['cluster', 'decisions'] }

const COMMON = `You are a red-team refuter for a review of ${WHO}. Your job is to DISPROVE the claims you are given: find errors, misreadings, over-generalisation from thin samples, wrong numbers, wrong attributions. Be adversarial and concrete; say 'partially' or 'refuted' only with evidence, 'unverifiable' when the source is not available to you.
Sources: ${BASE}/sessions.jsonl (one row per transcript: path, source, nested, project, session_id, first_ts/last_ts, models, tok{model:[input,cache_write,cache_read,output]}, user_turns, assistant_turns, tools, first_prompt, cost_new, cost_full, new_tokens, cache_read, out_tokens, api_errors, interrupts, short_openers, originator, reasoning_effort), ${BASE}/quant_summary.txt, ${BASE}/automation.txt, ${BASE}/cmd_stats.json, ${BASE}/risky_digest.md, ${BASE}/graded.jsonl (if present), ${BASE}/lanes_result.json and ${BASE}/lanes/*.md (what the lanes said — treat as claims, not evidence), rendered transcripts under ${BASE}/md/<lane>/*.md (each file header names its raw source path). You MAY read ${RAW} when a claim cites a session id or the rendered file is elided.
Read-only everywhere: do not create, modify or delete anything except ${BASE}/redteam/<cluster>.md where you write your notes (mkdir -p). Never copy credentials into your notes. Cost model: list price per M tokens opus/fable 15 in, 75 out, 18.75 cache-write, 1.5 cache-read; sonnet 3/15/3.75/0.3; haiku 1/5/1.25/0.1; codex gpt 1.25/10/1.25/0.125. Timestamps are UTC; local offset ${TZ}. Return one verdict per claim (split a claim into parts if parts differ; keep the claim text you were given, append '[part]' labels).`

phase('Refute')
const results = await pipeline(args.clusters,
  c => agent(`${COMMON}\n\nCLUSTER: ${c.cluster}\nHINT: ${c.hint || ''}\nCLAIMS:\n${c.claims.map((x, i) => `${i + 1}. ${x}`).join('\n')}\n\nWrite notes to ${BASE}/redteam/${c.cluster}.md and return the JSON.`,
    { label: `refute:${c.cluster}`, phase: 'Refute', schema: VERDICT, agentType: 'worker' }),
  (r, c) => {
    if (!r) return null
    const contested = r.verdicts.filter(v => v.verdict !== 'verified')
    if (!contested.length) return { cluster: c.cluster, refuter: r, adjudication: null }
    return agent(`You are an adjudicator. A report made claims; a refuter contested some. Decide each contested part on the evidence: side with the report, the refuter, or both-partly, and state the exact corrected wording. Verify against the same sources yourself (do not take either side's word): ${BASE}/sessions.jsonl, ${BASE}/md/**, ${BASE}/graded.jsonl, ${BASE}/automation.txt, ${BASE}/risky_digest.md, ${RAW}. Read the refuter's notes at ${BASE}/redteam/${c.cluster}.md. Write your notes to ${BASE}/redteam/${c.cluster}-adjudicated.md. Read-only otherwise; never copy credentials into notes. Timestamps are UTC; local offset ${TZ}.\n\nCLUSTER: ${c.cluster}\nCONTESTED:\n${JSON.stringify(contested, null, 1)}\n\nReturn JSON: {cluster, decisions:[{claim, side:'report'|'refuter'|'both', final_wording, evidence}]}`,
      { label: `adjudicate:${c.cluster}`, phase: 'Adjudicate', agentType: 'worker', schema: DECISION })
      .then(a => ({ cluster: c.cluster, refuter: r, adjudication: a }))
  })
return { results: results.filter(Boolean) }
