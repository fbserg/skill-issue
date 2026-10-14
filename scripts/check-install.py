#!/usr/bin/env python3
"""Verify the local skill-issue install is not split across checkouts."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]

def skill_names(subdir: str) -> tuple[str, ...]:
    """Skill dirs install.sh links: every skills/<subdir>/*/ holding a SKILL.md."""
    return tuple(sorted(path.parent.name for path in (REPO_ROOT / "skills" / subdir).glob("*/SKILL.md")))


CODEX_SKILLS = skill_names("codex")
CLAUDE_SKILLS = skill_names("claude")
SHARED_SKILLS = skill_names("shared")
# install.sh links only these shared skills into Codex.
CODEX_SHARED_SKILLS = ("zero", "herdr-share")

# Delegate agent definitions symlinked into ~/.claude/agents/.
AGENTS = tuple(sorted(path.name for path in (REPO_ROOT / "agents").glob("*.md")))

EXPECTED_LINKS = {
    Path(f"~/.codex/skills/{name}").expanduser(): REPO_ROOT / f"skills/codex/{name}"
    for name in CODEX_SKILLS
}
EXPECTED_LINKS.update({
    Path(f"~/.codex/skills/{name}").expanduser(): REPO_ROOT / f"skills/shared/{name}"
    for name in CODEX_SHARED_SKILLS
})
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


def check_codex_skill_parity() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "generate-codex-skills.py"), "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout, end="")
        fail(f"Codex skill gate content is stale:\n{result.stderr}")
    print(result.stdout, end="")


def check_refs() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check-refs.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout, end="")
        fail(f"reference-drift check failed:\n{result.stderr}")
    print(result.stdout, end="")


GUARD_MARKER_RE = re.compile(r"^[ \t]*([A-Za-z_][A-Za-z0-9_]*_RE)=", re.MULTILINE)


def main() -> int:
    for link, expected in EXPECTED_LINKS.items():
        if link.parent.is_symlink():
            print(f"SKIP: {link.parent} is externally managed")
            continue
        check_link(link, expected)

    check_codex_skill_parity()
    check_refs()

    print(f"OK skill-issue install: {REPO_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
