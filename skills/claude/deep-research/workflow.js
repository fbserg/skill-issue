export const meta = {
  name: 'deep-research',
  description: 'Dynamic deep-research harness — Opus plans sized angles with a guaranteed disconfirmation lens; Sonnet searches, fetches, and verifies with GRADE-lite evidence tiers; an Opus critic drives a bounded saturation loop; Opus reasons from first principles and writes the tiered report.',
  whenToUse: 'When the user wants a deep, multi-source, fact-checked research report on any topic. BEFORE invoking, check if the question is specific enough to research directly — if underspecified (e.g., "what car to buy" without budget/use-case/region), ask 2-3 clarifying questions to narrow scope. Then pass the refined question as args, weaving the answers in.',
  phases: [
    { title: 'Scope',      detail: 'Judge complexity → sized angle plan, ≥1 disconfirmation lens', model: 'opus' },
    { title: 'Search',     detail: 'One boundary-scoped WebSearch agent per angle' },
    { title: 'Fetch',      detail: 'URL-dedup → fetch sources → extract claims with evidence tiers' },
    { title: 'Verify',     detail: 'Central claims only, 1 skeptic each — refuted demotes to contested' },
    { title: 'Critic',     detail: 'Completeness critic — gaps trigger ≤2 targeted extra rounds', model: 'opus' },
    { title: 'Reasoning',  detail: 'First-principles passes over the verified claim pool (conditional)', model: 'opus' },
    { title: 'Synthesize', detail: 'Tiered findings, contested block, honest caveats', model: 'opus' },
  ],
}

// ─── Sizing & catalogs ───
const SIZING = {
  simple:   { maxAngles: 3, maxFetch: 6,  centralCap: 4, extraRounds: 0 },
  moderate: { maxAngles: 5, maxFetch: 12, centralCap: 6, extraRounds: 1 },
  complex:  { maxAngles: 8, maxFetch: 20, centralCap: 8, extraRounds: 2 },
}
const LENSES = [
  'broad-primary', 'mechanism', 'empirical-trials', 'contrarian-disconfirmation',
  'heterogeneity-subgroups', 'practitioner-folk-origin', 'historical-why-belief-exists', 'steelman-opposite',
]
const TIERS = ['rct_meta', 'rct', 'observational', 'mechanistic', 'expert_opinion', 'anecdote_folk']
const MAX_ANGLES_PER_EXTRA_ROUND = 4
const MIN_BUDGET_FOR_EXTRA_ROUND = 80000

const LENS_CATALOG =
  '- broad-primary: the mainstream/consensus answer and its strongest evidence\n' +
  '- mechanism: how/why it works (or fails) at a causal level\n' +
  '- empirical-trials: RCTs, meta-analyses, measured outcomes — what was actually tested\n' +
  '- contrarian-disconfirmation: why the consensus answer is WRONG — null results, failed replications, debunkings, failure conditions\n' +
  '- heterogeneity-subgroups: for whom/when does the answer flip — subpopulations, doses, contexts\n' +
  '- practitioner-folk-origin: what practitioners actually do, and where the folk belief came from\n' +
  '- historical-why-belief-exists: how the belief arose and spread (distinct from whether it is true)\n' +
  '- steelman-opposite: strongest possible case for the opposite conclusion'

const TIER_GUIDE =
  '- rct_meta: meta-analysis or systematic review of randomized trials\n' +
  '- rct: a single randomized controlled trial\n' +
  '- observational: cohort/case-control/cross-sectional/survey data\n' +
  '- mechanistic: causal/biological/physical reasoning, in-vitro, animal models — plausibility, not proof\n' +
  '- expert_opinion: authority statement without cited data\n' +
  '- anecdote_folk: personal accounts, testimonials, folk wisdom'

