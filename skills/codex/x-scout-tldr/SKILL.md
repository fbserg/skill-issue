---
name: x-scout-tldr
description: Scan X/Twitter web search for architectural site plan automation, landscape/site drafting, urban forestry, and arboriculture/tree-plan automation, then give the user a concise TLDR. Use when the user asks for an X Scout scan, daily X update, Twitter/X TLDR, or recent posts about site plan/tree-plan automation without using an X API key or paid feed.
---

# X Scout TLDR

## Goal

Produce a short daily TLDR from X/Twitter-adjacent search with no API key, no paid service, and no Grok/X API dependency. The primary free path is browser-backed Nitter search. Direct logged-out `x.com/search` is unreliable and should be treated as manual fallback only.

## Workflow

1. Get the query set:
   - Run `node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --markdown` for the current search lanes and URLs.
   - The helper includes the previous successful run timestamp in the search URLs when one exists.
   - For an explicit lookback window, add `--days N` to `--markdown`, `--json`, `--open`, or `--scan`.
   - Query definitions live in `/Users/serg/.codex/skills/x-scout-tldr/queries.json`; do not duplicate them elsewhere.
2. Run the scanner:
   - Run `node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --scan`.
   - The scanner uses Playwright against Nitter mirrors, starting with `NITTER_URL`/`NITTER_INSTANCE` if set, then public fallback mirrors.
   - The helper stores seen tweet IDs and suppresses repeats on future runs.
   - If all free mirrors fail, the helper exits clearly and prints manual fallback URLs.
3. Reliability upgrade:
   - For a durable free setup, self-host Nitter locally and set `NITTER_URL=http://127.0.0.1:8788`.
   - Bind self-hosted Nitter to localhost. Use a secondary X account if Nitter needs session cookies.
   - Do not require, request, or store X/Grok API keys for this skill.
4. Try browser inspection only as fallback:
   - Prefer opening the generated `https://x.com/search?...&f=live` URLs with available browser/web tools.
   - Use Latest/live results, not Top, when the UI exposes that distinction.
   - Stay logged out unless the user has already provided an available browser session; never ask for or store credentials.
5. If X blocks automation, open the tabs for the user:
   - Run `node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --open`.
   - Ask the user to paste useful post URLs or visible text snippets from the tabs.
   - Then summarize the pasted material.
6. Filter aggressively:
   - Keep: site-plan workflows, permit drawings, construction drawings, landscape architecture workflows, planting/grading plans, GIS/mapping workflows, urban forestry, street-tree inventory, canopy/climate-risk work, arborist/tree inventory/tree protection/TPP automation.
   - Drop: mechanical CAD, product design CAD, Fusion/Onshape/SolidWorks/Blender demos, 3D model generation, 3D renders, interior visualization, Midjourney/DALL-E art, Enscape/Lumion/Twinmotion demos, generic AI-image content, generic architecture hype without drafting/site-plan/tree-plan substance.
7. Summarize:
   - Start with `TLDR:` and 2-4 bullets.
   - Include `Worth clicking:` with up to 5 links and one-line reasons.
   - Include `Noise / misses:` if most matches were off-topic.
   - Include `Confidence:` as High/Medium/Low based on access and result quality.
8. Mark the run:
   - After completing the summary, run `node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --mark-run`.
   - Do not mark the run if access was blocked before any meaningful scan happened.

## Output Rules

- Do not imply completeness. This is a manual/web-search scan, not an X API archive.
- Do not fabricate post text, authors, metrics, or dates.
- Do not include mechanical CAD, product CAD, Fusion, Onshape, SolidWorks, Blender, STL, mesh, 3D model generation, renders, interiors, or AI art in results.
- Prefer fewer, better links over a long dump.
- If there are no meaningful matches, say that plainly and name the lanes checked.
- Mention when access was blocked, login-gated, rate-limited, or based on user-pasted snippets.

## Helper Script

Use `scripts/x-scout-queries.mjs` to print or open the standard query set:

```bash
node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --markdown
node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --scan
node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --scan --days 3
node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --open
node /Users/serg/.codex/skills/x-scout-tldr/scripts/x-scout-queries.mjs --mark-run
```
