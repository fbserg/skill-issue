#!/usr/bin/env python3
"""Verify the local skill-issue install is not split across checkouts."""
from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "codex": (
        "adversarial-review",
        "epic-plan",
        "issue",
        "refactor-dupes",
        "resolve-issue",
        "ww",
        "zero",
    ),
    "claude": (
        "authentic-writing",
        "authenticity-check",
        "epic-plan",
        "humanizer",
        "issue",
        "resolve-issue",
        "zero",
    ),
}
EXPECTED_LINKS = {
    Path(f"~/.{runtime}/skills/{name}").expanduser(): REPO_ROOT / f"skills/{runtime}/{name}"
    for runtime, names in EXPECTED_SKILLS.items()
    for name in names
}
EXPECTED_LINKS[
    Path("~/.local/bin/gmail-tools").expanduser()
] = REPO_ROOT / "tools/gmail-tools/bin/gmail-tools"


def fail(message: str) -> None:
    print(f"FAIL: {message}", file=sys.stderr)
    sys.exit(1)


def check_link(link: Path, expected: Path) -> None:
    if not link.is_symlink():
        fail(f"{link} is not a symlink")
    resolved = link.resolve()
    if resolved != expected.resolve():
        fail(f"{link} resolves to {resolved}, expected {expected}")
    if not resolved.exists():
        fail(f"{link} target does not exist: {resolved}")
    if resolved.name == "gmail-tools" and not os.access(resolved, os.X_OK):
        fail(f"{resolved} is not executable")


def main() -> int:
    for link, expected in EXPECTED_LINKS.items():
        check_link(link, expected)

    print(f"OK skill-issue install: {REPO_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