// ─── Schemas ───
const SCOPE_SCHEMA = {
  type: 'object', required: ['question', 'summary', 'complexity', 'needsEvidenceTiering', 'angles', 'reasoningSubquestions'],
  properties: {
    question:   { type: 'string' },
    summary:    { type: 'string' },
    complexity: { enum: ['simple', 'moderate', 'complex'] },
    needsEvidenceTiering: { type: 'boolean' },
    reasoningSubquestions: { type: 'array', maxItems: 3, items: { type: 'string' } },
    angles: { type: 'array', minItems: 2, maxItems: 8, items: {
      type: 'object', required: ['label', 'query', 'boundary', 'lens'],
      properties: {
        label:    { type: 'string' },
        query:    { type: 'string' },
        boundary: { type: 'string' },
        lens:     { enum: LENSES },
      },
    }},
  },
}
const SEARCH_SCHEMA = {
  type: 'object', required: ['results'],
  properties: {
    results: { type: 'array', maxItems: 5, items: {
      type: 'object', required: ['url', 'title', 'relevance'],
      properties: {
        url:       { type: 'string' },
        title:     { type: 'string' },
        snippet:   { type: 'string' },
        relevance: { enum: ['high', 'medium', 'low'] },
      },
    }},
  },
}
const EXTRACT_SCHEMA = {
  type: 'object', required: ['claims', 'sourceQuality'],
  properties: {
    sourceQuality: { enum: ['primary', 'secondary', 'blog', 'forum', 'unreliable'] },
    publishDate:   { type: 'string' },
    claims: { type: 'array', maxItems: 4, items: {
      type: 'object', required: ['claim', 'quote', 'importance', 'evidenceTier', 'isMechanisticInference'],
      properties: {
        claim:      { type: 'string' },
        quote:      { type: 'string' },
        importance: { enum: ['central', 'supporting', 'tangential'] },
        evidenceTier: { enum: TIERS },
        isMechanisticInference: { type: 'boolean' },
      },
    }},
  },
}
const VERDICT_SCHEMA = {
  type: 'object', required: ['refuted', 'evidence', 'confidence', 'tierMismatch'],
  properties: {
    refuted:      { type: 'boolean' },
    evidence:     { type: 'string' },
    confidence:   { enum: ['high', 'medium', 'low'] },
    tierMismatch: { type: 'boolean' },
    counterSource:{ type: 'string' },
  },
}
const REASONED_SCHEMA = {
  type: 'object', required: ['conclusion', 'reasoning', 'leansOnClaimIds', 'confidence'],
  properties: {
    conclusion:      { type: 'string' },
    reasoning:       { type: 'string' },
    leansOnClaimIds: { type: 'array', items: { type: 'integer' } },
    confidence:      { enum: ['high', 'medium', 'low'] },
  },
}
const CRITIC_SCHEMA = {
  type: 'object', required: ['overstatements', 'oneSidedness', 'missingAngles', 'saturated'],
  properties: {
    overstatements: { type: 'array', items: { type: 'string' } },
    oneSidedness:   { type: 'string' },
    missingAngles:  { type: 'array', maxItems: 4, items: {
      type: 'object', required: ['label', 'query', 'boundary', 'lens'],
      properties: {
        label:    { type: 'string' },
        query:    { type: 'string' },
        boundary: { type: 'string' },
        lens:     { enum: LENSES },
      },
    }},
    saturated: { type: 'boolean' },
  },
}
const REPORT_SCHEMA = {
  type: 'object', required: ['summary', 'findings', 'caveats'],
  properties: {
    summary: { type: 'string' },
    findings: { type: 'array', items: {
      type: 'object', required: ['claim', 'confidence', 'tier', 'sources', 'evidence'],
      properties: {
        claim:      { type: 'string' },
        confidence: { enum: ['high', 'medium', 'low'] },
        tier:       { enum: [...TIERS, 'reasoned-from-cited-mechanism', 'mixed'] },
        sources:    { type: 'array', items: { type: 'string' } },
        evidence:   { type: 'string' },
      },
    }},
    caveats:       { type: 'string' },
    openQuestions: { type: 'array', items: { type: 'string' } },
  },
}

// ─── Phase 0: Scope/Plan (Opus) ───
const QUESTION = (typeof args === 'string' && args.trim()) || ''
if (!QUESTION) {
  return { error: "No research question provided. Pass it as args: Workflow({scriptPath: '...', args: '<question>'})" }
}

