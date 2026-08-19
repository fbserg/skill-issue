# AI usage review: methodology

How to review a body of AI-assistant transcripts (Claude Code, Codex CLI, claude.ai exports) and come out with findings that survive an adversarial check. Written after two runs: a 33-person org archive in exporter-markdown format (Aug 2026) and one person's own month of local transcripts. Both runs, their numbers and their corrections are the calibration for what follows. Self-run red team: 111 claim parts, 70 verified, 21 partially, 18 refuted, 2 unverifiable.

The whole thing is LLM-run. A human sets scope, reads the final report, and decides. Everything between is scripts plus fan-out agents with written prompts.

## 0. What you get

- A quantitative picture per person/project/model: tokens, list-price shadow cost, session shapes, tool mix, automation share, sub-agent share, time-of-day.
- Per-person or per-project profiles: what works, what does not, risk, first action. Every claim cites a file and a quote.
- Theme reads across the whole corpus: verification, prompting/front-loading, waste and failure modes, orchestration, Codex usage, automations, security/privacy.
- A rubric grade per sampled session (six dimensions, risk flags, waste signals) so cohorts can be compared on the same scale.
- A red-team log: which claims were attacked, which fell, what changed.
- A report and an action plan.

Time: 4–6 hours wall-clock for a corpus of ~10k sessions if the fan-out runs in parallel. Token cost of the review itself: the org run used ~30 Sonnet lanes + 46 red-team agents (~5–8 M tokens); the self run used 12 lanes + 16 red-team agents (~2.6 M). Grading is cheap once the agent preamble is stripped (~$0.16 per session on Sonnet).

## 1. Inputs and formats

Three formats show up. The tools handle all three.

| Source | Where | Shape | Gotchas |
|---|---|---|---|
| Claude Code | `~/.claude/projects/<proj>/<session>.jsonl` | one JSON per line: `type` user/assistant/summary, `message.content` blocks (text, tool_use, tool_result, thinking), `message.usage` (input, cache_creation_input_tokens, cache_read_input_tokens, output), `timestamp`, `isSidechain`, `cwd`, `gitBranch` | sub-agent transcripts live in `<session>/subagents/**/*.jsonl` (nested); rewinds/forks create sibling files with the same start second and title; teammate messages, idle notifications and task notifications arrive as **user-role** turns |
| Codex CLI | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | `session_meta` (cwd, originator codex-tui / codex_exec), `turn_context` (model, effort), `response_item` (message role user/assistant, function_call, function_call_output), `event_msg` `token_count` with cumulative `total_token_usage` | first user message is often the injected AGENTS.md / `<recommended_plugins>` boilerplate; `spawn_agent`/`send_message` payloads are opaque blobs, so Codex sub-agents are invisible; no tool markers in the exporter's md rendering |
| Exporter markdown (shared org archive) | `<user>/YYYY-MM-DD.md` + `metrics/YYYY-MM-DD.csv` | `### HH:MM–HH:MM · claude|codex · title`, `**User:**/**Assistant:**`, `→ used tool X` | redaction may eat prose (`[REDACTED:entropy]`); sub-agent tokens skipped; forks double-count; some people hand-paste in their own format |

Decide the window (a month is enough to see habits; six months to see adoption) and the population (everyone with a folder, or one person).

## 2. Pipeline

```
inventory → quant → automation families → command scan → sample → render → lanes ─┐
                                                                    └→ rubric grade ┘→ synthesis → red team → adjudicate → report v2 → proposals
```

Each step writes files into one work dir. Nothing writes back into the corpus. If the corpus is a shared repo, treat it read-only and never push.

### 2.1 Inventory and quant (`tools/quant.py`)

`python3 tools/quant.py --days 31 --out ./work` walks `~/.claude/projects` (top-level and nested) and `~/.codex/sessions`, and writes `work/sessions.jsonl`, one row per file: source, nested flag, project, session id, first/last timestamp, tokens per model (input, cache-write, cache-read, output), user/assistant turns, tool counts, first prompt, interrupts, API errors, list-price cost two ways (`cost_new` = input+cache-write+output; `cost_full` adds cache reads).

For exporter markdown use `tools/extract_exporter_md.py <root>` (sessions with text) plus the sidecar CSVs for tokens.

Then `python3 tools/summarize.py ./work` aggregates into `work/quant_summary.txt`: totals by source; per project with dominant models; per day; hour-of-day and weekend share for human-started sessions; session-shape stats (0/≤1 human turns, duration median/p90, >8 h, >1,000 assistant turns, top-1% cost share); model mix; tool call counts; Codex effort levels; biggest sessions. It also writes `automation.txt` and `families.json` (§2.2).

