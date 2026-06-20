---
name: epic-research
description: Pre-plan research for an upcoming epic. Invoke with /epic-research TOPIC.
---

Three parallel agents on three lanes (direct competitors, tech peers, GitHub code), all grounded in our actual implementation. Output: a synthesis the user can act on or feed into `/epic-plan`. Stops: after step 0 (wait for scope answers), after step 4 (wait for "go to plan?" or "save report").

## 0. Scope the question

Before any research, ask 2–4 sharp questions. Pick the ones that matter for *this* topic:

- What's the **subsystem under audit**? (file paths, not vague nouns — "our title block" → `scripts/html_build/titleblock.{html.j2,css}` etc.)
- What axis are we comparing on? (architecture / UX / pricing / output quality / maintenance burden / handoff story)
- Direct competitors only, tech-stack peers only, or both?
- Geographic / market scope? (NA only? global? open-source only?)
- What would change in our roadmap based on the answer? (kills "just curious" research that ships nothing)

**Stop. Wait for answers.** If user says "you decide," state assumptions explicitly so they can be challenged.

## 1. Ground in our implementation

Before dispatching, walk the subsystem ourselves enough to brief the agents accurately. Each agent gets:

- **3–10 bullets** of our current shape: file paths with line counts, key abstractions, hard constraints (sheet sizes, scale rules, etc.), data flow sketch.
- **The specific axis** we're comparing on (from step 0).
- **What "ahead/behind" means** for this question (e.g. "ahead = less LLM-edit friction" vs "ahead = better PDF output quality").

Use `Explore` subagent if grounding takes >3 reads; otherwise grep + Read directly. Don't skip this — vague briefs produce vague reports.

## 2. Dispatch three agents in parallel

Send all three in a single message. Cap each at 400–700 words, demand concrete URLs / repo paths / `file:line` refs, demand "ahead / behind / steal / don't steal" framing.

### Agent 1 — Direct competitors
> *Who else solves this exact job for this exact user.*

Find tools/companies/products that produce the SAME deliverable for the SAME user. Search:
- Industry-specific terms + named competitors you suspect.
- Reddit / HN / forums where pros say what they actually use (more honest than vendor sites).
- Pricing pages and target-tier signals.

For each: deliverable mechanism, structure/customizability, pricing tier, target user, ahead-or-behind on what axes, visible tech-stack signals (LinkedIn, job posts, docs, error-page leaks).

**Goal:** is this leapfrog territory or catch-up? Where's the NA/EU/etc. market gap?

### Agent 2 — Tech-stack peers
> *Who else builds it this way, even if for a different deliverable.*

Find best-of-breed projects (open + commercial) using the same TECHNICAL approach. Compare: file layout, abstraction level, token system, multi-variant handling (sheet sizes / themes / locales), designer-handoff story.

Identify **2–3 exemplars worth studying** and **2–3 we're already ahead of**. Cite specific patterns (e.g. "FreeCAD `freecad:autofill` slot vocabulary") not vague categories ("they use templates").

### Agent 3 — GitHub deep search
> *What's actually shipping in code.*

Run ~10–15 targeted `gh search code` and `gh search repos` queries. For top 10–15 hits:
- Repo name + URL + stars
- Stack
- What they generate
- File structure for the relevant subsystem **with paths and line counts**
- Multi-variant handling

Highlight any approach materially better than ours. Filter aggressively — 1.5k★ repos doing it badly are more useful than 50★ repos doing it well, because they reveal what the field tolerates.

## 3. Synthesize

After all three return, write **one report** with this shape:

1. **Where we sit** — one paragraph. Leapfrog / parity / catch-up, with the axis named.
2. **Comparison table** — competitors × axes (architecture, abstraction, multi-variant, handoff, etc.). Mark cells "ahead / parity / behind / N/A".
3. **Ideas worth stealing** — 2–4 concrete patterns with source repo + the refactor path on our side (file:line where it'd land).
4. **Don't steal** — 2–3 patterns with reasons. Kills "we should rewrite in X" cargo-culting.
5. **Smallest valuable next move** — one sentence. Often "do nothing, we're ahead." Sometimes a 1-day refactor. Rarely a sibling epic.

**Tone:** outcomes not vibes. No "interesting findings" / "promising directions" / LinkedIn voice.

## 4. Handoff

End with one of:
- **"Want this as a `/epic-plan` brief?"** — if the synthesis surfaced concrete refactor work (item 3 + item 5 are non-trivial).
- **"Save report to `<path>/research-<slug>.md`?"** — if findings are reference material more than action.
- **"Done — we're ahead, no move needed."** — if synthesis is "leapfrog, keep shipping."

Wait for user to pick. Don't auto-create issues. Don't auto-write files.

**Skip step 4 entirely if invoked from `/epic-plan` step 0d** — synthesis flows back into the planner's draft as prior art, no handoff prompt needed.

## Tweaks per question type

- **Pricing/positioning** — drop Agent 3 (GitHub), add a "user voice" agent (Reddit / G2 / Twitter / forum threads).
- **Pure tech / refactor** — drop Agent 1 (competitors), add a "spec/standards" agent (W3C, RFCs, standards bodies, language-spec edge cases).
- **Greenfield "should we build X"** — keep all three but reframe Agent 1 as "who already shipped this and why aren't they winning."
- **Single-vendor evaluation** ("should we adopt Vercel / Stripe / Supabase for X") — collapse to two agents: vendor deep-dive + 2–3 named alternatives. Skip Agent 3.

## Rules

- **Three lanes don't overlap.** If two agent prompts are starting to converge, you've narrowed the question wrong — back to step 0.
- **Word caps are real.** Three 600-word reports synthesize. Three 3000-word reports don't. Cap and enforce.
- **Concrete refs or it didn't happen.** No vendor URL, no repo path, no `file:line` → not a finding, just a vibe.
- **Ground every agent in our code.** "Compare X to competitors" without our file paths produces generic best-practices slop.
- **Don't pre-pitch `/epic-plan`.** Offer it in step 4 only if synthesis warrants. Most research ends in "nothing to do, we're fine."
- **Cache the brief.** If user re-runs `/epic-research` on the same topic within a session, reuse step-1 grounding — don't re-read the same files.

## Pairing with the epic stack

- **`/epic-research`** — answers "where do we stand" before scoping work.
- **`/epic-plan`** — turns a decided direction into child issues.
- **`/epic-run`** — executes the plan.
- **`/epic-retro`** — mines closed epics for skill improvements.

Natural flow when research surfaces work: `/epic-research` → user picks a direction → `/epic-plan` with that direction as the topic + the synthesis as prior art → `/epic-run`.