phase('Scope')
const scope = await agent(
  '## Research Planner\n\n' +
  'Decompose this research question into a sized plan of complementary search angles.\n\n' +
  '## Question\n' + QUESTION + '\n\n' +
  '## 1. Judge complexity\n' +
  '- simple: single factual question in a settled domain → 2-3 angles\n' +
  '- moderate: multi-faceted, or some real controversy → 3-5 angles\n' +
  '- complex: contested empirical domain, multiple mechanisms/subpopulations, high stakes of being wrong → 5-8 angles\n\n' +
  '## 2. Pick angles from the lens catalog\n' + LENS_CATALOG + '\n\n' +
  'HARD RULE: at least one angle MUST use lens `contrarian-disconfirmation` — actively hunt the case AGAINST the consensus answer (null results, failed replications, debunkings, failure conditions). Non-negotiable, even for simple questions.\n\n' +
  'Each angle needs a `boundary`: one or two sentences stating what it covers AND what it explicitly EXCLUDES, so no two angles overlap. Each `query` must be a concrete, high-signal web search string.\n\n' +
  '## 3. Evidence machinery\n' +
  '- needsEvidenceTiering: true for empirical/health/causal/scientific topics where evidence strength matters; false for pure preference, how-to, or product-comparison questions.\n' +
  '- reasoningSubquestions: 0-3 counterintuitive sub-questions worth reasoning through from first principles once evidence is collected (e.g. "if the mechanism is X, why do trials in population Y show nothing?"). Empty for simple topics.\n\n' +
  'Return the question (verbatim or lightly normalized), a 1-2 sentence decomposition strategy, complexity, the angles, and the evidence-machinery fields.\n\nStructured output only.',
  { label: 'scope', phase: 'Scope', schema: SCOPE_SCHEMA, model: 'opus', effort: 'high', agentType: 'opus-worker' }
)
if (!scope) return { error: 'Scope agent returned no result.' }

const sizing = SIZING[scope.complexity] || SIZING.moderate
log('Q: ' + QUESTION.slice(0, 80) + (QUESTION.length > 80 ? '…' : ''))
log('Complexity: ' + scope.complexity + ' → ≤' + sizing.maxAngles + ' angles, ≤' + sizing.maxFetch + ' fetches/round, ' + sizing.extraRounds + ' extra round(s) max')

// Enforce sizing + the disconfirmation guarantee even if the planner slipped.
let angles = scope.angles.slice(0, sizing.maxAngles)
if (!angles.some(a => a.lens === 'contrarian-disconfirmation')) {
  const disc = scope.angles.find(a => a.lens === 'contrarian-disconfirmation') || {
    label: 'disconfirmation',
    query: QUESTION + ' criticism null results debunked evidence against',
    boundary: 'Only evidence AGAINST the consensus answer: null/negative results, failed replications, debunkings, failure conditions. Excludes supporting evidence.',
    lens: 'contrarian-disconfirmation',
  }
  if (angles.length >= sizing.maxAngles) angles[angles.length - 1] = disc
  else angles.push(disc)
}
log('Angles: ' + angles.map(a => a.label + ' [' + a.lens + ']').join(' · '))

// ─── Shared state across rounds ───
const normURL = u => {
  try {
    const p = new URL(u)
    return (p.hostname.replace(/^www\./, '') + p.pathname.replace(/\/$/, '')).toLowerCase()
  } catch { return u.toLowerCase() }
}
const normClaim = t => t.toLowerCase().replace(/[^a-z0-9 ]/g, '').replace(/\s+/g, ' ').trim()
const relRank  = { high: 0, medium: 1, low: 2 }
const qualRank = { primary: 0, secondary: 1, blog: 2, forum: 3, unreliable: 4 }

const seenURL    = new Map()
const seenClaims = new Set()
const confirmed  = []   // verified centrals + unverified supporting/tangential
const contested  = []   // refuted-by-skeptic, demoted not deleted
const allSources = []
const roundLog   = []
let claimDupes = 0, urlDupes = 0, budgetDropped = 0
let totalSearches = 0, totalFetches = 0, totalVerifies = 0, criticRuns = 0
let nextClaimId = 0

const SEARCH_PROMPT = (angle) =>
  '## Web Searcher: ' + angle.label + ' [' + angle.lens + ']\n\n' +
  'Research question: "' + QUESTION + '"\n\n' +
  'Your angle: **' + angle.label + '**\n' +
  'Boundary (stay inside it — other agents cover the rest): ' + angle.boundary + '\n' +
  'Search query: `' + angle.query + '`\n\n' +
  '## Task\nUse WebSearch with the query above (refine once if results are weak). Return the top 4-5 most relevant results WITHIN YOUR BOUNDARY.\n' +
  'Rank by relevance to the ORIGINAL question. Skip obvious SEO spam/content farms.\n\nStructured output only.'

