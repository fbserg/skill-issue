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

--check does a real content comparison (extracted claude text, terminology-
substituted, ordinal-normalized) against what is actually sitting in the
codex file after each gate marker — not just "is the marker present". A
gate whose claude source changed since the last --write is reported as
drift, exactly like a missing gate.

--write is all-or-nothing: every gate's claude-side anchor is resolved and
every codex-side target file is re-rendered in memory first; only if all of
that succeeds does it touch disk. It repairs stale gates (re-splices fresh
content over the old block) instead of skipping them just because the marker
is present.

Usage:
    scripts/generate-codex-skills.py --check   # exit 1 if any gate is missing or stale
    scripts/generate-codex-skills.py --write   # insert/repair gates in place, atomically
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ORDINAL_ITEM_RE = re.compile(r"^(\d+)\. ", re.MULTILINE)
LEADING_ORDINAL_RE = re.compile(r"^\d+\. ")


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


def normalize_ordinal(text: str) -> str:
    """Strip a leading `<digits>. ` so ordinal-renumbered gate items compare
    equal regardless of which number they landed on."""
    return LEADING_ORDINAL_RE.sub("N. ", text, count=1)


REPO_ROOT = Path(__file__).resolve().parents[1]

TERMINOLOGY = {
    '`agentType: "worker"` — Sonnet at `effort: medium`; the agent type carries the model, no\n  separate `model:` needed): ': "): ",
    "Sonnet lane-runner": "Codex sub-agent",
    "a Sonnet **lane-runner**": "a Codex sub-agent",
    "several\n  `Agent` tool calls in one assistant turn": "several sub-agent dispatches in one turn",
    "`Agent` tool": "sub-agent dispatch",
    "~/.claude/logs": "~/.codex/logs",
    "one persistent `Monitor`": "one persistent background watch loop",
    (
        "`claude agents --json\n     --cwd <lane-worktree>` (never `TaskOutput` "
        "— deprecated, unavailable to\n     subagents, and returns a transcript "
        "symlink that can overflow this\n     session's context on read)"
    ): "a job status check",
    "`TaskOutput`": "a job status check",
    "`TaskStop` it **first**": "stop it **first**",
    "`TaskStop` the monitor": "stop the monitor",
}


def apply_terminology(text: str) -> str:
    for claude_term, codex_term in TERMINOLOGY.items():
        text = text.replace(claude_term, codex_term)
    return text


def _find_anchor(text: str, anchor: str, *, path: str) -> int:
    """Locate `anchor` in `text`, tolerant of the source having been
    reflowed (line-wrapped) since the anchor was written: internal runs of
    whitespace in the anchor match any run of whitespace in the text. Fails
    loudly, naming the unresolved anchor, instead of silently falling back
    to some other position."""
    # Preserve every whitespace *run* in the anchor (so a required leading
    # "\n" still requires whitespace, not nothing) but let it match any
    # equivalent run in the source, so pure reflow (a wrapped line) doesn't
    # break the match. Only collapses whitespace runs, never drops one.
    parts = re.split(r"(\s+)", anchor)
    pattern = re.compile("".join(
        r"\s+" if part.strip() == "" and part != "" else re.escape(part)
        for part in parts
    ))
    m = pattern.search(text)
    if not m:
        raise ValueError(f"{path}: anchor not found: {anchor!r}")
    return m.start()


NEXT_ORDINAL_RE = re.compile(r"\n\d+\. ")
NEXT_BULLET_RE = re.compile(r"\n- ")


def _next_boundary(text: str, start: int) -> int:
    """Find where a spliced-in gate body ends, scanning forward from `start`.
    A gate body never starts a line with `<digit>. `, `- `, or `## ` itself
    right after its own first line (those only appear as *following*
    structure — the next ordinal list item, the next top-level bullet, the
    next heading, or the next gate's own marker), and never contains a blank
    line internally (verified for every gate in GATES/BLITZ_REWRITE). So the
    nearest of those is the true end of this gate's body — not just the next
    blank line, which for a gate spliced into a tight list (no blank lines
    between items, ordinal or bulleted) would swallow every item after it.
    Bodies that are themselves a single bullet line (bullet_prefix gates)
    are one line with no internal `\\n- `, so this still finds the *next*
    bullet correctly."""
    candidates = []
    for literal in ("\n<!-- gate:", "\n## ", "\n\n"):
        i = text.find(literal, start)
        if i != -1:
            candidates.append(i)
    for pattern in (NEXT_ORDINAL_RE, NEXT_BULLET_RE):
        m = pattern.search(text, start)
        if m:
            candidates.append(m.start())
    return min(candidates) if candidates else len(text)


