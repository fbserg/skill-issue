#!/usr/bin/env python3
"""Carry gates from skills/claude/* into their skills/codex/* counterparts.

Design (from the ctxeng audit, §2 items 3-5): the codex tree is hand-authored
and deliberately thinner than the claude tree — method/choreography prose is
allowed to differ per tier, and this script does not touch it. But an
irreversible-action gate (a state machine, a kill switch, a watchdog) is not
"method" — it is the interface Codex is supposed to honor before it takes an
action a human can't cheaply undo (merging, filing issues, discarding a lane).
Those gates must be carried through verbatim, or the codex tier is strictly
weaker than the tier that gates it.

This is NOT a full-file transpiler. It does not invent codex prose from claude
prose — the two trees differ far too much in voice and structure for a
mechanical rewrite to be honest. Instead it owns a small, explicit GATES
table: each entry names one gate, the exact claude-side text that is its
source of truth, where that text lives (for --check to catch drift), and the
codex-side insertion point. A small TERMINOLOGY table substitutes the handful
of Claude-only tool/agent names that appear inside gate text (Sonnet,
`agentType: "worker"`, the Agent tool, `~/.claude/logs`) for their Codex
equivalents; nothing else in the file is touched.

Usage:
    scripts/generate-codex-skills.py --check   # exit 1 if any gate is missing
    scripts/generate-codex-skills.py --write   # insert missing gates in place
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ORDINAL_ITEM_RE = re.compile(r"^(\d+)\. ", re.MULTILINE)


def renumber_ordinal_block(text: str, block_start: int) -> str:
    """Renumber sequential `N. ` top-level items from block_start to the next
    heading (or end of file), so an inserted gate item doesn't leave two `2.`s.
    Only touches lines that already look like `<digits>. ` — gate comment
    lines and wrapped continuation text don't match and are left alone."""
    heading_pos = text.find("\n## ", block_start)
    end = heading_pos if heading_pos != -1 else len(text)
    segment = text[block_start:end]
    counter = [0]

    def _renumber(m: re.Match) -> str:
        counter[0] += 1
        return f"{counter[0]}. "

    renumbered = ORDINAL_ITEM_RE.sub(_renumber, segment)
    return text[:block_start] + renumbered + text[end:]

REPO_ROOT = Path(__file__).resolve().parents[1]

TERMINOLOGY = {
    '`agentType: "worker"` — Sonnet at `effort: medium`; the agent type carries the model, no\n  separate `model:` needed): ': "): ",
    "Sonnet lane-runner": "Codex sub-agent",
    "a Sonnet **lane-runner**": "a Codex sub-agent",
    "several\n  `Agent` tool calls in one assistant turn": "several sub-agent dispatches in one turn",
    "`Agent` tool": "sub-agent dispatch",
    "~/.claude/logs": "~/.codex/logs",
    "one persistent `Monitor`": "one persistent background watch loop",
    "`TaskOutput`": "a job status check",
}


def apply_terminology(text: str) -> str:
    for claude_term, codex_term in TERMINOLOGY.items():
        text = text.replace(claude_term, codex_term)
    return text


class Gate:
    def __init__(self, skill: str, gate_id: str, claude_path: str,
                 claude_anchor: str, claude_end_anchor: str,
                 codex_path: str, codex_marker: str,
                 codex_insert_after: str, codex_replace: str | None = None,
                 renumber_after_heading: str | None = None):
        self.skill = skill
        self.gate_id = gate_id
        self.claude_path = claude_path
        self.claude_anchor = claude_anchor
        self.claude_end_anchor = claude_end_anchor
        self.codex_path = codex_path
        self.codex_marker = codex_marker
        self.codex_insert_after = codex_insert_after
        self.codex_replace = codex_replace
        # If set, an ordinal-list heading (e.g. "## Implement") whose numbered
        # items get renumbered after this gate is spliced into the list —
        # the gate text carries its own claude-side "N. " prefix, which would
        # otherwise collide with the codex list's own numbering.
        self.renumber_after_heading = renumber_after_heading

    def extract_claude_text(self) -> str:
        text = (REPO_ROOT / self.claude_path).read_text(encoding="utf-8")
        start = text.index(self.claude_anchor)
        end = text.index(self.claude_end_anchor, start)
        return text[start:end].strip()

    def rendered_block(self) -> str:
        source = self.extract_claude_text()
        body = apply_terminology(source)
        return f"<!-- gate:{self.gate_id} carried from {self.claude_path} -->\n{body}"