const FETCH_PROMPT = (source, angleLabel) =>
  '## Source Extractor\n\n' +
  'Research question: "' + QUESTION + '"\n\n' +
  'Fetch and extract key claims from this source:\n' +
  '**URL:** ' + source.url + '\n**Title:** ' + source.title + '\n**Found via:** ' + angleLabel + ' search\n\n' +
  '## Task\n1. Use WebFetch to retrieve the page.\n' +
  '2. Assess source quality: primary/secondary/blog/forum/unreliable.\n' +
  '3. Extract 2-4 FALSIFIABLE claims bearing on the research question. Each must:\n' +
  '   - be a concrete, checkable statement\n' +
  '   - include a direct quote from the source\n' +
  '   - be rated central/supporting/tangential\n' +
  '   - carry an evidenceTier — what kind of evidence BACKS the claim in this source:\n' + TIER_GUIDE + '\n' +
  '   - set isMechanisticInference=true when the claim is the source\'s own "should work because…" reasoning rather than a measured result. Mechanism dressed as proof is the #1 extraction error — flag it.\n' +
  '4. Note publish date if available.\n\n' +
  'If fetch fails or page is irrelevant/paywalled, return claims: [] and sourceQuality: "unreliable".\n\nStructured output only.'

const VERIFY_PROMPT = (claim) =>
  '## Skeptical Claim Verifier\n\n' +
  'You are the ONLY skeptic this claim gets — be rigorous. A refuted claim is demoted to a visible "contested" block (the reader sees the dispute), not deleted, so flag honestly rather than charitably.\n\n' +
  '## Research question\n' + QUESTION + '\n\n' +
  '## Claim under review\n"' + claim.claim + '"\n\n' +
  '**Source:** ' + claim.sourceUrl + ' (' + claim.sourceQuality + ')\n' +
  '**Stated evidence tier:** ' + claim.evidenceTier + (claim.isMechanisticInference ? ' (flagged as mechanistic inference)' : '') + '\n' +
  '**Supporting quote:** "' + claim.quote + '"\n\n' +
  '## Checklist\n' +
  '1. Is the claim supported by the quote, or an overreach/misread?\n' +
  '2. WebSearch specifically for DISCONFIRMING evidence: null results, contradicting studies, failed replications, debunkings.\n' +
  '3. Tier mismatch: is mechanistic inference, expert opinion, or anecdote being stated as proven fact? If the claim\'s wording overstates its tier, set tierMismatch=true (and refute if the overstatement is material).\n' +
  '4. Is the claim outdated — superseded by newer evidence?\n' +
  '5. Is this marketing fluff / press release / cherry-picked benchmark / SEO content?\n\n' +
  '**refuted=true** if: unsupported by quote / credibly contradicted / materially overstated vs tier / outdated / marketing.\n' +
  '**refuted=false** ONLY if: well-supported, current, and stated no stronger than its evidence warrants.\n' +
  'Default to refuted=true if uncertain.\n\nStructured output only. Evidence MUST be specific (name the contradicting source or the exact overreach).'

const claimLineLite = c =>
  '[' + c.id + '] (' + c.evidenceTier + (c.isMechanisticInference ? ' · mech-inference' : '') + ' · ' + c.importance +
  (c.verified ? ' · skeptic-checked' : '') + ') ' + c.claim

const claimLineFull = c =>
  claimLineLite(c) + '\n    src: ' + c.sourceUrl + ' (' + c.sourceQuality + ') — "' + (c.quote || '').slice(0, 200) + '"'

// ─── Bounded saturation loop: Search → Fetch → Verify → Critic ───
let round = 0
let critic = null

