#!/usr/bin/env python3
"""Doc-link drift guard: verify every relative markdown link in tracked .md files exists on disk."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# Which .md files to scan (explicit set + any tracked root-level .md)
SCAN_EXPLICIT = [
    REPO_ROOT / "README.md",
    REPO_ROOT / "INDEX.md",
    REPO_ROOT / "hooks/claude/README.md",
]

# Pattern: [text](target) — captures the link target
LINK_RE = re.compile(r'\[(?:[^\]]*)\]\(([^)]+)\)')


def tracked_root_mds() -> list[Path]:
    """Return tracked .md files at the repo root."""
    result = subprocess.run(
        ["git", "ls-files", "*.md"],
        capture_output=True, text=True, cwd=REPO_ROOT, check=False,
    )
    paths = []
    for line in result.stdout.splitlines():
        p = REPO_ROOT / line
        # root-level only (no directory separator in the ls-files output path)
        if "/" not in line and p.exists():
            paths.append(p)
    return paths


def collect_md_files() -> list[Path]:
    seen: set[Path] = set()
    files: list[Path] = []
    for p in SCAN_EXPLICIT + tracked_root_mds():
        if p not in seen and p.exists():
            seen.add(p)
            files.append(p)
    return files


def extract_link_targets(md_file: Path) -> list[str]:
    text = md_file.read_text(encoding="utf-8")
    return LINK_RE.findall(text)


def is_checkable(target: str) -> bool:
    """Return True if this target is a local filesystem path we should verify."""
    if target.startswith(("http://", "https://", "mailto:")):
        return False
    if target.startswith("#"):
        return False
    return True


def strip_fragment(target: str) -> str:
    return target.split("#")[0]


def resolve_target(md_file: Path, raw: str) -> Path | None:
    """Resolve a relative link target to an absolute path.

    Strategy:
      1. Relative to the file's directory (standard markdown convention).
      2. Fall back to repo root (common in root-level doc files).
    """
    cleaned = strip_fragment(raw)
    if not cleaned:
        return None  # pure anchor after stripping — skip

    file_dir = md_file.parent
    candidate = (file_dir / cleaned).resolve()
    if candidate.exists():
        return candidate

    # Fall back to repo root
    root_candidate = (REPO_ROOT / cleaned).resolve()
    if root_candidate.exists():
        return root_candidate

    # Return the first candidate (relative-to-file) as the failing path to report
    return candidate


def main() -> int:
    files = collect_md_files()
    missing: list[tuple[Path, str, Path]] = []  # (md_file, raw_target, resolved)
    checked = 0

    for md_file in files:
        for raw_target in extract_link_targets(md_file):
            if not is_checkable(raw_target):
                continue
            resolved = resolve_target(md_file, raw_target)
            if resolved is None:
                continue  # pure anchor stripped to empty
            checked += 1
            if not resolved.exists():
                missing.append((md_file, raw_target, resolved))

    if missing:
        for md_file, raw_target, resolved in missing:
            rel_md = md_file.relative_to(REPO_ROOT)
            print(f"MISSING  {rel_md}: [{raw_target}] -> {resolved}", file=sys.stderr)
        print(
            f"\n{len(missing)} broken link(s) found in {len(files)} file(s) "
            f"({checked} links checked).",
            file=sys.stderr,
        )
        return 1

    print(f"OK  {checked} link(s) checked across {len(files)} file(s) — all targets exist.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
