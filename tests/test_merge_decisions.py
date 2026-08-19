"""scripts/merge-decisions.py: per-lane decision file merger.

Three parallel lanes each appending to the one append-only DECISIONS.md
produced three identical merge conflicts (2026-08 epic40 postmortem). Lanes
now write docs/decisions/<slug>.md instead; this script folds them into the
ledger at close-out. Covers merge order, idempotency, and the malformed-file
hard-fail (see scripts/merge-decisions.py's module docstring).

Run with: python3 -m pytest tests/test_merge_decisions.py -v
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "merge-decisions.py"
SPEC = importlib.util.spec_from_file_location("merge_decisions", MODULE_PATH)
assert SPEC and SPEC.loader
MERGE_DECISIONS = importlib.util.module_from_spec(SPEC)
sys.argv = ["merge-decisions.py"]
SPEC.loader.exec_module(MERGE_DECISIONS)

HEADER = (
    "# Decisions\n\n"
    "Durable rulings on contested choices. Check here before re-litigating.\n\n"
)


def _write_ledger(tmp_path: Path, header: str = HEADER, entries: str = "") -> Path:
    path = tmp_path / "DECISIONS.md"
    path.write_text(header + entries, encoding="utf-8")
    return path


def _decisions_dir(tmp_path: Path) -> Path:
    d = tmp_path / "decisions"
    d.mkdir()
    return d


def test_merge_inserts_new_entry_after_header_before_existing_entries(tmp_path: Path) -> None:
    existing = "## 2026-08-07 — Old ruling\n\n**Decision:** kept things as-is.\n\n"
    ledger = _write_ledger(tmp_path, entries=existing)
    lane_dir = _decisions_dir(tmp_path)
    (lane_dir / "lane-a.md").write_text(
        "## 2026-08-18 — New ruling\n\n**Decision:** did the new thing.\n",
        encoding="utf-8",
    )

    count = MERGE_DECISIONS.merge(ledger, lane_dir)

    assert count == 1
    text = ledger.read_text(encoding="utf-8")
    assert text.startswith(HEADER)
    new_pos = text.index("## 2026-08-18 — New ruling")
    old_pos = text.index("## 2026-08-07 — Old ruling")
    assert new_pos < old_pos
    assert "**Decision:** did the new thing." in text
    assert not (lane_dir / "lane-a.md").exists()


def test_merge_inserts_after_non_dated_header_sections(tmp_path: Path) -> None:
    """The ledger's own protocol note (a non-dated '## ' section) must stay
    part of the header — new entries insert after it, not before it."""
    header_with_protocol = (
        HEADER
        + "## Recording a new ruling\n\n"
        + "Write docs/decisions/<slug>.md instead of editing this file.\n\n"
    )
    existing = "## 2026-08-07 — Old ruling\n\n**Decision:** kept things as-is.\n\n"
    ledger = _write_ledger(tmp_path, header=header_with_protocol, entries=existing)
    lane_dir = _decisions_dir(tmp_path)
    (lane_dir / "lane-a.md").write_text(
        "## 2026-08-18 — New ruling\n\n**Decision:** did the new thing.\n",
        encoding="utf-8",
    )

    count = MERGE_DECISIONS.merge(ledger, lane_dir)

    assert count == 1
    text = ledger.read_text(encoding="utf-8")
    protocol_pos = text.index("## Recording a new ruling")
    new_pos = text.index("## 2026-08-18 — New ruling")
    old_pos = text.index("## 2026-08-07 — Old ruling")
    assert protocol_pos < new_pos < old_pos
    # Heading and body stay separated by a blank line, not glued together.
    assert "## 2026-08-18 — New ruling\n\n**Decision:**" in text


def test_merge_order_is_date_descending_then_filename_ascending(tmp_path: Path) -> None:
    ledger = _write_ledger(tmp_path)
    lane_dir = _decisions_dir(tmp_path)
    (lane_dir / "z-lane.md").write_text(
        "## 2026-08-18 — Z same-day entry\n\n**Decision:** z.\n", encoding="utf-8"
    )
    (lane_dir / "a-lane.md").write_text(
        "## 2026-08-18 — A same-day entry\n\n**Decision:** a.\n", encoding="utf-8"
    )
    (lane_dir / "older-lane.md").write_text(
        "## 2026-08-10 — Older entry\n\n**Decision:** older.\n", encoding="utf-8"
    )

    count = MERGE_DECISIONS.merge(ledger, lane_dir)

    assert count == 3
    text = ledger.read_text(encoding="utf-8")
    # Same-day entries: a-lane (filename-ascending) before z-lane.
    pos_a = text.index("A same-day entry")
    pos_z = text.index("Z same-day entry")
    pos_older = text.index("Older entry")
    assert pos_a < pos_z < pos_older


def test_lane_file_with_multiple_entries_splits_correctly(tmp_path: Path) -> None:
    ledger = _write_ledger(tmp_path)
    lane_dir = _decisions_dir(tmp_path)
    (lane_dir / "lane-a.md").write_text(
        "## 2026-08-18 — First entry\n\n**Decision:** first.\n\n"
        "## 2026-08-17 — Second entry\n\n**Decision:** second.\n",
        encoding="utf-8",
    )

    count = MERGE_DECISIONS.merge(ledger, lane_dir)

    assert count == 2
    text = ledger.read_text(encoding="utf-8")
    pos_first = text.index("First entry")
    pos_second = text.index("Second entry")
    assert pos_first < pos_second  # 08-18 sorts before 08-17 (descending)


def test_merge_is_idempotent_with_nothing_pending(tmp_path: Path) -> None:
    existing = "## 2026-08-07 — Old ruling\n\n**Decision:** kept things as-is.\n\n"
    ledger = _write_ledger(tmp_path, entries=existing)
    lane_dir = _decisions_dir(tmp_path)
    before = ledger.read_text(encoding="utf-8")

    count = MERGE_DECISIONS.merge(ledger, lane_dir)

    assert count == 0
    assert ledger.read_text(encoding="utf-8") == before


def test_merge_no_op_when_decisions_dir_does_not_exist(tmp_path: Path) -> None:
    ledger = _write_ledger(tmp_path)
    missing_dir = tmp_path / "does-not-exist"

    count = MERGE_DECISIONS.merge(ledger, missing_dir)

    assert count == 0


def test_rerun_after_merge_is_a_no_op(tmp_path: Path) -> None:
    ledger = _write_ledger(tmp_path)
    lane_dir = _decisions_dir(tmp_path)
    (lane_dir / "lane-a.md").write_text(
        "## 2026-08-18 — New ruling\n\n**Decision:** did the new thing.\n",
        encoding="utf-8",
    )

    first_count = MERGE_DECISIONS.merge(ledger, lane_dir)
    after_first = ledger.read_text(encoding="utf-8")
    second_count = MERGE_DECISIONS.merge(ledger, lane_dir)
    after_second = ledger.read_text(encoding="utf-8")

    assert first_count == 1
    assert second_count == 0
    assert after_first == after_second


def test_readme_stub_is_never_treated_as_a_lane_file(tmp_path: Path) -> None:
    ledger = _write_ledger(tmp_path)
    lane_dir = _decisions_dir(tmp_path)
    (lane_dir / "README.md").write_text("# lane decisions\n\nnot a lane file\n", encoding="utf-8")

    count = MERGE_DECISIONS.merge(ledger, lane_dir)

    assert count == 0
    assert (lane_dir / "README.md").exists()  # stub survives


@pytest.mark.parametrize(
    "content,expected_fragment",
    [
        ("", "file is empty"),
        ("   \n\n  ", "file is empty"),
        ("Some prose before any heading.\n\n## 2026-08-18 — Title\n\nbody\n", "content before the first"),
        ("Not a heading at all, no ## anywhere.\n", "content before the first"),
        ("## Not a dated heading\n\n**Decision:** x.\n", "does not match"),
        ("## 2026-13-40 — Bad date shape but right length\n\nbody\n", None),  # regex only checks shape, not validity
    ],
)
def test_malformed_lane_file_fails_hard_naming_the_file(
    tmp_path: Path, content: str, expected_fragment: str | None
) -> None:
    ledger = _write_ledger(tmp_path)
    lane_dir = _decisions_dir(tmp_path)
    bad_file = lane_dir / "bad-lane.md"
    bad_file.write_text(content, encoding="utf-8")

    if expected_fragment is None:
        # Shape-valid (regex doesn't validate calendar correctness) — merges fine.
        count = MERGE_DECISIONS.merge(ledger, lane_dir)
        assert count == 1
        return

    with pytest.raises(MERGE_DECISIONS.MalformedLaneFileError) as exc_info:
        MERGE_DECISIONS.merge(ledger, lane_dir)
    message = str(exc_info.value)
    assert str(bad_file) in message
    assert expected_fragment in message


def test_malformed_file_blocks_the_whole_merge_no_partial_write(tmp_path: Path) -> None:
    """One malformed lane file must not let good lane files merge partially —
    fail before writing anything."""
    ledger = _write_ledger(tmp_path)
    lane_dir = _decisions_dir(tmp_path)
    (lane_dir / "good-lane.md").write_text(
        "## 2026-08-18 — Good entry\n\n**Decision:** fine.\n", encoding="utf-8"
    )
    (lane_dir / "bad-lane.md").write_text("no heading here\n", encoding="utf-8")
    before = ledger.read_text(encoding="utf-8")

    with pytest.raises(MERGE_DECISIONS.MalformedLaneFileError):
        MERGE_DECISIONS.merge(ledger, lane_dir)

    assert ledger.read_text(encoding="utf-8") == before
    assert (lane_dir / "good-lane.md").exists()  # not deleted
    assert (lane_dir / "bad-lane.md").exists()


def test_main_exits_1_and_names_file_on_malformed_lane(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    ledger = _write_ledger(tmp_path)
    lane_dir = _decisions_dir(tmp_path)
    (lane_dir / "bad-lane.md").write_text("no heading here\n", encoding="utf-8")
    monkeypatch.setattr(MERGE_DECISIONS, "DECISIONS_PATH", ledger)
    monkeypatch.setattr(MERGE_DECISIONS, "DECISIONS_DIR", lane_dir)

    with pytest.raises(SystemExit) as exc_info:
        MERGE_DECISIONS.main()

    assert exc_info.value.code == 1
    err = capsys.readouterr().err
    assert "bad-lane.md" in err


def test_main_exits_0_when_nothing_pending(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    ledger = _write_ledger(tmp_path)
    lane_dir = _decisions_dir(tmp_path)
    monkeypatch.setattr(MERGE_DECISIONS, "DECISIONS_PATH", ledger)
    monkeypatch.setattr(MERGE_DECISIONS, "DECISIONS_DIR", lane_dir)

    assert MERGE_DECISIONS.main() == 0