while (true) {
  let fetchSlots = sizing.maxFetch
  const rTag = 'r' + round + ':'

  const stageResults = await pipeline(
    angles,

    angle => agent(SEARCH_PROMPT(angle), {
      label: rTag + 'search:' + angle.label, phase: 'Search', schema: SEARCH_SCHEMA, model: 'sonnet', effort: 'medium', agentType: 'worker',
    }).then(r => {
      totalSearches++
      if (!r) return null
      log(angle.label + ': ' + r.results.length + ' results')
      return { angle: angle.label, results: r.results }
    }),

    searchResult => {
      if (!searchResult) return []
      const sorted = [...searchResult.results].sort((a, b) => relRank[a.relevance] - relRank[b.relevance])
      const novel = sorted.filter(r => {
        const key = normURL(r.url)
        if (seenURL.has(key)) { urlDupes++; return false }
        if (fetchSlots <= 0 && relRank[r.relevance] >= 1) { budgetDropped++; return false }
        seenURL.set(key, searchResult.angle)
        fetchSlots--
        return true
      })
      return parallel(
        novel.map(source => () => {
          let host = 'unknown'
          try { host = new URL(source.url).hostname.replace(/^www\./, '') } catch {}
          totalFetches++
          return agent(FETCH_PROMPT(source, searchResult.angle), {
            label: rTag + 'fetch:' + host, phase: 'Fetch', schema: EXTRACT_SCHEMA, model: 'sonnet', effort: 'medium', agentType: 'worker',
          }).then(ext => {
            if (!ext) return null
            return {
              url: source.url, title: source.title, angle: searchResult.angle,
              sourceQuality: ext.sourceQuality, publishDate: ext.publishDate,
              claims: ext.claims.map(c => ({ ...c, sourceUrl: source.url, sourceQuality: ext.sourceQuality })),
            }
          }).catch(e => {
            log('fetch failed: ' + source.url + ' — ' + (e.message || e))
            return { url: source.url, title: source.title, angle: searchResult.angle, sourceQuality: 'unreliable', claims: [] }
          })
        })
      )
    }
  )

  const roundSources = stageResults.filter(Boolean).flat().filter(Boolean)
  allSources.push(...roundSources)

  // Dedup new claims by normalized text vs everything ever seen (not just confirmed —
  // else skeptic-contested claims reappear every round and the loop never converges).
  const fresh = []
  for (const c of roundSources.flatMap(s => s.claims)) {
    const key = normClaim(c.claim)
    if (seenClaims.has(key)) { claimDupes++; continue }
    seenClaims.add(key)
    fresh.push({ ...c, id: nextClaimId++, round })
  }
  log('Round ' + round + ': ' + roundSources.length + ' sources → ' + fresh.length + ' fresh claims' + (claimDupes ? ' (' + claimDupes + ' dupes total)' : ''))

  // ── Verify (slim): central fresh claims only, 1 skeptic each, demote-not-kill ──
  const centralFresh = fresh
    .filter(c => c.importance === 'central')
    .sort((a, b) => qualRank[a.sourceQuality] - qualRank[b.sourceQuality])
    .slice(0, sizing.centralCap)
  const centralIds = new Set(centralFresh.map(c => c.id))

  const verdicts = await parallel(
    centralFresh.map(claim => () => {
      totalVerifies++
      return agent(VERIFY_PROMPT(claim), {
        label: rTag + 'skeptic:' + claim.claim.slice(0, 40), phase: 'Verify', schema: VERDICT_SCHEMA, model: 'sonnet', effort: 'medium', agentType: 'worker',
      }).then(v => ({ claim, v }))
    })
  )
  for (const item of verdicts.filter(Boolean)) {
    const { claim, v } = item
    if (v && v.refuted) {
      contested.push({ ...claim, skepticEvidence: v.evidence, tierMismatch: !!v.tierMismatch, counterSource: v.counterSource || '' })
      log('contested: "' + claim.claim.slice(0, 60) + '…"')
    } else {
      confirmed.push({ ...claim, verified: !!v, tierMismatch: v ? !!v.tierMismatch : false })
    }
  }
  // Supporting/tangential (and over-cap centrals) skip the gauntlet — they lean on
  // extraction quality + the critic.
  for (const c of fresh) {
    if (!centralIds.has(c.id)) confirmed.push({ ...c, verified: false })
  }

  roundLog.push({
    round,
    angles: angles.map(a => a.label + ' [' + a.lens + ']'),
    sources: roundSources.length,
    freshClaims: fresh.length,
    contestedSoFar: contested.length,
  })

  // ── Critic (Opus): saturated, or loop back with targeted missing angles ──
  criticRuns++
  critic = await agent(
    '## Completeness Critic\n\n' +
    'You judge whether this research run is saturated or has material gaps. Round ' + round + '; at most ' + sizing.extraRounds + ' extra round(s) allowed after round 0.\n\n' +
    '## Research question\n' + QUESTION + '\n\n' +
    '## Angle coverage so far\n' +
    roundLog.map(r => 'Round ' + r.round + ': ' + r.angles.join(' · ') + ' (' + r.sources + ' sources, ' + r.freshClaims + ' fresh claims)').join('\n') + '\n\n' +
    '## Accumulated claims\n' + (confirmed.map(claimLineLite).join('\n') || '(none)') + '\n\n' +
    '## Contested (skeptic-refuted, will be shown as disputed)\n' +
    (contested.map(c => '[' + c.id + '] ' + c.claim + ' — skeptic: ' + c.skepticEvidence.slice(0, 150)).join('\n') || '(none)') + '\n\n' +
    '## Task\n' +
    '1. overstatements: claims in the pool stated stronger than their evidence tier warrants (cite claim ids).\n' +
    '2. oneSidedness: is the pool lopsided — all pro or all con, one population, mechanism-only, no disconfirming evidence found despite searching? One blunt sentence; empty string if balanced.\n' +
    '3. missingAngles: ONLY angles whose findings would materially change the answer — a missed evidence type, subpopulation, or counter-hypothesis. Each needs {label, query, boundary, lens} with lens from: ' + LENSES.join(', ') + '. Boundaries must not overlap angles already covered. Empty array if coverage is adequate.\n' +
    '4. saturated: true if another search round would mostly re-find what is already here.\n\n' +
    'Be stingy with missingAngles — each costs a full search round. An angle that would merely add more of the same evidence is NOT missing.\n\nStructured output only.',
    { label: rTag + 'critic', phase: 'Critic', schema: CRITIC_SCHEMA, model: 'opus', effort: 'high', agentType: 'opus-worker' }
  )

  if (!critic) { log('Critic returned nothing — finalizing'); break }
  if (critic.saturated || !critic.missingAngles.length) { log('Critic: saturated after round ' + round); break }
  if (round >= sizing.extraRounds) { log('Critic found gaps but extra-round budget exhausted: ' + critic.missingAngles.map(a => a.label).join(', ')); break }
  if (budget.total && budget.remaining() < MIN_BUDGET_FOR_EXTRA_ROUND) { log('Token budget low — finalizing without extra round'); break }

  angles = critic.missingAngles.slice(0, MAX_ANGLES_PER_EXTRA_ROUND)
  round++
  log('Critic round ' + (round - 1) + ' → extra round ' + round + ': ' + angles.map(a => a.label + ' [' + a.lens + ']').join(' · '))
}