class Gate:
    # Generous per-gate ceiling on extracted body length, in characters. A
    # real end-anchor match is always a small, known span; a silent
    # end-anchor miss that falls through to something far away (or EOF)
    # blows straight past this and fails loudly instead of splicing garbage
    # into the codex file. Override per-gate for short single-line gates so
    # a wrong-anchor EOF runaway is caught even on a small source file.
    DEFAULT_MAX_LEN = 3000

    def __init__(self, skill: str, gate_id: str, claude_path: str,
                 claude_anchor: str, claude_end_anchor: str,
                 codex_path: str, codex_marker: str,
                 codex_insert_after: str, codex_replace: str | None = None,
                 renumber_after_heading: str | None = None,
                 bullet_prefix: str | None = None,
                 max_len: int | None = None):
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
        self.bullet_prefix = bullet_prefix
        self.max_len = max_len if max_len is not None else self.DEFAULT_MAX_LEN

    def extract_claude_text(self) -> str:
        text = (REPO_ROOT / self.claude_path).read_text(encoding="utf-8")
        start = _find_anchor(text, self.claude_anchor, path=self.claude_path)
        end = _find_anchor(text, self.claude_end_anchor, path=self.claude_path)
        if end <= start:
            raise ValueError(
                f"{self.claude_path}: end anchor {self.claude_end_anchor!r} "
                f"found before start anchor {self.claude_anchor!r} for gate "
                f"'{self.gate_id}'"
            )
        extracted = text[start:end].strip()
        if len(extracted) > self.max_len:
            raise ValueError(
                f"{self.claude_path}: gate '{self.gate_id}' extracted "
                f"{len(extracted)} chars, over the {self.max_len}-char ceiling "
                f"— end anchor {self.claude_end_anchor!r} likely didn't match "
                "the intended nearby text and extraction ran long"
            )
        return extracted

    def rendered_body(self) -> str:
        source = self.extract_claude_text()
        body = apply_terminology(source)
        if self.bullet_prefix:
            body = self.bullet_prefix + body
        return body

    def marker_comment(self) -> str:
        return f"<!-- gate:{self.gate_id} carried from {self.claude_path} -->"

    def rendered_block(self) -> str:
        return f"{self.marker_comment()}\n{self.rendered_body()}"

    def comparable(self, body: str) -> str:
        return normalize_ordinal(body) if self.renumber_after_heading else body

    def find_existing_body(self, codex_text: str) -> str | None:
        """Return the current body text already spliced in for this gate, or
        None if the marker isn't present. Relies on gate bodies never
        containing a blank line internally (verified for all gates below):
        the body runs from right after the marker's own line to the next
        blank line."""
        marker = self.marker_comment()
        idx = codex_text.find(marker)
        if idx == -1:
            return None
        body_start = idx + len(marker) + 1  # skip the trailing \n
        body_end = _next_boundary(codex_text, body_start)
        return codex_text[body_start:body_end]


