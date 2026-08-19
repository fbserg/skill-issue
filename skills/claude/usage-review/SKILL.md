---
name: usage-review
description: >
  Review a body of AI-assistant transcripts (your own local Claude Code / Codex CLI
  sessions, or a shared exporter-markdown archive) into a red-teamed report: numbers,
  automation families, risk incidents, rubric grades, per-project/person coaching, action
  plan. Everything stays local except what the grader/lanes send to your own model provider.
  Use when the user asks to review/audit/analyze their AI usage, transcripts, sessions,
  token spend, or "how am I using Claude/Codex".
---

# usage-review

Turn a corpus of AI-assistant transcripts into findings that survive an adversarial check.
Method, calibration numbers and pitfalls: `METHODOLOGY.md` (read §2–§3 once before the first
run). This file is the operating procedure.

## Before you run anything — settle with the user (one message, all at once)

1. **Corpus**: local (`~/.claude/projects` + `~/.codex/sessions`, default) or an exporter-markdown
   archive (`<root>/<user>/YYYY-MM-DD.md`, use `tools/extract_exporter_md.py`).
2. **Window**: days back (31 shows habits; 180 shows adoption).
3. **Who** — one sentence for the lane/red-team prompts: whose transcripts, what they do
   ("one solo developer running several products, heavy sub-agent orchestration"; "a 12-person
   agency team, mostly Claude Code"). This is the only place a name enters the pipeline; a
   handle or "the user" is fine.
4. **Audience**: self (no restrictions — it is their own data), a manager, the whole team.
   Names + dollars + tiers is management-only; coaching for individuals travels as a separate
   sheet without tiers or costs.
5. **Grade?** The rubric grader costs ~$0.16/session on Sonnet at list price and sends clipped
   renders to `claude -p`; default yes for ≥40 human sessions.

If the user gave all five (or said "just run it"), do not ask — state the assumptions and go.

## Run

```bash
SKILL=<this skill's directory>            # resolve from the installed usage-review skill path
python3 $SKILL/tools/pipeline.py --days <N> [--grade --context <work>/context.txt] [--user <label>]
```

`pipeline.py` = quant → cmd_scan → summarize → sample → render → risky_digest → [grade → digest]
→ secret_scan, into `~/.local/share/usage-review/<date>/` (override with `--work`; it refuses any
path inside a git work tree and writes a `.gitignore` of `*`). It prints the work dir, the file
list, secret-scan HIGH count, and the exact `Workflow` args for the next step. `context.txt` for
the grader is one paragraph: who, projects, transcript conventions — write it from step 3.
Window semantics: sessions active in the last N days are counted whole, so a long session that
started earlier brings its full cost; `quant_summary.txt` says how many did — quote the actual span.

Then, in this session:

```
Workflow({ scriptPath: "$SKILL/workflows/lanes.js",
           args: { base: "<work dir>", who: "<step 3>", tz: "<date +%z>", lanes: <parse <work dir>/lanes.json> } })
```

One `worker` per lane; each writes `<work>/lanes/<lane>.md` and returns JSON. Save the return
value as `<work>/lanes_result.json`.

**Draft** the report yourself from `quant_summary.txt`, `automation.txt`, `risky_digest.md`,
`digest.md` (if graded) and the lane JSON — recompute any number you quote from `sessions.jsonl` rather than
copying a lane's figure. Structure: short version (7 bullets) · numbers at a glance · method and
caveats · where the money goes · what works · what does not · waste itemised · risk and incidents
(what happened / root gap / file cite) · rubric grades · per-project or per-person table (what
works / what to fix / first action) · automations · action plan (this week / 2–4 weeks / quarter) ·
sources. Write it to `<work>/report-draft.md`.

**Red team**: extract 100–150 specific claims from the draft into clusters (shape:
`examples/claims.example.json` — numbers, per-project facts, incidents, grades), then

```
Workflow({ scriptPath: "$SKILL/workflows/redteam.js",
           args: { base: "<work dir>", who: "<step 3>", tz: "<date +%z>", clusters: <the clusters> } })
```

Apply the adjudicated corrections, add a red-team log section (verified / partially / refuted /
unverifiable counts, what changed), write `<work>/report.md`. Expect a third of contested claims to
move; a red team that refutes nothing was not adversarial.

**Proposals** go in a separate section or file: each names the finding it rests on, the mechanism
(hook, script, CLAUDE.md line, model routing, skill), the owner, and how you would know it worked.

## Privacy gates — verbatim, not negotiable

- The corpus is read-only. Nothing writes into `~/.claude`, `~/.codex`, or a shared archive; if
  the corpus is a git repo, `git status` on it must be clean at the end.
- The work dir lives outside every git repo (`pipeline.py` enforces; if you set `--work`, keep it
  so). Never `git add` a work dir or its report; the report is handed to the user as a file path
  or a private artifact, never committed by this skill.
- Run `python3 $SKILL/tools/secret_scan.py <work dir>` and `... secret_scan.py <work>/report.md`
  before the report goes anywhere; redact HIGH findings (write `[credential present, redacted]`),
  tell the user to rotate what was found. Lane and red-team prompts already forbid copying
  credentials into notes.
- Data leaving the machine: only clipped renders/quotes sent to the user's own model provider by
  `grade.py` and by the Workflow agents. No other network calls exist in the tools; do not add any.
- Numbers are list-price shadow cost — say so in the report; people are on subscriptions.
- Names + dollars + tiers stays with the audience from step 4.

## Done when

`<work>/report.md` exists with a red-team log, secret scan on it is clean, and the user has the
work dir path, the headline numbers, and the first action. Report token cost of the review itself
(lanes + red team + grading) alongside.

## Exporter-markdown corpus (shared archive)

`python3 $SKILL/tools/extract_exporter_md.py <root> --out <work>/grade_in.jsonl` replaces quant +
render; numbers come from the archive's sidecar CSVs. Stratify per person (tag = person) and build
`lanes.json` by hand in the same shape (`{key, dir, extra}`) — `METHODOLOGY.md` §2.6 lists the lane
set that covers an org, including the corpus-privacy and pipeline-health lanes.