Price at public list per model (opus/fable 15/75, cache-write 18.75, cache-read 1.5; sonnet 3/15/3.75/0.3; haiku 1/5/1.25/0.1; gpt-5 class 1.25/10/1.25/0.125 per M). Say in the report that it is a comparison unit, since people are on subscriptions. Report both `cost_new` (comparable to the org exporter's basis) and `cost_full` (what long contexts really re-bill).

### 2.2 Automation families

`summarize.py` groups top-level sessions by opening-prompt prefix (`--family-prefix 40 --family-min 20`). Anything that repeats 20+ times with the same first 40 characters is an automation (email triage, photo ID, cron reviewers, pings, graders). Table: family, runs, new tokens, cost, share, dominant model, source. Do this before anything else: it tells you which "sessions" are robots, and it usually removes 70% of the session count from the human denominator. In the org run 70% of sessions had ≤1 human turn and were review harnesses, cron and hooks; in the self run 3,397 of 8,449 sessions were one email classifier.

Watch for framework boilerplate masquerading as a family (Codex `<recommended_plugins>` stub) and for "user turns" that are teammate traffic.

### 2.3 Command scan (`tools/cmd_scan.py ./work`)

Regex over every shell command any tool issued (Claude Bash, Codex exec/apply_patch): force push, filter-repo, DROP/DELETE/TRUNCATE, FLUSHDB, kill -9, deploy verbs, ssh targets, gmail sends, `--no-verify`, `--admin`, `rm -rf`, sudo rm. Also counts: commits, pushes, PR creates/merges, test runs, lint, `sleep`, `python -c`, headless `codex exec` / `claude -p`.

Output is noisy on purpose. `python3 tools/risky_digest.py ./work` groups it by pattern into `risky_digest.md` (dedupe on a digit-stripped prefix, timestamps, project, nested/codex flags, example commands); hand that to the verification/risk lane with the instruction to separate real actions from greps, patch bodies and prose. In the self run 10,995 hits reduced to about a dozen real items.

### 2.4 Sample selection

Stratify, do not cherry-pick. `python3 tools/sample.py ./work --per-lane 8 --grade-n 50` does this: per project largest, median, most recent (thirds); automation families and 0-turn sessions excluded from the human sample, two of each family kept for the automation lane; targeted pulls for the theme lanes (top-N by cost, most API errors, most interrupts, shortest openers with many turns, longest openers, parents with most sub-agents plus one child each, Codex TUI vs headless). It writes `select.json` (`path`, `tag`, optional per-item `budget`) and `lanes.json` (lane key, directory, and a lane brief carrying the corpus numbers). For a multi-person archive stratify per person instead — same shape, tag = person.

Sizes that worked: 6–12 sessions per person lane; 8–17 per theme lane; 40–60 for the rubric grade (two per person is the floor for a per-person read; call it "indicative").

### 2.5 Render (`tools/render.py`)

`python3 tools/render.py --sessions work/sessions.jsonl --select work/select.json --outdir work/md --budget 50000 --grade-jsonl work/grade_in.jsonl --grade-tags grade`

Produces one markdown per session with a header (date, span, source, project, model, turn counts, tokens, cost) and the body: `**User** [hh:mm]:`, `**Assistant:**`, `→ used tool X: <arg summary>`, `← result (n chars) first line`. Budget clips head 60% / tail 40% and marks the elision. Sub-agent turns are labelled. Codex renders show exec/apply_patch calls and outputs. Automation samples get a 12k budget.

Known limit: a 100+ agent parent session elides most of its middle even at 50k. If delegation quality of mega-sessions matters, extract Agent/spawn_agent calls separately with a script.

### 2.6 Lanes (Workflow fan-out)

One agent per lane, Sonnet-class at medium effort (`worker`), reading every file in its lane directory plus `quant_summary.txt` and the automation table, writing a long-form markdown report and returning a structured JSON (headline, strengths, weaknesses, risks, waste, suggestions, quotes, numbers). `workflows/lanes.js` is the script; it takes `{base, who, tz, lanes}` as args (`lanes` = `lanes.json`) and hardcodes nothing.

Lane set that covers a corpus:

- **Per person / per project** (one each for heavy users; light users grouped 3–4 per lane). Sections: what was worked on; how the human directs the AI (openers, steering, delegation, verification); what worked; what did not (thrash, waste, failure modes); risk (destructive, prod, credentials, data); ranked concrete suggestions.
- **Verification and risk**: are "done/verified" claims backed by observed tests, exit codes, browser/DB/API checks; count sessions that accept unverified claims; triage the command-scan digest into real incidents.
- **Prompting, front-loading, steering**: what arrives late that belonged in turn 1; corrections; interrupts; plan mode / AskUserQuestion / effort steering use; what an opening template should contain for this person.
- **Waste and failure modes**: the most expensive sessions and what they bought; retries; dead sessions; never-restarted contexts; automation artifacts that only look like waste.
- **Orchestration and delegation**: quality of sub-agent briefs; does the parent verify sub-agent claims; polling loops; resource limits; duplicated lanes; fan-out size vs task.
- **Codex usage** (if present): what it is used for vs Claude, effort levels, headless dispatch, multi-agent, failure modes.
- **Automations**: model fit per family, prompt quality, verification, data sensitivity, cost per run.
- **Security and privacy of the corpus itself** (shared archives): credentials, client data, redaction quality, personal sessions, who can push.
- **Sharing and duplication** (orgs): which tools/skills exist, who owns them, what got re-derived by several people.
- **Pipeline health** (orgs): exporter bugs, staleness, forks, format drift; git history of the archive.

Lane prompt rules that mattered: "read EVERY file fully"; "every claim cites file + short verbatim quote or the `→ used tool` line"; "facts only if you saw them"; "do not read outside the lane dir except the context files"; "write to `<workdir>/lanes/<lane>.md` only"; "never copy a credential into the report — write `[credential present, redacted]`". Give the lane its numbers (month totals, family counts) so it can put a sample in proportion; `sample.py` bakes them into each lane brief.

### 2.7 Rubric grade (`tools/grade.py`)

`python3 tools/grade.py work/grade_in.jsonl --out work/graded.jsonl --model sonnet --jobs 5 --context work/context.txt`

Headless `claude -p` with `--tools "" --strict-mcp-config --disable-slash-commands --system-prompt` (drops the ~78k-token agent preamble; without that each grade costs ~50× more). `context.txt` is one paragraph naming the org/person, the projects and the transcript conventions; the rubric is fixed so cohorts stay comparable.

Dimensions 0–4: goal clarity, context grounding, verification, iteration efficiency, outcome, delegation fit. Plus `gradable`/reason, work type, risk flags (credentials_in_transcript, production_data_touched, destructive_operation, unverified_claim_treated_as_done, client_prod_system_touched, security_relevant_change, large_unreviewed_change, model_error_accepted_by_human), waste signals (repeated_identical_request, thrash_loop, rework_of_completed_task, premature_done_claim, context_lost_and_restarted, oversized_scope_for_one_session, trivial_task_for_expensive_model, assistant_did_work_human_never_read), up to 3 evidence quotes, a one-line highlight, a coaching note.

`tools/digest.py work/graded.jsonl` prints per-dimension means, flag counts, and a per-person strongest/weakest session with no composite score, no leaderboard, no cost column.

Calibration so far: Sonnet test-retest within one point on all dimensions; every spot-checked quote verbatim in source; grader agreed 12/12 with hand-labelled gradability. Reference points: the org run, 54 gradable sessions: verification 2.74, other five 3.19–3.54. One heavy solo orchestrator, 41 sessions: verification 3.71, goal clarity 3.00, iteration 3.02, outcome 3.56, delegation 3.93.

### 2.8 Synthesis (the human-facing draft)

Write the report from the numbers you recomputed yourself plus the lane JSON. Structure that worked: short version (7 bullets) · numbers at a glance · method and caveats (the data-quality facts that change how numbers read) · where the money goes · what is working · what is not · waste itemised · risk and incidents · rubric grades · person-by-person or project-by-project table (what works / what to fix / first action) · automations · action plan (this week / 2–4 weeks / quarter) · appendix of sources. Every incident row: what happened, root gap, file cite.

### 2.9 Red team

Extract 100–150 specific claims from the draft into clusters (numbers, per-person facts, incidents, grades). `examples/claims.example.json` is the shape. One refuter agent per cluster, instructed to **disprove**: recompute numbers from `sessions.jsonl` and spot-check raw files; open the cited transcripts; return per-claim verdicts verified / partially / refuted / unverifiable with evidence and corrected wording. Then one adjudicator per cluster that has contested parts, told to verify against the sources itself and pick report / refuter / both with final wording. `workflows/redteam.js` is the script; args `{base, who, tz, clusters}` with `clusters` in the `claims.example.json` shape.

Add an editorial lane (framing, fairness, anything HR-shaped that should not be) and an independent recompute lane for every headline number.

Tally and publish: verified / partially / refuted / unverifiable counts, what changed, refutations that did not survive, what stays uncertain. Org run: 274 verdict parts, 172 verified, 82 partially, 18 refuted; adjudicators sided with the refuter 51 times, the report 21, split 29. Expect a third of contested claims to move.

Typical things the red team catches: a count that included automation; "since June" that was really July; a plugin cost that was already inside a person's total; a "multi-tenant staging outage" that was a local docker stand; a person-month comparison off by 2× because the other side excluded cache reads or forks; an incident attributed to the wrong step of a chain (who widened the scope vs who executed).

### 2.10 Report v2 and proposals

Apply corrections, keep a red-team log section, republish. Then write proposals separately from the findings: each proposal names the finding it rests on, the mechanism (hook, script, CLAUDE.md line, model routing, skill), the owner, and how you would know it worked.

## 3. Pitfalls, in the order they bit

1. **Session counts count robots.** Always classify automation families first and report human sessions separately.
2. **Forks double-count.** Cluster sessions with identical (start second, title); keep the largest sibling; report the removed share as an upper bound (org: 9.1%).
3. **Sub-agents are half the tokens.** Exporters that skip `isSidechain`/`agentId` under-measure fan-out users. Local runs must include nested files. Codex `spawn_agent` children are not recoverable at all; say so.
4. **Cache reads dominate real spend** (62% in the self run). Report `cost_full` next to `cost_new`, and remember cache reads re-bill every turn of a long context.
5. **User-role turns are not human turns.** Teammate messages, idle and task notifications inflate them; a 266-"user-turn" blitz session was mostly fleet chatter.
6. **Codex has no tool markers in exporter renders**, so any execution-evidence scoring penalises Codex users structurally. The self-run renderer fixes this by reading rollouts directly.
7. **Regex risk scans are 90% noise.** Greps for the words, patch bodies, docs. A reviewer lane must triage them; do not put raw counts in the report.
8. **Deterministic "quality" scorers measure export hygiene.** Two shipped in the org archive correlated r≈0.27 with the LLM grade and gave a dev-stand wipe full safety marks. Keep them as format validators.
9. **Two sessions per person is not a per-person grade.** Label it indicative; use the census for anything that ranks.
10. **Elision hides mega-sessions.** Extract tool-call lists separately when delegation quality of 100+ agent sessions matters.
11. **Lane graders are generous.** The org lanes returned 28/33 profiles at 5/5 on some axis; the tiers came from a human read across lanes, never from the raw scores.
12. **Hooks can block the tooling.** A pretool hook that pattern-matches "find … ~" blocked a heredoc containing report prose; write large files with the file tool, not shell heredocs.
13. **Do not write into a shared archive.** One lane left ten stub files in the repo root; check `git status` of the corpus at the end.
14. **Names + dollars + tiers is management-only.** Coaching travels as a separate sheet without tiers or costs.

## 4. Running it against your own threads (quickstart)

```bash
T=<this skill dir>/tools
python3 $T/pipeline.py --days 31                       # quant → cmd_scan → summarize → select → render → risky_digest → secret_scan
python3 $T/pipeline.py --days 31 --grade --context work/context.txt   # + rubric grade + digest (sends clipped renders to `claude -p`)
```

`pipeline.py` writes to `~/.local/share/usage-review/<date>/` by default and refuses a work dir inside a git work tree. Each step is also a standalone tool (§2). Then, in Claude Code: run `workflows/lanes.js` with `{base, who, tz, lanes: <lanes.json>}`, write the draft, extract claims into the `examples/claims.example.json` shape, run `workflows/redteam.js` with `{base, who, tz, clusters}`, apply corrections, run `tools/secret_scan.py` on the report, publish to its audience.

For an exporter-markdown corpus, replace quant+render with `tools/extract_exporter_md.py <root> --out work/grade_in.jsonl` and the sidecar CSVs for the numbers.

## 5. Privacy

Local transcripts contain credentials people typed, client data, and personal sessions. Keep the work dir out of git (`pipeline.py` enforces it and writes a `.gitignore`), keep the report's names-and-dollars table to its audience, run `tools/secret_scan.py` on the work dir and on the report before anything is shared, redact what it finds, and rotate what you find. The only data that leaves the machine is what the grader and the lane/red-team agents send to your own model provider. In a shared archive, the exporter's defaults (publish every project root) are a consent problem; say so in the report and fix the default.

## 6. Files here

- `tools/pipeline.py` one-shot runner for the steps below (local corpus)
- `tools/quant.py` local Claude + Codex inventory and tokens → `sessions.jsonl`
- `tools/cmd_scan.py` shell-command risk/stat scan → `risky_cmds.jsonl`, `cmd_stats.json`
- `tools/summarize.py` → `quant_summary.txt`, `automation.txt`, `families.json`
- `tools/sample.py` stratified sample → `select.json`, `lanes.json`
- `tools/render.py` compact markdown renders + grade input
- `tools/risky_digest.py` → `risky_digest.md` for the verification lane
- `tools/grade.py` rubric grader (`claude -p`, preamble stripped)
- `tools/digest.py` non-punitive digest of grades
- `tools/secret_scan.py` credential scan of renders/reports before sharing
- `tools/extract_exporter_md.py` extractor for exporter-markdown archives
- `workflows/lanes.js`, `workflows/redteam.js` Workflow scripts, all inputs via `args`
- `examples/claims.example.json` claim-cluster shape for the red team (synthetic)
