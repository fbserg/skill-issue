#!/usr/bin/env python3
"""Merge per-lane decision files into the DECISIONS.md ledger.

Three parallel lanes each appending to the one append-only DECISIONS.md
produced three identical merge conflicts (2026-08 epic40 postmortem). The
fix: a lane with a ruling writes `docs/decisions/<lane-or-branch-slug>.md`
(same entry format as the ledger — one or more `## YYYY-MM-DD — Title`
sections) instead of editing DECISIONS.md directly. At close-out, this
script appends every `docs/decisions/*.md` entry into DECISIONS.md in
deterministic order (newest date first, filename ascending as a tiebreak —
matching the ledger's own newest-first convention) and deletes the merged
lane files. `docs/decisions/README.md` is a stub kept to hold the directory
open in git and document the convention; it is never treated as a lane file.

Idempotent: with no lane files pending, this is a no-op (exit 0). Fails
fast, naming the file, on any lane file that doesn't parse as one or more
dated entries — no partial merge, no silent skip.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DECISIONS_PATH = REPO_ROOT / "docs" / "DECISIONS.md"
DECISIONS_DIR = REPO_ROOT / "docs" / "decisions"

STUB_FILENAMES = {"README.md", ".gitkeep"}

# A ledger entry heading: "## 2026-08-18 — Title text"
HEADING_RE = re.compile(r"^(\d{4}-\d{2}-\d{2}) — .+$")
SECTION_SPLIT_RE = re.compile(r"(?m)^## ")

# The ledger's own first *dated* entry — this is the insertion point for
# newly merged entries. Distinct from SECTION_SPLIT_RE because the ledger
# also carries non-dated "## " sections (e.g. a protocol note) that belong
# to the header, not to the entry list.
DATED_SECTION_RE = re.compile(r"(?m)^## \d{4}-\d{2}-\d{2} — ")


class MalformedLaneFileError(Exception):
    """A lane file under docs/decisions/ doesn't parse as dated entries."""


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def find_lane_files(decisions_dir: Path) -> list[Path]:
    if not decisions_dir.is_dir():
        return []
    return sorted(
        p for p in decisions_dir.glob("*.md")
        if p.name not in STUB_FILENAMES
    )


def parse_lane_file(path: Path) -> list[dict]:
    """Return every `## YYYY-MM-DD — Title` section in path, in file order.

    Raises MalformedLaneFileError naming `path` if the file is empty, has
    content before its first `## ` heading (this also catches "no heading at
    all" — a headingless non-blank file has nothing but preamble), or any
    heading doesn't match the dated-title pattern.
    """
    text = path.read_text(encoding="utf-8")
    if not text.strip():
        raise MalformedLaneFileError(f"{path}: file is empty")

    parts = SECTION_SPLIT_RE.split(text)
    preamble, sections = parts[0], parts[1:]
    if preamble.strip():
        raise MalformedLaneFileError(
            f"{path}: content before the first '## ' heading is not allowed "
            "(or no '## ' heading found at all)"
        )

    entries = []
    for section in sections:
        heading_line, _, body = section.partition("\n")
        heading_line = heading_line.rstrip()
        match = HEADING_RE.match(heading_line)
        if not match:
            raise MalformedLaneFileError(
                f"{path}: entry heading '{heading_line}' does not match "
                "'YYYY-MM-DD — Title'"
            )
        entry_text = "## " + heading_line + "\n\n" + body.strip("\n") + "\n\n"
        entries.append({"date": match.group(1), "text": entry_text, "source": path})
    return entries


def merge(decisions_path: Path, decisions_dir: Path) -> int:
    """Merge all lane files in decisions_dir into decisions_path.

    Returns the number of entries merged (0 means no-op — decisions_path is
    left untouched). Raises MalformedLaneFileError before writing anything
    if any lane file fails to parse.
    """
    lane_files = find_lane_files(decisions_dir)
    if not lane_files:
        return 0

    # Parse everything first — a malformed file must not cause a partial
    # merge (some lane files consumed, others left behind).
    entries: list[dict] = []
    for path in lane_files:
        entries.extend(parse_lane_file(path))

    # Newest date first, filename ascending as a tiebreak — matches the
    # ledger's existing newest-first convention. Stable sort: sort by
    # filename first (ascending), then by date (descending) so equal dates
    # keep filename order.
    entries.sort(key=lambda e: str(e["source"]))
    entries.sort(key=lambda e: e["date"], reverse=True)

    ledger_text = decisions_path.read_text(encoding="utf-8")
    match = DATED_SECTION_RE.search(ledger_text)
    header = ledger_text[: match.start()] if match else ledger_text
    rest = ledger_text[match.start():] if match else ""

    new_block = "".join(e["text"] for e in entries)
    decisions_path.write_text(header + new_block + rest, encoding="utf-8")

    for path in lane_files:
        path.unlink()

    return len(entries)


def main() -> int:
    try:
        count = merge(DECISIONS_PATH, DECISIONS_DIR)
    except MalformedLaneFileError as e:
        fail(str(e))

    if count == 0:
        print("OK merge-decisions: no pending lane files, nothing to merge.")
        return 0

    print(f"OK merge-decisions: merged {count} entr{'y' if count == 1 else 'ies'} "
          f"into {DECISIONS_PATH.relative_to(REPO_ROOT)}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
