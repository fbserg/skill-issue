#!/usr/bin/env python3
"""Verify the local skill-issue install is not split across checkouts."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

# Codex-native skills; shared zero is registered separately below.
CODEX_SKILLS = (
    "adversarial-review",
    "blitz",
    "epic-plan",
    "issue",
    "refactor-dupes",
    "resolve-issue",
    "ww",
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
    "transcript-backup",
)

# Shared skill sources. All install into Claude; zero also installs into Codex.
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

# Runtime-native counterparts are allowed to differ in prose and tools, but a
# newer source-side edit must be explicitly reviewed on the Codex side.
CODEX_PARITY_PAIRS = (
    ("skills/claude/blitz", "skills/codex/blitz"),
    ("skills/claude/epic-plan", "skills/codex/epic-plan"),
    ("skills/claude/issue", "skills/codex/issue"),
    ("skills/claude/resolve-issue", "skills/codex/resolve-issue"),
    ("skills/shared/ww", "skills/codex/ww"),
)

EXPECTED_LINKS = {
    Path(f"~/.codex/skills/{name}").expanduser(): REPO_ROOT / f"skills/codex/{name}"
    for name in CODEX_SKILLS
}
EXPECTED_LINKS[Path("~/.codex/skills/zero").expanduser()] = REPO_ROOT / "skills/shared/zero"
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


def last_change_timestamp(relative_path: str) -> int:
    result = subprocess.run(
        ["git", "log", "-1", "--format=%ct", "--", relative_path],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip())


def check_codex_skill_parity() -> None:
    stale = [
        (source, codex)
        for source, codex in CODEX_PARITY_PAIRS
        if last_change_timestamp(source) > last_change_timestamp(codex)
    ]
    if stale:
        pairs = ", ".join(f"{source} -> {codex}" for source, codex in stale)
        fail(f"Codex skill review is stale: {pairs}")


def main() -> int:
    for link, expected in EXPECTED_LINKS.items():
        if link.parent.is_symlink():
            print(f"SKIP: {link.parent} is externally managed")
            continue
        check_link(link, expected)

    check_codex_skill_parity()

    print(f"OK skill-issue install: {REPO_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
