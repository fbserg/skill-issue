#!/usr/bin/env python3
"""Verify the local skill-issue install is not split across checkouts."""
from __future__ import annotations

import os
import re
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

# Claude-only skills remaining under skills/claude/ (the shared skills that
# used to be duplicated here — authenticity-check, humanizer, zero — now live
# solely under skills/shared/, see SHARED_SKILLS below. authentic-writing and
# transcript-backup were deleted: zero invocations across 14,509 transcripts;
# skills/shared/ww was deleted: its only unique content was a boundary
# sentence blitz already states from the other side).
CLAUDE_SKILLS = (
    "adversary",
    "blitz",
    "deep-research",
    "epic-plan",
    "issue",
    "resolve-issue",
    "simplify-sweep",
)

# Shared skill sources. All install into Claude; zero also installs into Codex.
SHARED_SKILLS = (
    "authenticity-check",
    "humanizer",
    "zero",
)

# Delegate agent definitions symlinked into ~/.claude/agents/.
AGENTS = (
    "bulk.md",
    "explore-mid.md",
    "lane.md",
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


def check_hook_guard_marker_parity() -> None:
    """hooks/claude/*.sh in this repo is a mirror only — scripts/install.sh
    does not install it. The harness executes whatever ~/.claude/hooks (a
    symlink) points at instead. A guard added to the mirror but never ported
    to the live file silently does nothing (this happened in PR #23: a
    worktree-escape guard landed in the mirror, not the live hook).

    Byte-parity is too strict — the two files have legitimately diverged
    (e.g. the live file's Heartwood-VM PHASE 1.5 block has no mirror
    counterpart). Instead this checks that every ALL-CAPS `..._RE=` guard
    regex variable defined in a mirror hook is also defined, by name, in the
    corresponding live hook file.
    """
    live_hooks_dir = Path("~/.claude/hooks").expanduser()
    if not live_hooks_dir.is_symlink():
        print(f"SKIP: {live_hooks_dir} is not installed (hooks are opt-in, "
              "see hooks/claude/README.md) — cannot check guard-marker parity")
        return
    live_hooks_dir = live_hooks_dir.resolve()

    mirror_dir = REPO_ROOT / "hooks" / "claude"
    for mirror_file in sorted(mirror_dir.glob("*.sh")):
        mirror_markers = set(GUARD_MARKER_RE.findall(mirror_file.read_text()))
        if not mirror_markers:
            continue
        live_file = live_hooks_dir / mirror_file.name
        if not live_file.exists():
            fail(
                f"{mirror_file.relative_to(REPO_ROOT)} defines guard marker(s) "
                f"{sorted(mirror_markers)} but the live hook {live_file} does not exist"
            )
        live_markers = set(GUARD_MARKER_RE.findall(live_file.read_text()))
        missing = mirror_markers - live_markers
        if missing:
            fail(
                f"{mirror_file.relative_to(REPO_ROOT)} has guard marker(s) {sorted(missing)} "
                f"not present in the live hook {live_file} — a mirror-only fix the harness "
                "never executes (see PR #23)"
            )
def main() -> int:
    for link, expected in EXPECTED_LINKS.items():
        if link.parent.is_symlink():
            print(f"SKIP: {link.parent} is externally managed")
            continue
        check_link(link, expected)

    check_codex_skill_parity()
    check_refs()
    check_hook_guard_marker_parity()

    print(f"OK skill-issue install: {REPO_ROOT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