GATES = [
    Gate(
        skill="resolve-issue",
        gate_id="draft-state-gate",
        claude_path="skills/claude/resolve-issue/SKILL.md",
        claude_anchor="**Finalize gate: repo checks pass",
        claude_end_anchor="\n\nPR body sections:",
        codex_path="skills/codex/resolve-issue/SKILL.md",
        codex_marker="draft-state-gate",
        codex_insert_after="6. Mark the PR ready only after checks pass.",
        codex_replace="6. Mark the PR ready only after checks pass.",
    ),
    Gate(
        skill="resolve-issue",
        gate_id="amendment-repoll",
        claude_path="skills/claude/resolve-issue/SKILL.md",
        claude_anchor="2. **Amendment re-poll, before any commit.**",
        claude_end_anchor="\n3. *Before any code*",
        codex_path="skills/codex/resolve-issue/SKILL.md",
        codex_marker="amendment-repoll",
        codex_insert_after="1. Create branch `fix/issue-<N>-<short-slug>` in a worktree.",
        codex_replace=None,
        renumber_after_heading="## Implement",
    ),
    Gate(
        skill="issue",
        gate_id="stop-label-check",
        claude_path="skills/claude/issue/SKILL.md",
        claude_anchor="**Before dispatching each new wave**, check the",
        claude_end_anchor="Beyond the `gh` guard/list calls above",
        codex_path="skills/codex/issue/SKILL.md",
        codex_marker="stop-label-check",
        codex_insert_after=(
            "8. For a batch, dispatch independent `resolve-issue` workers concurrently, "
            "cap concurrency at four, and await the wave before starting another. Each "
            "worker owns its worktree and full issue lifecycle."
        ),
        codex_replace=None,
    ),
    Gate(
        skill="issue",
        gate_id="pulse-watchdog",
        claude_path="skills/claude/issue/SKILL.md",
        claude_anchor="**Watchdog — arm it BEFORE dispatching wave 1",
        claude_end_anchor="- **Idempotent.**",
        codex_path="skills/codex/issue/SKILL.md",
        codex_marker="pulse-watchdog",
        codex_insert_after=(
            "11. With three or more lanes, keep a visible ledger and actively monitor "
            "lane status. Restart a dead lane through `resolve-issue --resume`; never "
            "discard its worktree or GitHub state."
        ),
        codex_replace=None,
    ),
]

# The one gate REWRITE (item #5): codex/blitz's DONE gate currently contradicts
# its own claude source (per-follow-up `gh issue create` vs "findings return
# batched, never as issue confetti"). Handled separately from GATES because it
# replaces contradictory text rather than inserting missing text.
BLITZ_REWRITE = {
    "skill": "blitz",
    "claude_path": "skills/claude/blitz/SKILL.md",
    "claude_anchor": "- **Findings return batched, never as issue confetti.**",
    "claude_end_anchor": "\n- **3+ background lanes",
    "codex_path": "skills/codex/blitz/SKILL.md",
    "codex_old": (
        "- Any FOLLOW-UP a lane surfaces is filed via `gh issue create` (label "
        "`follow-up`) before that lane may report `DONE`. A follow-up left only "
        "in transcript prose counts as dropped."
    ),
}


def gate_present(codex_text: str, marker: str) -> bool:
    return f"gate:{marker}" in codex_text or f"<!-- gate:{marker}" in codex_text


def check() -> list[str]:
    problems = []
    for gate in GATES:
        codex_text = (REPO_ROOT / gate.codex_path).read_text(encoding="utf-8")
        if not gate_present(codex_text, gate.codex_marker):
            problems.append(f"{gate.codex_path}: missing gate '{gate.gate_id}' (source {gate.claude_path})")
    blitz_text = (REPO_ROOT / BLITZ_REWRITE["codex_path"]).read_text(encoding="utf-8")
    if BLITZ_REWRITE["codex_old"] in blitz_text:
        problems.append(
            f"{BLITZ_REWRITE['codex_path']}: still carries the per-follow-up "
            "gh issue create rule that skills/claude/blitz/SKILL.md forbids"
        )
    return problems


def write() -> None:
    for gate in GATES:
        codex_file = REPO_ROOT / gate.codex_path
        text = codex_file.read_text(encoding="utf-8")
        if gate_present(text, gate.codex_marker):
            continue
        block = gate.rendered_block()
        if gate.codex_replace:
            assert gate.codex_replace in text, f"anchor not found in {gate.codex_path}: {gate.codex_replace!r}"
            text = text.replace(gate.codex_replace, block, 1)
        else:
            assert gate.codex_insert_after in text, f"anchor not found in {gate.codex_path}: {gate.codex_insert_after!r}"
            text = text.replace(gate.codex_insert_after, gate.codex_insert_after + "\n\n" + block, 1)
        if gate.renumber_after_heading:
            heading_pos = text.index(gate.renumber_after_heading)
            list_start = text.index("\n", heading_pos) + 1
            text = renumber_ordinal_block(text, list_start)
        codex_file.write_text(text, encoding="utf-8")
        print(f"wrote gate '{gate.gate_id}' into {gate.codex_path}")

    blitz_file = REPO_ROOT / BLITZ_REWRITE["codex_path"]
    text = blitz_file.read_text(encoding="utf-8")
    if BLITZ_REWRITE["codex_old"] in text:
        claude_text = (REPO_ROOT / BLITZ_REWRITE["claude_path"]).read_text(encoding="utf-8")
        start = claude_text.index(BLITZ_REWRITE["claude_anchor"])
        end = claude_text.index(BLITZ_REWRITE["claude_end_anchor"], start)
        new_block = apply_terminology(claude_text[start:end].strip())
        text = text.replace(BLITZ_REWRITE["codex_old"], new_block, 1)
        blitz_file.write_text(text, encoding="utf-8")
        print(f"rewrote confetti gate in {BLITZ_REWRITE['codex_path']}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="exit 1 if any gate is missing/stale")
    group.add_argument("--write", action="store_true", help="insert missing gates in place")
    args = parser.parse_args()

    if args.write:
        write()
        return 0

    problems = check()
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print(f"OK {len(GATES) + 1} gate(s) present across the codex tree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
