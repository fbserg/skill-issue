# Calibration Cases

Read this when you are unsure what good output looks like. One full worked
run, kept for what it calibrates: the skill correctly doing almost nothing to
prose that only looks sloppy. If you can do this case, you will not
over-edit. (The output contract itself — headers, sections, exact structure —
is already specified as a literal template in SKILL.md; this file exists to
calibrate restraint, not to re-demonstrate the contract shape.)

---

## Example 3: Restraint (genuine human prose that only looks sloppy)

**User:** "make this sound less like AI"

**Input (a real person, formal register, a colon, a parenthetical, one tricolon):**
> I have taught this seminar for nineteen years, and the pattern never
> changes: the students who struggle most in October are, almost without
> exception, the ones who do best in May. What looks like confusion in week
> three (the long silences, the abandoned drafts, the office-hours visits that
> start with "I think I'm lost") is usually the sound of someone actually
> rebuilding how they read. It is uncomfortable to watch and worse to
> experience. I no longer try to rescue them too early.

**Step 0:** No voice file, no sample. Generic mode.

**Pass 2 (tell removal):** Run the catalog honestly. Candidate flags and the
verdicts:
- A tricolon ("the long silences, the abandoned drafts, the office-hours
  visits"): pattern 12, but it is a single earned list with a specific,
  concrete payload, not reflexive padding. Leave it.
- The colon after "never changes" and the parenthetical aside: ordinary human
  syntax doing real work. A single strong connective like this is normal
  punctuation, the same way one or two em dashes would be (pattern 22
  restraint); it is not a tell.
- "almost without exception": mild hedge, but it is the writer's honest,
  load-bearing qualifier (pattern 9 restraint, and a human marker in
  do-not-flag.md Part 2). Keep it.

There is nothing machine here. The prose has specific details (nineteen years,
October, May, week three, a quoted student line), mixed feeling (uncomfortable
to watch and worse to experience), and real sentence-length swing. These are
the human markers do-not-flag.md says to protect.

**Pass 3 (self-audit):** The honest answer to "what would tip a reader that a
machine wrote this" is: nothing would. A heavy rewrite here would be the
failure. Output minimal edits (none needed) and explain the restraint.

### Humanized draft
Voice: generic

> I have taught this seminar for nineteen years, and the pattern never
> changes: the students who struggle most in October are, almost without
> exception, the ones who do best in May. What looks like confusion in week
> three (the long silences, the abandoned drafts, the office-hours visits that
> start with "I think I'm lost") is usually the sound of someone actually
> rebuilding how they read. It is uncomfortable to watch and worse to
> experience. I no longer try to rescue them too early.

(Unchanged. This is already human writing.)

### What changed
- Nothing. No machine tells were present.

### Deliberately left alone
- The colon and the parenthetical aside: a single strong connective and one
  aside, within normal human range (pattern 22 applies the same restraint to
  one or two em dashes), not artifacts.
- The tricolon: a single earned list with concrete content, not pattern-12
  padding.
- "almost without exception": the writer's honest qualifier and a human
  marker; removing it would change the claim.

### Meaning check
Nothing changed, so nothing to drift. Flagging this would have stripped
specific detail and voice from genuine human prose, which is the worst error
this skill can make.

### Next step
No file path was given. Stopping here.

## What this teaches

The catalog is a question, not a verdict. Run every flag through its
restraint note and do-not-flag.md before you touch anything. Doing nothing,
explained, is a correct and common output.
