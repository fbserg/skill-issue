#!/usr/bin/env python3
"""Verify the local skill-issue install is not split across checkouts."""
from __future__ import annotations

import os
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

# Codex-only skills — unchanged, canonical home is skills/codex/.
CODEX_SKILLS = (
    "adversarial-review",
    "epic-plan",
    "issue",
    "issue-wave",
    "refactor-dupes",
    "resolve-issue",
    "ww",
    "zero",
)

# Claude-only skills remaining under skills/claude/ (the five shared skills
# that used to be duplicated here — authentic-writing, authenticity-check,
# humanizer, ww, zero — now live solely under skills/shared/, see
# SHARED_SKILLS below).
CLAUDE_SKILLS = (
    "adversary",
    "blitz",
    "deep-research",
    "epic-plan",
    "issue",
    "resolve-issue",
    "simplify-sweep",
)

# Skills shared between Claude and Codex prose, installed for Claude only.
# Canonical home is skills/shared/ — no longer duplicated under skills/claude/.
SHARED_SKILLS = (
    "authentic-writing",
    "authenticity-check",
    "humanizer",
    "ww",
    "zero",
)

# Delegate agent definitions symlinked into ~/.claude/agents/.
AGENTS = (
    "bulk.md",
    "explore-mid.md",
    "opus-worker.md",
    "worker.md",
)

EXPECTED_LINKS = {
    Path(f"~/.codex/skills/{name}").expanduser(): REPO_ROOT / f"skills/codex/{name}"
    for name in CODEX_SKILLS
}
EXPECTED_LINKS.update({
    Path(f"~/.claude/skills/{name}").expanduser(): REPO_ROOT / f"skills/claude/{name}"
    for name in CLAUDE_SKILLS
})
EXPECTED_LINKS.update({
    Path(f"~/.claude/skills/{name}").expanduser(): REPO_ROOT / f"skills/shared/{name}"
    for name in SHARED_SKILLS
})
EXPECTED_LINKS.update({
    Path(f"~/.claude/agents/{name}").expanduser(): REPO_ROOT / f"agents/{name}"
    for name in AGENTS
})
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
        if link.parent.is_symlink():
            print(f"SKIP: {link.parent} is externally managed")
            continue
        check_link(link, expected)

    print(f"OK skill-issue install: {REPO_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
