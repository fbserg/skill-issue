#!/usr/bin/env python3
"""Verify the local skill-issue install is not split across checkouts."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_SKILLS = {
    "claude": (
        "epic-plan",
        "epic-run",
        "epic-research",
        "epic-retro",
        "issue-sweep",
        "tidy",
        "zero",
    ),
    "codex": (
        "epic-plan",
        "epic-run",
        "epic-research",
        "issue-sweep",
        "quick-research",
        "tidy",
        "zero",
    ),
}
EXPECTED_LINKS = {
    Path(f"~/.{runtime}/skills/{name}").expanduser(): REPO_ROOT / f"skills/{runtime}/{name}"
    for runtime, names in EXPECTED_SKILLS.items()
    for name in names
}
EXPECTED_LINKS[
    Path("~/.local/bin/epic-tools").expanduser()
] = REPO_ROOT / "tools/epic-tools/bin/epic-tools"
EXPECTED_SUBCOMMANDS = {
    "parse-epic",
    "epic-status",
    "verify-pr",
    "revert",
    "pr-create",
    "lock-status",
    "cleanup",
    "plan-to-epic",
}


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
    if resolved.name == "epic-tools" and not os.access(resolved, os.X_OK):
        fail(f"{resolved} is not executable")


def installed_epic_tools_help() -> str:
    result = subprocess.run(
        ["epic-tools", "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        fail(f"epic-tools --help failed:\n{output.strip()}")
    return output


def parse_subcommands(help_text: str) -> set[str]:
    match = re.search(r"\{([\w,\-]+)\}", help_text)
    if not match:
        fail("could not parse epic-tools subcommands from --help")
    return set(match.group(1).split(","))


def check_help_flag(subcommand: str, needle: str) -> None:
    result = subprocess.run(
        ["epic-tools", subcommand, "--help"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = result.stdout + result.stderr
    if result.returncode != 0:
        fail(f"epic-tools {subcommand} --help failed:\n{output.strip()}")
    if needle not in output:
        fail(f"epic-tools {subcommand} --help does not mention {needle}")


def main() -> int:
    for link, expected in EXPECTED_LINKS.items():
        check_link(link, expected)

    subcommands = parse_subcommands(installed_epic_tools_help())
    if subcommands != EXPECTED_SUBCOMMANDS:
        fail(
            "epic-tools subcommand mismatch: "
            f"extra={sorted(subcommands - EXPECTED_SUBCOMMANDS)} "
            f"missing={sorted(EXPECTED_SUBCOMMANDS - subcommands)}"
        )

    check_help_flag("revert", "--yes")
    check_help_flag("cleanup", "--yes")
    print(f"OK skill-issue install: {REPO_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