if (!confirmed.length && !contested.length) {
  return {
    question: QUESTION, complexity: scope.complexity,
    summary: 'No claims extracted from any source.',
    findings: [], contested: [], reasoned: [],
    sources: allSources.map(s => ({ url: s.url, quality: s.sourceQuality })),
    rounds: roundLog,
    stats: { complexity: scope.complexity, rounds: roundLog.length, sourcesFetched: allSources.length, claims: 0 },
  }
}

// ─── Phase 3.5: First-principles reasoning (Opus, conditional) ───
const poolBlock =
  '## Claim pool (verified + unverified)\n' + (confirmed.map(claimLineFull).join('\n') || '(none)') + '\n\n' +
  '## Contested claims (skeptic-refuted — usable as disputed signal, not fact)\n' +
  (contested.map(c => claimLineFull(c) + '\n    skeptic: ' + c.skepticEvidence.slice(0, 200)).join('\n') || '(none)')

let reasoned = []
const subqs = (scope.reasoningSubquestions || []).slice(0, 3)
if (scope.needsEvidenceTiering && subqs.length && confirmed.length) {
  reasoned = (await parallel(
    subqs.map(q => () =>
      agent(
        '## First-Principles Reasoner\n\n' +
        'Research question: "' + QUESTION + '"\n\n' +
        'Your sub-question: **' + q + '**\n\n' +
        poolBlock + '\n\n' +
        '## Task\n' +
        'Reason from first principles using ONLY the claim pool above as your evidence base (cite claim ids in leansOnClaimIds). ' +
        'Produce a non-obvious conclusion the individual sources do not state outright — reconcile contradictions, explain why mechanism and trial data diverge, identify the conditions under which the answer flips.\n' +
        'Your output will be tagged tier "reasoned-from-cited-mechanism" and kept distinct from directly-evidenced findings — do NOT dress inference as measured fact. ' +
        'If the pool cannot support a real conclusion, say so plainly with confidence low.\n\nStructured output only.',
        { label: 'reason:' + q.slice(0, 40), phase: 'Reasoning', schema: REASONED_SCHEMA, model: 'opus', effort: 'high', agentType: 'opus-worker' }
      ).then(r => r && { ...r, subquestion: q, tier: 'reasoned-from-cited-mechanism' })
    )
  )).filter(Boolean)
  log('Reasoning: ' + reasoned.length + '/' + subqs.length + ' sub-questions answered')
}

