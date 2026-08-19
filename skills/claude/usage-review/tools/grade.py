#!/usr/bin/env python3
"""LLM-graded rubric for AI-assistant sessions (rendered by render.py or extract_exporter_md.py). Headless `claude -p`, strict JSON out.

Design notes that matter for cost and honesty:
  * `--tools "" --strict-mcp-config --disable-slash-commands --system-prompt`
    strips the agent preamble (77.9k cached tokens -> 1.5k). Without it every
    grade costs ~50x more.
  * The grader is allowed to answer "not gradable" so export artifacts
    (zero-user-turn sessions, harness rollouts, placeholder files) leave the
    denominator instead of scoring badly.
  * Nothing is aggregated into a single ranking number here; per-dimension
    scores plus free-text notes are the product.
  * Data path: each transcript render (already clipped) is sent to `claude -p`,
    i.e. to the user's own Claude account/provider. Nothing else leaves the
    machine; results are written to --out only.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
import subprocess
import sys

DEFAULT_CONTEXT = """You grade transcripts of people working with AI coding assistants (Claude Code, Codex CLI,
claude.ai). Sub-agent transcripts are usually separate files, so a short parent transcript can hide
delegated work. Transcripts are renderings: user and assistant text, tool calls as
'-> used tool X: <arg summary>' and results as '<- result (n chars) first line'; the middle of a long
session may be elided. Judge the human's working method visible in the transcript, never the
assistant's prose style, never the language used, never how many tokens were spent."""

SYSTEM_PROMPT_TEMPLATE = """{context}

You output one JSON object and nothing else. No markdown fence, no commentary."""

RUBRIC = """Grade this session. Output exactly this JSON shape:

{
  "gradable": true|false,
  "not_gradable_reason": "" | "no_user_turns" | "harness_or_automation" | "placeholder_or_empty" | "too_truncated",
  "work_type": "feature"|"bugfix"|"review"|"research"|"spec"|"qa"|"ops"|"meta"|"other",
  "goal_clarity": 0-4,
  "context_grounding": 0-4,
  "verification": 0-4,
  "iteration_efficiency": 0-4,
  "outcome": 0-4,
  "delegation_fit": 0-4,
  "risk_flags": [ ... ],
  "waste_signals": [ ... ],
  "evidence": ["<= 3 short quotes or paraphrases, translated to English, that justify the lowest and highest score"],
  "highlight": "one English sentence: the single most notable thing a manager should know",
  "coaching_note": "one or two English sentences addressed to the engineer, specific and actionable"
}

Dimension anchors (0 = absent, 2 = partial, 4 = exemplary):
- goal_clarity: did the human state a concrete target, constraints and what 'done' means,
  rather than a vague wish? Short prompts inside an already-established context count as clear.
- context_grounding: did the human point the assistant at the right files/tickets/systems and
  correct wrong assumptions, rather than letting it guess?
- verification: was any claim of success checked against reality (tests run, output read,
  reproduction, browser/DB/API observation, independent reviewer)? An assistant asserting
  "done" with nothing observed is 0-1 even if it looks confident. Codex sessions have no tool
  markers -- judge reported evidence (exit codes, counts, file line numbers), not markers.
- iteration_efficiency: did the work converge, or did it loop on the same failure, re-ask the
  same thing, or redo already-'finished' work? Fewer wasted cycles is higher.
- outcome: did something concrete land (code, spec, decision, verified diagnosis) versus
  ending open, abandoned or with an unverified claim?
- delegation_fit: was the assistant used for work worth delegating (analysis, breadth, tedium)
  versus something the human should have done in 30 seconds or that the model was clearly
  unfit for?

risk_flags (choose from, or add your own short snake_case token):
  credentials_in_transcript, production_data_touched, destructive_operation,
  unverified_claim_treated_as_done, client_prod_system_touched, security_relevant_change,
  large_unreviewed_change, model_error_accepted_by_human

waste_signals (choose from, or add):
  repeated_identical_request, thrash_loop, rework_of_completed_task, premature_done_claim,
  context_lost_and_restarted, oversized_scope_for_one_session, trivial_task_for_expensive_model,
  assistant_did_work_human_never_read

If the transcript contains no user turns at all, or is an automation harness rollout, or is a
placeholder, set gradable=false with the reason and give all numeric dimensions 0.

--- SESSION METADATA ---
user: {user}
date: {date}
project: {project}
tool: {source}
title: {title}
turn counts: user={n_user} assistant={n_assistant} tool_markers={n_tool_calls}
raw length: {chars} characters (clipped for you: {clipped})

--- TRANSCRIPT ---
{text}
--- END TRANSCRIPT ---
"""


def grade_one(rec: dict, model: str, timeout: int, system_prompt: str) -> dict:
    prompt = RUBRIC
    for field in ("user", "date", "project", "source", "title", "n_user",
                  "n_assistant", "n_tool_calls", "chars", "clipped", "text"):
        prompt = prompt.replace("{" + field + "}", str(rec[field]))
    cmd = [
        "claude", "-p",
        "--model", model,
        "--tools", "",
        "--strict-mcp-config",
        "--disable-slash-commands",
        "--system-prompt", system_prompt,
        "--output-format", "json",
    ]
    proc = subprocess.run(
        cmd, input=prompt, capture_output=True, text=True, timeout=timeout
    )
    key = {k: rec[k] for k in ("user", "date", "path", "line", "project", "source",
                               "session_id", "title", "n_user", "n_assistant",
                               "n_tool_calls", "chars", "format")}
    if proc.returncode != 0:
        return {**key, "error": f"cli exit {proc.returncode}: {proc.stderr[-400:]}"}
    try:
        envelope = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {**key, "error": f"cli produced non-json: {proc.stdout[:300]}"}
    raw = envelope.get("result", "")
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return {**key, "error": f"model produced no json object: {raw[:300]}",
                "cost_usd": envelope.get("total_cost_usd")}
    try:
        grade = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        return {**key, "error": f"model json invalid: {exc}: {match.group(0)[:300]}",
                "cost_usd": envelope.get("total_cost_usd")}
    return {**key, "grade": grade, "cost_usd": envelope.get("total_cost_usd"),
            "grader_model": model}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("jsonl")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--context", default=None, help="text file describing the org/person/projects for the grader (replaces the default context paragraph)")
    args = ap.parse_args()
    context = open(args.context, encoding="utf-8").read().strip() if args.context else DEFAULT_CONTEXT
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(context=context)

    recs = [json.loads(line) for line in open(args.jsonl, encoding="utf-8")]
    results: list[dict] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(grade_one, r, args.model, args.timeout, system_prompt): r for r in recs}
        for future in concurrent.futures.as_completed(futures):
            rec = futures[future]
            try:
                res = future.result()
            except Exception as exc:  # noqa: BLE001 - surface, never swallow
                res = {"user": rec["user"], "path": rec["path"], "line": rec["line"],
                       "error": f"{type(exc).__name__}: {exc}"}
            results.append(res)
            tag = "ERR " if "error" in res else "ok  "
            print(f"{tag}{res.get('user')} {res.get('date','')} {str(res.get('title',''))[:50]}",
                  file=sys.stderr)
    with open(args.out, "w", encoding="utf-8") as sink:
        for res in results:
            sink.write(json.dumps(res, ensure_ascii=False) + "\n")
    total = sum(r.get("cost_usd") or 0 for r in results)
    errs = sum(1 for r in results if "error" in r)
    print(f"graded {len(results)} sessions, {errs} errors, ${total:.3f}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
