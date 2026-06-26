#!/usr/bin/env python3
"""Daily Claude Code + Codex transcript archiver.

Copies JSONL transcripts from their source dirs into an archive directory,
stripping embedded base64 blobs (pasted images / screenshots) so the archive
stays lean. One-way: never deletes a destination file after the CLI prunes the
source, re-copies a transcript as it grows, and refuses to overwrite a larger
archived copy with a smaller one (logs a keep-larger warning instead).

Storage-agnostic by design: this script only writes to a local directory. Point
TRANSCRIPT_ARCHIVE_DIR at a folder inside any file-sync client (Dropbox, iCloud
Drive, Google Drive, OneDrive, Syncthing) and you get off-machine backup for
free -- the sync client does the uploading, this script never talks to a cloud
API. A plain external disk, an rsync target, or a git repo work equally well.
"""

import os
import re
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone

HOME = Path.home()

# --- Where to archive to -----------------------------------------------------
# Required. Any local directory. If it lives inside a synced folder
# (Dropbox/iCloud/Google Drive/OneDrive/Syncthing) you get off-machine backup
# automatically -- this script never speaks a cloud API.
_env = os.environ.get("TRANSCRIPT_ARCHIVE_DIR", "").strip()
if not _env:
    sys.stderr.write(
        "TRANSCRIPT_ARCHIVE_DIR is not set.\n"
        "Set it to the directory you want transcripts copied into, e.g.:\n"
        '  export TRANSCRIPT_ARCHIVE_DIR="$HOME/Dropbox/transcript-archive"\n'
    )
    sys.exit(2)
ARCHIVE_DIR = Path(_env).expanduser()

# --- What to archive: (src_root, dest_root, glob_pattern) --------------------
SOURCES = [
    (HOME / ".claude" / "projects", ARCHIVE_DIR / "claude", "**/*.jsonl"),
    (HOME / ".codex" / "sessions", ARCHIVE_DIR / "codex" / "sessions", "**/*.jsonl"),
]
# Single-file copies: (src, dest)
SINGLE_FILES = [
    (HOME / ".codex" / "history.jsonl", ARCHIVE_DIR / "codex" / "history.jsonl"),
]

LOG_FILE = Path(__file__).resolve().parent / "backup.log"
FREE_DISK_WARN_GB = 10

# Strip base64 runs of 200+ chars (embedded images/screenshots in transcripts).
B64_RE = re.compile(rb"[A-Za-z0-9+/]{200,}={0,2}")
STRIP_MARKER = b"__STRIPPED_BASE64__"


def strip_base64(data: bytes) -> bytes:
    return B64_RE.sub(STRIP_MARKER, data)


def free_gb(path: str = "/") -> float:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize / (1024 ** 3)


def archive_size_str(root: Path) -> str:
    try:
        result = subprocess.run(
            ["du", "-sh", str(root)], capture_output=True, text=True, timeout=120
        )
        return result.stdout.split("\t")[0].strip() if result.returncode == 0 else "unknown"
    except Exception:
        return "unknown"


def archive_file_count(root: Path) -> int:
    # os.walk with a swallowing onerror so one unreadable subdir (e.g. a
    # cloud-provider placeholder) does not zero out the whole count.
    total = 0
    for _dirpath, _dirnames, filenames in os.walk(root, onerror=lambda e: None):
        total += len(filenames)
    return total


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}  {msg}"
    print(line, flush=True)
    try:
        with LOG_FILE.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        print(f"[log write failed: {e}]", file=sys.stderr)


def process_file(src: Path, dest: Path) -> str:
    """Returns 'added', 'updated', 'skipped', 'kept-larger', or 'error:<msg>'."""
    try:
        src_mtime = os.path.getmtime(src)
    except OSError as e:
        return f"error:stat src: {e}"

    dest_exists = dest.exists()
    if dest_exists:
        try:
            dest_mtime = os.path.getmtime(dest)
        except OSError:
            dest_mtime = 0.0
        if dest_mtime >= src_mtime:
            return "skipped"
        action = "updated"
    else:
        action = "added"

    try:
        raw = src.read_bytes()
    except OSError as e:
        return f"error:read: {e}"

    stripped = strip_base64(raw)

    # Never let a newer-but-smaller source clobber a larger archived copy.
    # Transcript JSONL only grows within a session, so a shrink means the
    # source was truncated, rewritten, or restored from an older state --
    # keep the bigger archive and surface it loudly rather than losing history.
    if dest_exists:
        try:
            dest_size = dest.stat().st_size
        except OSError:
            dest_size = -1
        if dest_size >= 0 and len(stripped) < dest_size:
            return "kept-larger"

    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(stripped)
        os.utime(dest, (src_mtime, src_mtime))
    except OSError as e:
        return f"error:write: {e}"

    return action


def _apply(result: str, src: Path, counts: dict, errors: list) -> None:
    if result.startswith("error:"):
        counts["error"] += 1
        msg = f"ERROR {src}: {result[6:]}"
        errors.append(msg)
        log(msg)
    elif result == "kept-larger":
        counts["kept"] += 1
        log(f"WARN keep-larger (source smaller than archived copy, NOT overwritten): {src}")
    else:
        counts[result] += 1


def main() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    counts = {"added": 0, "updated": 0, "skipped": 0, "kept": 0, "error": 0}
    errors: list[str] = []
    sources_seen = 0

    for src_root, dest_root, pattern in SOURCES:
        if not src_root.exists():
            log(f"WARN: source not found, skipping: {src_root}")
            continue
        sources_seen += 1
        for src in src_root.glob(pattern):
            if not src.is_file():
                continue
            dest = dest_root / src.relative_to(src_root)
            _apply(process_file(src, dest), src, counts, errors)

    for src, dest in SINGLE_FILES:
        if not src.exists():
            log(f"WARN: single-file source not found, skipping: {src}")
            continue
        sources_seen += 1
        _apply(process_file(src, dest), src, counts, errors)

    total = archive_file_count(ARCHIVE_DIR)
    size_str = archive_size_str(ARCHIVE_DIR)
    free = free_gb("/")
    free_warn = " *** WARNING: LOW DISK SPACE ***" if free < FREE_DISK_WARN_GB else ""

    # Errors first, then the no-source fatal, so the SUMMARY line is always last
    # (monitors tail the final line).
    if errors:
        log(f"ERRORS ({len(errors)}):")
        for e in errors:
            log(f"  {e}")

    no_sources = sources_seen == 0
    if no_sources:
        log("ERROR: no transcript sources found (no ~/.claude/projects, "
            "~/.codex/sessions, or ~/.codex/history.jsonl) -- archived nothing. "
            "Check HOME and the launchd environment.")

    log(
        f"SUMMARY | added={counts['added']} updated={counts['updated']} "
        f"skipped={counts['skipped']} kept_larger={counts['kept']} "
        f"errors={counts['error']} | archive_total={total} files | "
        f"archive_size={size_str} | free_disk={free:.1f}GB{free_warn}"
    )

    sys.exit(1 if (counts["error"] or no_sources) else 0)


if __name__ == "__main__":
    main()
