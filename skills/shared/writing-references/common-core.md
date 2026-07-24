# Common Core: shared calibration for humanizer and authenticity-check

Content that was byte-identical across `humanizer/SKILL.md` and
`authenticity-check/SKILL.md` — the rewrite tool and the diagnostic tool read
from the same catalog and the same discovery mechanism, since they are the two
halves of one pair (see each SKILL.md's own framing of that pair). Read the
section named from the calling SKILL.md; this file does not stand alone.

## Voice-profile discovery

`Glob` the working directory and up to two parent levels, in this priority
order: `VOICE.md`, then `STYLE-GUIDE.md`, then `voice-profile.md` / `.yaml` /
`.json`, then `.manuscript/STYLE-GUIDE.md`, then a voice or style section
inside `AGENTS.md` or `CLAUDE.md`.

## Dead-giveaway tell catalog (for the density pre-check)

Count only the **dead-giveaway** tells, not the weak surface signals: chat-UI
contamination (pattern 31), knowledge-cutoff disclaimers (29), collaborative
chatbot artifacts (28), significance inflation (1), promotional language (5),
AI-vocabulary clustering (16), sycophantic tone (7), generic positive
conclusion (13).

One exception always overrides density: any chat-UI contamination string
(pattern 31) is decisive on its own, whatever the overall count, because its
presence is near-certain confirmation rather than a weak signal.

## Core insight

The reason AI prose reads as AI is not its vocabulary. It is its uniformity:
even sentence lengths, even rhythm, even hedging, the same shapes resolved the
same way.

## False-positive guardrails (shared subset)

Do not flag these in isolation — escalate only on recurrence or co-occurrence:

- A single em dash. Only dash frequency and monotony is a tell.
- Formal or elevated vocabulary. Register is not origin.
- Common transitions ("however," "therefore," "for example").
- One passive sentence, one tricolon, one topic sentence.

This is a subset. The calling SKILL.md adds one or two guardrails of its own
(a rewrite tool and a read-only diagnostic tool credit "perfect grammar" and
"curly quotes" slightly differently) and the full treatment — human markers to
preserve or credit, per-model idiolects, hard stop conditions — is in
`references/do-not-flag.md`.
