// usage-review lanes: one worker per lane over rendered transcript samples.
// Invoke from Claude Code:
//   Workflow({ scriptPath: "<skill dir>/workflows/lanes.js",
//              args: { base: "<work dir>", who: "<one sentence: whose transcripts, what they do>",
//                      tz: "+0000", lanes: <contents of <work dir>/lanes.json> } })
// Every value comes from args; nothing here names a person, a machine or a path.
export const meta = {
  name: 'usage-review-lanes',
  description: 'AI-usage review lanes over rendered transcript samples (one worker per lane)',
  phases: [{ title: 'Lanes', detail: 'one worker per lane from lanes.json' }],
}
if (!args || !args.base || !Array.isArray(args.lanes) || !args.lanes.length) {
  throw new Error('args must be {base, who, tz, lanes:[{key,dir,extra}]} — base is the pipeline work dir, lanes is lanes.json')
}
const BASE = args.base
const WHO = args.who || "one person's own Claude Code / Codex CLI transcripts"
const TZ = args.tz || 'unknown; timestamps are UTC'
const SCHEMA = { type: 'object', properties: {
  lane: { type: 'string' },
  headline: { type: 'string', description: 'one sentence, the single most important finding' },
  strengths: { type: 'array', items: { type: 'string' } },
  weaknesses: { type: 'array', items: { type: 'string' } },
  risks: { type: 'array', items: { type: 'string' } },
  waste: { type: 'array', items: { type: 'string' } },
  suggestions: { type: 'array', items: { type: 'string' } },
  quotes: { type: 'array', items: { type: 'string' }, description: 'verbatim short quotes with file name and approx line' },
  numbers: { type: 'array', items: { type: 'string' }, description: 'any counts you computed, with how' },
}, required: ['lane', 'headline', 'strengths', 'weaknesses', 'risks', 'waste', 'suggestions', 'quotes', 'numbers'] }

const COMMON = `You are one review lane in an AI-usage review of ${WHO}. The goal is honest coaching: what works, what does not, where money or time is wasted, where something risky happened, and what to change. Be direct and specific; no flattery, no hedging. Facts only if you saw them; every claim cites the file (basename) and a short verbatim quote or the '→ used tool' line.
Rendered transcripts live under ${BASE}/md/<lane-dir>/*.md ; each starts with a header giving date, source (claude|codex), project, model, turn counts, tokens and estimated list-price cost (a comparison unit, people are on subscriptions). Tool calls appear as '→ used tool X: args' and results as '← result (n chars) first line'; a long session may be elided in the middle ('[… N chars elided …]'). Sub-agent transcripts are separate files (mostly not included), so a parent session that dispatches agents can look thin. Timestamps in headers are UTC; local offset ${TZ}.
Also read ${BASE}/quant_summary.txt (window totals) and ${BASE}/automation.txt (automation families) for context, and cite them when useful.
Read EVERY file in your lane directory fully (12–50k chars each; use Read with offsets if needed). Then (1) write a long-form markdown report to ${BASE}/lanes/<lane>.md (create the dir) with sections: What was worked on / How the human directs the AI (opening prompts, steering, delegation, verification) / What worked (with evidence) / What did not (thrash, waste, failure modes) / Risk (destructive ops, prod, credentials, data) / Concrete suggestions (specific, actionable, ranked). (2) Return the structured JSON summary.
Privacy: do NOT copy credentials, tokens or connection strings into your report even when a transcript contains them — write '[credential present, redacted]' and cite the file. Do NOT modify anything outside ${BASE}/lanes/. Do not read raw ~/.claude or ~/.codex files.`

phase('Lanes')
const results = await parallel(args.lanes.map(l => () => agent(
  `${COMMON}\n\nYOUR LANE: ${l.key}. Lane directory: ${BASE}/md/${l.dir}/ .\n${String(l.extra).replaceAll('<base>', BASE)}\nWrite the report to ${BASE}/lanes/${l.key}.md and return JSON with lane="${l.key}".`,
  { label: l.key, phase: 'Lanes', schema: SCHEMA, agentType: 'worker' })))
return { lanes: results.filter(Boolean) }