// ─── Phase 4: Synthesize (Opus) ───
const reasonedBlock = reasoned.length
  ? '\n## First-principles conclusions (tier: reasoned-from-cited-mechanism)\n' +
    reasoned.map(r => '- Q: ' + r.subquestion + '\n  A (' + r.confidence + ', leans on claims ' + r.leansOnClaimIds.join(',') + '): ' + r.conclusion).join('\n')
  : ''

const report = await agent(
  '## Synthesis: research report\n\n' +
  '**Question:** ' + QUESTION + '\n\n' +
  poolBlock + reasonedBlock + '\n\n' +
  '## Instructions\n' +
  '1. Merge claims that say the same thing — combine their sources.\n' +
  '2. Group into coherent findings that directly answer the research question.\n' +
  '3. Every finding carries a tier — the STRONGEST evidence tier actually backing it (' + TIERS.join(' > ') + '), "mixed" when merged claims span tiers, or "reasoned-from-cited-mechanism" for findings built on the first-principles conclusions. Never launder mechanistic inference or anecdote into a higher tier.\n' +
  '4. Assign confidence: high (multiple quality sources, skeptic-checked, tier ≥ rct), medium (secondary sources or single study), low (single source, blog, mechanistic-only).\n' +
  '5. Write a 3-5 sentence executive summary that answers the question and names the evidence strength. Non-sycophantic: if the honest answer is "weaker than commonly believed" or "it depends", say exactly that.\n' +
  '6. Contested claims are NOT findings — but where a contested claim disputes a finding, say so in that finding\'s evidence text, and reflect the dispute in caveats.\n' +
  '7. Caveats: uncertainty, weak tiers, tier mismatches, time-sensitivity, what the disconfirmation search did and did not find.\n' +
  '8. List 2-3 open questions that emerged but were not answered.\n\nStructured output only.',
  { label: 'synthesize', phase: 'Synthesize', schema: REPORT_SCHEMA, model: 'opus', effort: 'high', agentType: 'opus-worker' }
)

const contestedOut = contested.map(c => ({
  claim: c.claim, source: c.sourceUrl, evidenceTier: c.evidenceTier,
  skepticEvidence: c.skepticEvidence, tierMismatch: c.tierMismatch, counterSource: c.counterSource,
}))
const sourcesOut = allSources.map(s => ({ url: s.url, quality: s.sourceQuality, angle: s.angle, claimCount: s.claims.length }))
const stats = {
  complexity: scope.complexity,
  rounds: roundLog.length,
  sourcesFetched: allSources.length,
  claimsExtracted: nextClaimId,
  claimsVerified: totalVerifies,
  confirmed: confirmed.length,
  contested: contested.length,
  reasoned: reasoned.length,
  urlDupes, claimDupes, budgetDropped,
  agentCalls: 1 + totalSearches + totalFetches + totalVerifies + criticRuns + subqs.length + (report ? 1 : 0),
}

if (!report) {
  return {
    question: QUESTION, complexity: scope.complexity,
    summary: 'Synthesis agent failed — returning ' + confirmed.length + ' claims unmerged.',
    findings: [],
    confirmed: confirmed.map(c => ({ claim: c.claim, tier: c.evidenceTier, verified: c.verified, source: c.sourceUrl, quote: c.quote })),
    contested: contestedOut, reasoned, sources: sourcesOut, rounds: roundLog, stats,
  }
}

// Fold the final critic's overstatement/one-sidedness notes into caveats.
const criticNotes = []
if (critic && critic.overstatements && critic.overstatements.length) criticNotes.push('Critic — overstatement risks: ' + critic.overstatements.join(' · '))
if (critic && critic.oneSidedness) criticNotes.push('Critic — one-sidedness: ' + critic.oneSidedness)
report.caveats = [report.caveats, ...criticNotes].filter(Boolean).join('\n')

return {
  question: QUESTION,
  complexity: scope.complexity,
  ...report,
  contested: contestedOut,
  reasoned: reasoned.map(r => ({ subquestion: r.subquestion, conclusion: r.conclusion, confidence: r.confidence, tier: r.tier, leansOnClaimIds: r.leansOnClaimIds })),
  sources: sourcesOut,
  rounds: roundLog,
  stats,
}
