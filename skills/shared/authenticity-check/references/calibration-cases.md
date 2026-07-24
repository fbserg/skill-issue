# Calibration Cases

Read this when you are unsure what good diagnostic output looks like. Two
full worked runs, kept for what they calibrate: the skill correctly giving a
high score and almost no flags to prose that only looks formal, and its
mirror, the skill correctly giving a low score to prose that only looks
clean. If you can do both, you will neither over-flag nor under-flag
laundered prose. (The output contract itself is already specified as a
literal template in SKILL.md; this file exists to calibrate the score, not
to re-demonstrate the contract shape.)

Note in both examples: the report describes the flagged spans, it never
rewrites them. There is no "suggested" prose anywhere in a correct output.

---

## Example 3: Restraint (genuine human prose that only looks formal)

**User:** "score how human this reads: I have taught this seminar for
nineteen years, and the pattern never changes: the students who struggle most
in October are, almost without exception, the ones who do best in May. What
looks like confusion in week three (the long silences, the abandoned drafts,
the office-hours visits that start with 'I think I'm lost') is usually the
sound of someone actually rebuilding how they read. It is uncomfortable to
watch and worse to experience. I no longer try to rescue them too early."

**Step 0:** No voice file, no "sounds like me" framing. Generic mode.
**Step 0b:** dead-giveaway tells near zero per 100 words. Low scrutiny; bias
hard toward a high score.

**Pass 1 (catalog):** Candidate flags, run honestly: two dash-like
parenthetical breaks; a tricolon ("the long silences, the abandoned drafts,
the office-hours visits"); a colon; a mild hedge ("almost without exception").

**Pass 2 (false-positive audit):** Every candidate is either a lone weak
signal or a human marker. The tricolon is a single earned list with concrete,
specific content, not reflexive padding (pattern 12 restraint). The hedge is
the writer's honest load-bearing qualifier (pattern 9 restraint, and a human
marker). Strong human markers throughout: specific numbers and times
(nineteen years, October, May, week three), a quoted student line, and mixed
feeling ("uncomfortable to watch and worse to experience"). All credited
upward.

**Pass 3 (internal consistency):** One consistent voice and register across
all chunks, with a natural sentence-length swing that reads as a mind, not a
template. No divergent span. No Pass 3 flag.

**Scoring:** No surviving tells, dense human markers, consistent earned
profile. The honest answer to "what would tip a reader that a machine wrote
this" is: nothing. High band, high number. A low score here would be the
failure.

### Authenticity report
Mode: generic
Scrutiny: low (from the density pre-check)

Authenticity: Reads human   Score: 95/100
(higher means it reads more authentically as a person's own work)

### Flagged spans
- None. There are no surviving machine tells after the false-positive audit.

### Reads as human (deliberately not flagged)
- The tricolon "the long silences, the abandoned drafts, the office-hours
  visits": a single earned list with concrete content, not pattern-12
  padding. Credited as voice.
- "almost without exception": the writer's honest, load-bearing qualifier and
  a human marker; flagging it would misread careful writing as hedging.
- Specific detail throughout (nineteen years, October, May, week three, the
  quoted "I think I'm lost") and the mixed feeling ("uncomfortable to watch
  and worse to experience"): dense human signal. These drove the score up.

### Score basis
The score is driven by dense, specific human markers, a consistent earned
voice, and an idiosyncratic sentence-length swing, with zero surviving tells.
The single biggest factor is specificity: the concrete numbers, the dated
references, and the quoted line are very hard to fake and very easy to
destroy. Almost nothing would lower this score short of evidence the details
are fabricated, which is outside what a text-only read can determine.

### Caveats
This is a heuristic read, not proof of authorship. A high score is not a
guarantee; it means nothing in the text reads as machine-written. It names no
detector.

### Next step
Nothing to do. This text reads as a person's own work; there is no rewrite to
recommend and this skill would not perform one anyway.

---

## Example 5: Relocated signature (clean vocabulary, uniform rhythm, no markers)

**User:** "Is this AI? How authentically does this read as a real person's
work? Keeping a small garden teaches you patience over time. You learn that
good soil matters more than expensive seeds. You learn that water at the
wrong hour does little good. You learn that the plants you ignore often
outlast the ones you fuss over. Each season brings its own small lessons,
and each lesson asks you to wait a little longer than you would like. In
the end, the garden gives back what your attention puts in."

**Step 0:** No "sounds like me" intent and no voice source. Generic mode.
**Step 0b:** No catalog dead-giveaway fires (no significance inflation, no
promotional cluster, no AI vocabulary, no chat-UI contamination, no
sycophancy). Density is near zero per 100 words on the dead-giveaway list,
which would normally pick Low / light scrutiny. The relocated-signature
override applies instead: rhythm is uniform (six similar-length
declaratives), three consecutive sentences share an identical "You learn
that..." anaphoric template resolved the same way, and an audit for human
markers (`do-not-flag.md` Part 2) returns nothing (no concrete detail, no
number, no date, no mixed feeling, no idiosyncratic sentence-length swing,
no unhedged personal opinion, no trade idiolect). Treat scrutiny as High;
do not apply the low-density high-score bias.

**Pass 1 (catalog):** Pattern 12 (rule-of-three / templated parallelism) on
the "You learn that..." triad, with the open/close aphorisms framing it
(pattern 4 persuasive-authority and pattern 13 generic positive conclusion
as soft contributing signals). No Family A/B/D/E lexical or formatting tell
fires; clean vocabulary, no slop words.

**Pass 2 (false-positive audit):** A single anaphora is ordinarily a human
rhetorical choice (`do-not-flag.md` Part 2). Here it is the entire structural
skeleton of a marker-free uniform passage, so the credit does not apply: the
co-occurrence (anaphora plus uniform rhythm plus zero markers) is the
template, not the rhetoric, and the Step 0b override governs (see
`scoring.md` Part 1, precedence note). The audit finds no positive evidence
of a human author to credit upward.

**Pass 3 (internal consistency):** One short paragraph, well below the
three-chunk floor. Skipped. The uniformity here is global, not a local seam,
which is consistent with the relocated-signature read, not against it.

**Scoring:** No catalog dead-giveaway, but uniform rhythm with no credited
markers is the Reads AI-generated band by `scoring.md` Part 1. Clean
vocabulary does not lift it (Part 2 down-force). Number lands in the 0-59
anchor.

### Authenticity report
Mode: generic
Scrutiny: high (density Low by vocabulary; relocated-signature override applied)

Authenticity: Reads AI-generated   Score: 30/100
(higher means it reads more authentically as a person's own work)

### Flagged spans
- "You learn that good soil matters more than expensive seeds. You learn
  that water at the wrong hour does little good. You learn that the plants
  you ignore often outlast the ones you fuss over." -> Family C, pattern 12
  (templated parallel skeleton): three consecutive sentences in identical
  anaphoric shape, near-identical length, each resolved on the same
  contrastive turn. The signature is the structure itself, not the words.
- "Keeping a small garden teaches you patience over time" ... "In the end,
  the garden gives back what your attention puts in." -> aphoristic frame
  (pattern 4 / pattern 13, soft contributing signal): a tidy maxim open and
  a symmetrical maxim close wrapping the body in a closed major-chord arc.
- Whole passage -> uniform rhythm with no specificity (SKILL.md core
  principle; scoring.md Part 1): clean vocabulary and correct grammar over
  an even cadence with not one concrete detail, dated reference, opinion,
  or idiosyncratic length swing. Clean words do not lift a relocated
  signature.

### Reads as human (deliberately not flagged)
- The plain, unadorned vocabulary was not flagged on its own. Per
  `do-not-flag.md` Part 1, register is not origin. It is also not credited
  upward, because absence of slop vocabulary is not evidence of a human; it
  is the laundering condition the relocated-signature override is designed
  to catch.
- An honest accounting: the audit looked for specific human markers (a
  number, a date, a mixed feeling, a sentence-length swing, an unhedged
  personal opinion, a trade idiolect) and found none. This section is
  required even when empty; its emptiness here is part of the score.

### Score basis
The score is driven by the conjunction the relocated-signature override
exists to catch: clean vocabulary plus uniform rhythm plus a templated
parallel skeleton plus zero credited human markers. The single biggest
factor is the absence of any concrete particular a person would supply.
What would most raise the score: one named plant or variety, a specific
season or year, a remembered failure with a number, a real opinion delivered
flat. Any one of those would break the relocated-signature pattern.

### Caveats
This is a heuristic read, not proof of authorship. A skilled human writer
can produce deliberately even, proverb-style prose, and a short passage
gives the diagnostic less to work with than a longer one. A low score is not
an accusation against any person; it means the text carries the statistical
signature of laundered AI prose. Human judgment is required to act on it.

### Next step
If you want this prose improved, this skill does not rewrite. The fix is
the separate humanizer skill, applied as a human-judged step (likely by
breaking the uniform cadence and grounding the prose in one concrete, lived
particular). After that, this skill can re-verify with a fresh read. No
target score is handed over.

---

## What these teach

1. The catalog is a question, not a verdict. Run every candidate through
   Pass 2 and the scoring restraint before lowering a score. A high score
   with a populated "Reads as human" section is a correct and common output.
2. A relocated signature (clean vocabulary, uniform rhythm, no human
   markers) still reads low. Clean word choice on top of templated
   uniformity does not buy the text out of the Reads AI-generated band; the
   Step 0b override and `scoring.md` Part 1 carry that decision, and the
   anaphora precedence note in Part 1 keeps the do-not-flag credit from
   accidentally rescuing it.