GATES = [
    Gate(
        skill="resolve-issue",
        gate_id="draft-state-gate",
        claude_path="docs/resolve-issue-full-pipeline.md",
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
        claude_path="docs/resolve-issue-full-pipeline.md",
        claude_anchor="2. **Amendment re-poll, before any commit.**",
        claude_end_anchor="\n3. *Before any code*",
        codex_path="skills/codex/resolve-issue/SKILL.md",
        codex_marker="amendment-repoll",
        codex_insert_after="1. Create branch `fix/issue-<N>-<short-slug>` in a worktree.",
        codex_replace=None,
        renumber_after_heading="## Implement",
    ),
    Gate(
        skill="resolve-issue",
        gate_id="negative-control",
        claude_path="docs/resolve-issue-full-pipeline.md",
        claude_anchor="- **Negative control:**",
        claude_end_anchor="\n- Commit tests on the same branch",
        codex_path="skills/codex/resolve-issue/SKILL.md",
        codex_marker="negative-control",
        codex_insert_after=(
            "6. Prove at least one new test discriminates the fix by temporarily "
            "reversing or disabling its core behavior, observing failure, "
            "restoring it, and confirming green."
        ),
        codex_replace=(
            "6. Prove at least one new test discriminates the fix by temporarily "
            "reversing or disabling its core behavior, observing failure, "
            "restoring it, and confirming green."
        ),
        renumber_after_heading="## Implement",
    ),
    Gate(
        skill="epic-plan",
        gate_id="dont-invent-scope",
        claude_path="skills/claude/epic-plan/SKILL.md",
        claude_anchor="**Don't invent scope.**",
        claude_end_anchor="\n3. **No PRD bloat.**",
        codex_path="skills/codex/epic-plan/SKILL.md",
        codex_marker="dont-invent-scope",
        codex_insert_after="- Do not implement code.",
        codex_replace=None,
        bullet_prefix="- ",
        max_len=250,
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


def _blitz_rendered() -> str:
    claude_text = (REPO_ROOT / BLITZ_REWRITE["claude_path"]).read_text(encoding="utf-8")
    start = _find_anchor(claude_text, BLITZ_REWRITE["claude_anchor"], path=BLITZ_REWRITE["claude_path"])
    end = _find_anchor(claude_text, BLITZ_REWRITE["claude_end_anchor"], path=BLITZ_REWRITE["claude_path"])
    return apply_terminology(claude_text[start:end].strip())


def check() -> list[str]:
    problems = []
    for gate in GATES:
        try:
            expected_body = gate.rendered_body()
        except ValueError as exc:
            problems.append(str(exc))
            continue
        codex_text = (REPO_ROOT / gate.codex_path).read_text(encoding="utf-8")
        existing_body = gate.find_existing_body(codex_text)
        if existing_body is None:
            problems.append(f"{gate.codex_path}: missing gate '{gate.gate_id}' (source {gate.claude_path})")
        elif gate.comparable(existing_body.strip()) != gate.comparable(expected_body.strip()):
            problems.append(
                f"{gate.codex_path}: gate '{gate.gate_id}' is stale — codex text no "
                f"longer matches {gate.claude_path} (drifted since the last --write)"
            )

    blitz_text = (REPO_ROOT / BLITZ_REWRITE["codex_path"]).read_text(encoding="utf-8")
    try:
        expected_rewrite = _blitz_rendered()
    except ValueError as exc:
        problems.append(str(exc))
        expected_rewrite = None
    if expected_rewrite is not None:
        if BLITZ_REWRITE["codex_old"] in blitz_text:
            problems.append(
                f"{BLITZ_REWRITE['codex_path']}: still carries the per-follow-up "
                "gh issue create rule that skills/claude/blitz/SKILL.md forbids"
            )
        elif expected_rewrite not in blitz_text:
            problems.append(
                f"{BLITZ_REWRITE['codex_path']}: confetti-gate rewrite is stale — "
                f"no longer matches {BLITZ_REWRITE['claude_path']}"
            )
    return problems


def _plan_gate_write(gate: Gate, text: str) -> str:
    """Return `text` with this gate's block inserted (if absent) or repaired
    (if stale/present). Raises loudly if an anchor this gate depends on is
    not found — never silently no-ops."""
    block = gate.rendered_block()
    existing_body = gate.find_existing_body(text)

    if existing_body is not None:
        if gate.comparable(existing_body.strip()) == gate.comparable(gate.rendered_body().strip()):
            return text  # already fresh, nothing to do
        marker = gate.marker_comment()
        marker_idx = text.index(marker)
        body_start = marker_idx + len(marker) + 1
        body_end = _next_boundary(text, body_start)
        text = text[:marker_idx] + block + text[body_end:]
    elif gate.codex_replace:
        if gate.codex_replace not in text:
            raise ValueError(f"anchor not found in {gate.codex_path}: {gate.codex_replace!r}")
        text = text.replace(gate.codex_replace, block, 1)
    else:
        if gate.codex_insert_after not in text:
            raise ValueError(f"anchor not found in {gate.codex_path}: {gate.codex_insert_after!r}")
        text = text.replace(gate.codex_insert_after, gate.codex_insert_after + "\n\n" + block, 1)

    if gate.renumber_after_heading:
        heading_pos = text.index(gate.renumber_after_heading)
        list_start = text.index("\n", heading_pos) + 1
        text = renumber_ordinal_block(text, list_start)
    return text


def write() -> None:
    """All-or-nothing: every gate is resolved and every target file's new
    content is computed in memory first. Only after every gate across every
    file succeeds does anything touch disk."""
    # Group gates by codex file so each file's edits compose before writing.
    by_file: dict[Path, str] = {}
    touched: dict[Path, list[str]] = {}

    def _load(path_str: str) -> Path:
        path = REPO_ROOT / path_str
        if path not in by_file:
            by_file[path] = path.read_text(encoding="utf-8")
            touched[path] = []
        return path

    for gate in GATES:
        path = _load(gate.codex_path)
        before = by_file[path]
        after = _plan_gate_write(gate, before)
        if after != before:
            touched[path].append(gate.gate_id)
        by_file[path] = after

    blitz_path = _load(BLITZ_REWRITE["codex_path"])
    blitz_text = by_file[blitz_path]
    expected_rewrite = _blitz_rendered()
    if BLITZ_REWRITE["codex_old"] in blitz_text:
        blitz_text = blitz_text.replace(BLITZ_REWRITE["codex_old"], expected_rewrite, 1)
        touched[blitz_path].append("confetti-gate-rewrite")
        by_file[blitz_path] = blitz_text
    elif expected_rewrite not in blitz_text:
        raise ValueError(
            f"{BLITZ_REWRITE['codex_path']}: confetti-gate rewrite anchor not "
            f"found and old text not present either — can't repair in place"
        )

    # Every gate resolved and every file re-rendered without error. Commit.
    for path, text in by_file.items():
        if touched[path]:
            path.write_text(text, encoding="utf-8")
            for gate_id in touched[path]:
                print(f"wrote gate '{gate_id}' into {path.relative_to(REPO_ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true", help="exit 1 if any gate is missing/stale")
    group.add_argument("--write", action="store_true", help="insert/repair missing or stale gates in place")
    args = parser.parse_args()

    if args.write:
        try:
            write()
        except ValueError as exc:
            print(f"FAIL: {exc}", file=sys.stderr)
            return 1
        return 0

    problems = check()
    if problems:
        for p in problems:
            print(f"FAIL: {p}", file=sys.stderr)
        return 1
    print(f"OK {len(GATES) + 1} gate(s) present and current across the codex tree")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
