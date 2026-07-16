#!/usr/bin/env python3
"""Team-grade Claude Code + Codex transcript archiver.

Mirrors JSONL transcripts from their source directories into a shared,
machine-namespaced archive directory. One-way: never deletes a destination
file after the CLI prunes the source, re-copies a transcript as it grows, and
refuses to overwrite a larger archived copy with a smaller one unless --force
is given.

Image policy: transcripts embed base64-encoded images twice per screenshot
(once in the tool_result block, once in the duplicate toolUseResult field).
Rather than a blind base64 regex (which used to mangle thinking signatures,
JWTs, and PDF/SVG bytes that merely *look* like base64), this version parses
each JSONL line as JSON and replaces only base64 image payloads it can
positively classify as agent-generated (screenshots, forwarded images) with a
small tombstone string, leaving the JSON structure valid. Human-pasted images
and document attachments are always kept. See README.md for the full policy
table and the reasoning behind it.

Storage-agnostic by design: this script only writes to a local directory.
Point TRANSCRIPT_ARCHIVE_DIR at a folder inside any file-sync client
(Dropbox, iCloud Drive, Google Drive, OneDrive, Syncthing) and you get
off-machine, multi-machine-safe backup for free -- the sync client does the
uploading, this script never talks to a cloud API. Machine-id namespacing
(see below) means two machines writing into the same synced folder never
collide.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

FREE_DISK_WARN_GB = 10
LOG_ROTATE_MAX_BYTES = 5 * 1024 * 1024  # 5MB, single generation (.1)

# ---------------------------------------------------------------------------
# Home directory (a function, not a module constant, so tests can point it at
# a fake HOME by setting the HOME env var before calling).
# ---------------------------------------------------------------------------


def home_dir() -> Path:
    return Path.home()


# ---------------------------------------------------------------------------
# Env / config resolution
# ---------------------------------------------------------------------------


def resolve_archive_dir() -> Path:
    raw = os.environ.get("TRANSCRIPT_ARCHIVE_DIR", "").strip()
    if not raw:
        sys.stderr.write(
            "TRANSCRIPT_ARCHIVE_DIR is not set.\n"
            "Set it to the directory you want transcripts mirrored into, e.g.:\n"
            '  export TRANSCRIPT_ARCHIVE_DIR="$HOME/Dropbox/transcript-archive"\n'
        )
        sys.exit(2)
    return Path(raw).expanduser()


def sanitize_machine_id(raw: str) -> str:
    return re.sub(r"[^a-z0-9-]", "-", raw.lower())


def resolve_machine_id() -> str:
    raw = os.environ.get("TRANSCRIPT_ARCHIVE_MACHINE_ID", "").strip()
    if not raw:
        raw = platform.node().split(".")[0]
    machine_id = sanitize_machine_id(raw)
    if not machine_id:
        sys.stderr.write(
            "Could not determine a usable machine id (hostname empty or unusable "
            "after sanitizing).\n"
            "Set TRANSCRIPT_ARCHIVE_MACHINE_ID explicitly, e.g.:\n"
            '  export TRANSCRIPT_ARCHIVE_MACHINE_ID="laptop"\n'
        )
        sys.exit(2)
    return machine_id


# ---------------------------------------------------------------------------
# Logging (lives at $ARCHIVE/<machine-id>/backup.log; rotates at 5MB)
# ---------------------------------------------------------------------------

_LOG_PATH: Optional[Path] = None


def rotate_log_if_large(path: Path, max_bytes: int = LOG_ROTATE_MAX_BYTES) -> None:
    try:
        if path.exists() and path.stat().st_size > max_bytes:
            rotated = path.with_name(path.name + ".1")
            os.replace(path, rotated)
    except OSError as e:
        sys.stderr.write(f"[log rotation failed: {e}]\n")


def configure_logging(path: Path, dry_run: bool = False) -> None:
    # --dry-run means "write nothing": no machine-namespaced directory, no
    # backup.log, so a dry run leaves zero trace on TRANSCRIPT_ARCHIVE_DIR
    # and doesn't inflate the SUMMARY's archive_total/archive_size with a
    # log file the run itself just created. Console logging still happens
    # via log()'s unconditional print().
    global _LOG_PATH
    if dry_run:
        _LOG_PATH = None
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        rotate_log_if_large(path)
        _LOG_PATH = path
    except OSError as e:
        sys.stderr.write(f"[log setup failed: {e}] -- continuing without file logging\n")
        _LOG_PATH = None


def log(msg: str) -> None:
    line = f"{datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')}  {msg}"
    print(line, flush=True)
    if _LOG_PATH is None:
        return
    try:
        with _LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as e:
        sys.stderr.write(f"[log write failed: {e}]\n")


# ---------------------------------------------------------------------------
# Tombstone
# ---------------------------------------------------------------------------


def make_tombstone(b64_string: str, media_type: str) -> str:
    approx_decoded_len = len(b64_string) * 3 // 4
    sha_hex12 = hashlib.sha256(b64_string.encode("utf-8")).hexdigest()[:12]
    return f"__IMAGE_TOMBSTONE(media_type={media_type},bytes={approx_decoded_len},sha256={sha_hex12})__"


def _looks_like_image_media_type(s: str) -> bool:
    return s.lower().startswith("image/")


# ---------------------------------------------------------------------------
# Claude policy
# ---------------------------------------------------------------------------


def walk_tool_use_result(node: object) -> bool:
    """Recursively tombstone base64 image bytes inside a toolUseResult value.

    toolUseResult duplicates the bytes already present in message.content's
    tool_result block (verified byte-identical), in one of two shapes:
      {type:'image', source:{type:'base64', data:...}}
      {..., file:{base64:...}}  where file.type/sibling type says 'image'
    """
    modified = False
    if isinstance(node, dict):
        ntype = node.get("type")
        source = node.get("source")
        if (
            ntype == "image"
            and isinstance(source, dict)
            and source.get("type") == "base64"
            and isinstance(source.get("data"), str)
        ):
            media_type = source.get("media_type", "unknown")
            source["data"] = make_tombstone(source["data"], media_type)
            modified = True

        file_field = node.get("file")
        if isinstance(file_field, dict) and isinstance(file_field.get("base64"), str):
            file_type = str(file_field.get("type", ""))
            if _looks_like_image_media_type(file_type) or ntype == "image":
                file_field["base64"] = make_tombstone(file_field["base64"], file_type or "unknown")
                modified = True

        for value in node.values():
            if isinstance(value, (dict, list)):
                if walk_tool_use_result(value):
                    modified = True
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                if walk_tool_use_result(item):
                    modified = True
    return modified


def claude_strip_line(obj: object) -> bool:
    """Mutates obj in place per the Claude image policy. Returns True if modified."""
    if not isinstance(obj, dict):
        return False
    modified = False

    message = obj.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if isinstance(content, list):
        for block in content:
            if not isinstance(block, dict):
                continue
            btype = block.get("type")

            if btype == "tool_result" and isinstance(block.get("content"), list):
                for inner in block["content"]:
                    if not isinstance(inner, dict) or inner.get("type") != "image":
                        continue
                    source = inner.get("source")
                    if (
                        isinstance(source, dict)
                        and source.get("type") == "base64"
                        and isinstance(source.get("data"), str)
                    ):
                        media_type = source.get("media_type", "unknown")
                        source["data"] = make_tombstone(source["data"], media_type)
                        modified = True

            elif btype == "image":
                source = block.get("source")
                if not (
                    isinstance(source, dict)
                    and source.get("type") == "base64"
                    and isinstance(source.get("data"), str)
                ):
                    continue
                is_human_paste = bool(obj.get("imagePasteIds")) or (
                    isinstance(obj.get("origin"), dict) and obj["origin"].get("kind") == "human"
                )
                is_agent_forwarded = obj.get("isMeta") is True and bool(obj.get("agentId"))
                if is_human_paste:
                    pass  # human paste is sacred, always kept
                elif is_agent_forwarded:
                    media_type = source.get("media_type", "unknown")
                    source["data"] = make_tombstone(source["data"], media_type)
                    modified = True
                else:
                    pass  # uncertain -- bias to preservation

            # btype == 'document' (or anything else): always kept, no-op.

    tool_use_result = obj.get("toolUseResult")
    if tool_use_result is not None and walk_tool_use_result(tool_use_result):
        modified = True

    return modified


# ---------------------------------------------------------------------------
# Codex policy
# ---------------------------------------------------------------------------


def tombstone_data_uri(data_uri: str) -> str:
    header, _, b64data = data_uri.partition(",")
    media_type = "unknown"
    if header.startswith("data:"):
        mt = header[len("data:"):].split(";")[0]
        if mt:
            media_type = mt
    return make_tombstone(b64data, media_type)


def _codex_walk(node: object) -> bool:
    modified = False
    if isinstance(node, dict):
        for key, value in list(node.items()):
            if key == "encrypted_content":
                continue  # never touch encrypted reasoning blobs
            if (
                key == "image_url"
                and isinstance(value, str)
                and value.startswith("data:")
                and node.get("type") == "input_image"
            ):
                node["image_url"] = tombstone_data_uri(value)
                modified = True
                continue
            if isinstance(value, (dict, list)):
                if _codex_walk(value):
                    modified = True
    elif isinstance(node, list):
        for item in node:
            if isinstance(item, (dict, list)):
                if _codex_walk(item):
                    modified = True
    return modified


def codex_strip_line(obj: object) -> bool:
    """Mutates obj in place per the Codex image policy. Returns True if modified."""
    if not isinstance(obj, dict):
        return False
    payload = obj.get("payload")
    if not isinstance(payload, dict):
        return False

    if payload.get("type") == "compacted" or "replacement_history" in payload:
        return False  # preserves `codex resume` on compacted sessions

    if payload.get("type") == "message" and payload.get("role") == "user":
        return False  # human paste: keep all input_image blocks verbatim

    return _codex_walk(payload)


# ---------------------------------------------------------------------------
# Per-line processing (bytes in, bytes out; untouched lines are byte-identical)
# ---------------------------------------------------------------------------


def iter_raw_lines(data: bytes):
    start = 0
    n = len(data)
    while start < n:
        idx = data.find(b"\n", start)
        if idx == -1:
            yield data[start:n]
            start = n
        else:
            yield data[start:idx + 1]
            start = idx + 1


def _split_line_ending(raw_line: bytes) -> tuple[bytes, bytes]:
    if raw_line.endswith(b"\r\n"):
        return raw_line[:-2], b"\r\n"
    if raw_line.endswith(b"\n"):
        return raw_line[:-1], b"\n"
    return raw_line, b""


def process_lines(raw: bytes, strip_fn) -> bytes:
    pieces = []
    for raw_line in iter_raw_lines(raw):
        content, ending = _split_line_ending(raw_line)
        if not content:
            pieces.append(raw_line)  # blank line -- nothing to parse
            continue
        try:
            text = content.decode("utf-8")
            obj = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError):
            pieces.append(raw_line)  # unparseable -- copy verbatim, bytes exact
            continue

        try:
            modified = strip_fn(obj)
        except Exception:
            # Never let a weird-but-valid JSON shape crash the run; treat it
            # as unmodified and fall back to the byte-identical original.
            modified = False

        if modified:
            try:
                new_text = json.dumps(obj, ensure_ascii=False)
                pieces.append(new_text.encode("utf-8") + ending)
            except (UnicodeEncodeError, ValueError):
                # Re-serialization can fail on content json.loads happily
                # accepted (e.g. a lone UTF-16 surrogate escape) -- never let
                # that crash the whole run; fall back to the byte-identical
                # original line (any tombstone on this line is skipped, but
                # every other line/file still gets processed).
                pieces.append(raw_line)
        else:
            pieces.append(raw_line)  # byte-identical passthrough
    return b"".join(pieces)


STRIP_FNS = {
    "strip-claude": claude_strip_line,
    "strip-codex": codex_strip_line,
}


# ---------------------------------------------------------------------------
# gzip compression (optional, --compress)
# ---------------------------------------------------------------------------
#
# Compression is a storage wrapper only: the bytes going into gzip are the
# SAME processed bytes (stripped/tombstoned transcripts, raw copies) that
# uncompressed mode would write. mtime=0 makes gzip.compress() deterministic
# -- re-compressing identical content yields identical bytes, since the
# gzip header would otherwise embed the current wall-clock time.

GZIP_COMPRESSLEVEL = 6


def gzip_compress_deterministic(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=GZIP_COMPRESSLEVEL, mtime=0)


def gzip_isize(gz_path: Path) -> int:
    """Read the ISIZE footer: the last 4 bytes of a gzip file, little-endian,
    the uncompressed size modulo 2**32. Good enough to compare against a
    freshly-processed byte length for the keep-larger guard -- files here
    top out around 106MB, nowhere near the 4GB wraparound.
    """
    with gz_path.open("rb") as f:
        f.seek(-4, os.SEEK_END)
        return int.from_bytes(f.read(4), "little")


def validated_gzip_isize(gz_path: Path) -> int:
    """gzip_isize(), but only after confirming `gz_path` is actually a
    readable gzip stream. Trusting the trailing 4 bytes of ANY file at the
    .gz path blind (no magic-byte check, no decompression) lets a truncated
    or corrupted .gz -- left by a non-atomic write interrupted mid-way (a
    crash, kill -9, disk-full, a sync-client conflict copy) -- report an
    arbitrary huge "uncompressed size" from whatever garbage bytes happen to
    sit at the end of the file. The keep-larger guard would then compare
    every future run's real content against that garbage and conclude
    "kept-larger" forever, silently and permanently wedging the corrupted
    copy with no automated recovery short of a human noticing and re-running
    with --force. Raises OSError on any validation failure so the caller's
    existing OSError fallback (treat size as unknown, skip the guard, let
    the corrupt copy be overwritten with correct new content) kicks in.
    """
    with gz_path.open("rb") as f:
        magic = f.read(2)
    if magic != b"\x1f\x8b":
        raise OSError(f"{gz_path}: not a gzip file (bad magic bytes {magic!r})")
    # Full-stream decompress to catch a truncated/corrupted body that still
    # happens to start with a valid magic + header. Costs a decompress pass
    # over files that top out around 106MB -- acceptable since this only
    # runs when mtime says the source grew and the keep-larger guard is
    # about to make a permanent-until-noticed decision.
    try:
        with gzip.open(gz_path, "rb") as gz:
            while gz.read(1024 * 1024):
                pass
    except (OSError, EOFError) as e:
        raise OSError(f"{gz_path}: corrupt/truncated gzip stream: {e}") from e
    return gzip_isize(gz_path)


def existing_uncompressed_size(path: Path) -> int:
    """Size to compare against a new processed-byte length for the
    keep-larger guard, regardless of whether `path` is a plain copy or a
    .gz -- lets the guard compare like-for-like across a format migration.
    """
    if path.suffix == ".gz":
        return validated_gzip_isize(path)
    return path.stat().st_size


# ---------------------------------------------------------------------------
# File-level processing
# ---------------------------------------------------------------------------


def process_file(
    src: Path, dest: Path, kind: str, force: bool, dry_run: bool, compress: bool = False
) -> str:
    """Returns 'added', 'updated', 'skipped', 'kept-larger', or 'error:<msg>'.

    With compress=True, the archived copy lives at `dest` + '.gz' instead of
    `dest`. Format migration: if the *other* format's copy exists (a plain
    dest left over from a run with --compress off, or vice versa), it's
    treated as the existing copy for the mtime-skip and keep-larger
    decisions, and is deleted after a successful write in the new format --
    same content, new wrapper, one file per source. This is the one
    sanctioned deletion in an otherwise one-way archiver (see README).
    """
    try:
        src_mtime = os.path.getmtime(src)
    except OSError as e:
        return f"error:stat src: {e}"

    active_dest = dest.with_name(dest.name + ".gz") if compress else dest
    other_dest = dest if compress else dest.with_name(dest.name + ".gz")

    active_exists = active_dest.exists()
    other_exists = other_dest.exists()

    if active_exists and other_exists:
        # Both formats present at once only happens when a prior run's
        # migration cleanup (delete the old-format copy after a successful
        # new-format write) didn't complete -- interrupted mid-way, or the
        # unlink itself failed (permissions, race). Retry it unconditionally
        # on every run, independent of the skip/write decision below, so a
        # stale duplicate is never left on disk forever waiting for a human
        # to notice: the mtime-skip check below is satisfied by active_dest
        # alone and would otherwise return "skipped" without ever touching
        # other_dest again.
        try:
            other_dest.unlink()
            other_exists = False
        except OSError as e:
            log(f"WARN: stale {other_dest} left behind after successful {active_dest} write: {e}")

    existing_dest = active_dest if active_exists else (other_dest if other_exists else None)

    if existing_dest is not None and not force:
        try:
            dest_mtime = os.path.getmtime(existing_dest)
        except OSError:
            dest_mtime = 0.0
        if dest_mtime >= src_mtime:
            return "skipped"
    action = "updated" if existing_dest is not None else "added"

    try:
        raw = src.read_bytes()
    except OSError as e:
        return f"error:read: {e}"

    if kind == "raw":
        processed = raw
    else:
        processed = process_lines(raw, STRIP_FNS[kind])

    # Never let a newer-but-smaller source clobber a larger archived copy --
    # transcript JSONL only grows within a session, so a shrink means the
    # source was truncated, rewritten, or restored from an older state.
    # Compared uncompressed-size to uncompressed-size, even across a format
    # migration (existing_uncompressed_size reads the .gz ISIZE footer when
    # the existing copy is compressed).
    if existing_dest is not None and not force:
        try:
            existing_size = existing_uncompressed_size(existing_dest)
        except OSError:
            existing_size = -1
        if existing_size >= 0 and len(processed) < existing_size:
            return "kept-larger"

    if dry_run:
        return action

    try:
        active_dest.parent.mkdir(parents=True, exist_ok=True)
        to_write = gzip_compress_deterministic(processed) if compress else processed
        active_dest.write_bytes(to_write)
        os.utime(active_dest, (src_mtime, src_mtime))
    except OSError as e:
        return f"error:write: {e}"

    # The new-format write above already succeeded -- action is a success
    # regardless of what happens to the old-format leftover below. Don't
    # fold a cleanup failure into "error:write" (that would mislabel a
    # successful write as an error in the SUMMARY's errors= count); log it
    # distinctly instead. The active_exists/other_exists check at the top of
    # this function retries the cleanup unconditionally on every future run
    # until it succeeds.
    if other_exists:
        try:
            other_dest.unlink()
        except OSError as e:
            log(f"WARN: stale {other_dest} left behind after successful {active_dest} write: {e}")

    return action


def _process_file_safe(
    src: Path, dest: Path, kind: str, force: bool, dry_run: bool, compress: bool = False
) -> str:
    """process_file(), but any uncaught exception degrades to a per-file
    error instead of aborting the whole run. process_lines() already guards
    the individual failure modes we've found in the wild (malformed JSON,
    deeply-nested JSON, unpaired UTF-16 surrogates on re-serialization); this
    is the last line of defense so one poisoned line never costs every other
    source/file in the run its SUMMARY line.
    """
    try:
        return process_file(src, dest, kind, force, dry_run, compress)
    except Exception as e:
        return f"error:{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Source table
# ---------------------------------------------------------------------------


@dataclass
class SourceSpec:
    name: str
    src_root: Path
    dest_root: Path
    pattern: Optional[str]  # None for single-file specs
    kind: str  # 'strip-claude' | 'strip-codex' | 'raw'

    @property
    def is_glob(self) -> bool:
        return self.pattern is not None


def build_sources(machine_root: Path) -> list[SourceSpec]:
    claude_home = home_dir() / ".claude"
    codex_home = home_dir() / ".codex"
    return [
        SourceSpec(
            "claude_projects",
            claude_home / "projects",
            machine_root / "claude" / "projects",
            "**/*.jsonl",
            "strip-claude",
        ),
        SourceSpec(
            "claude_tasks",
            claude_home / "tasks",
            machine_root / "claude" / "tasks",
            "**/*",
            "raw",
        ),
        SourceSpec(
            "codex_sessions",
            codex_home / "sessions",
            machine_root / "codex" / "sessions",
            "**/*.jsonl",
            "strip-codex",
        ),
        SourceSpec(
            "codex_history",
            codex_home / "history.jsonl",
            machine_root / "codex" / "history.jsonl",
            None,
            "raw",
        ),
    ]


# ---------------------------------------------------------------------------
# Misc reporting helpers
# ---------------------------------------------------------------------------


def free_gb(path: Path) -> float:
    st = os.statvfs(str(path))
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
    total = 0
    for _dirpath, _dirnames, filenames in os.walk(root, onerror=lambda e: None):
        total += len(filenames)
    return total


def warn_old_layout(archive_dir: Path, machine_id: str) -> None:
    old_claude = archive_dir / "claude"
    old_codex = archive_dir / "codex"
    if old_claude.exists() or old_codex.exists():
        log(
            f"WARN: old (pre-machine-namespacing) archive layout detected at {archive_dir} "
            f"-- migrate with: mkdir -p {archive_dir}/{machine_id} && "
            f"mv {archive_dir}/claude {archive_dir}/codex {archive_dir}/{machine_id}/ "
            "(not done automatically)."
        )


def apply_result(result: str, src: Path, counts: dict, errors: list, dry_run: bool) -> None:
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
        if dry_run and result in ("added", "updated"):
            verb = "add" if result == "added" else "update"
            log(f"[dry-run] would {verb}: {src}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Mirror Claude Code + Codex transcripts into a machine-namespaced archive."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass BOTH the mtime skip and the keep-larger guard. Exists to repair "
        "archives corrupted by the old base64-regex stripper while sources are still "
        "within retention. Use deliberately.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Log what would be added/updated. Write nothing. Same exit codes.",
    )
    parser.add_argument(
        "--compress",
        action="store_true",
        help="Gzip (level 6, deterministic) every file written to the archive; dest "
        "gains a .gz suffix. Content is identical to uncompressed mode -- compression "
        "is a storage wrapper only. Migrates a plain<->gz copy in place on first write "
        "after the flag changes; see README.",
    )
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)

    archive_dir = resolve_archive_dir()
    machine_id = resolve_machine_id()
    machine_root = archive_dir / machine_id

    configure_logging(machine_root / "backup.log", dry_run=args.dry_run)
    warn_old_layout(archive_dir, machine_id)

    counts = {"added": 0, "updated": 0, "skipped": 0, "kept": 0, "error": 0}
    errors: list = []
    sources_seen = 0

    for spec in build_sources(machine_root):
        if spec.is_glob:
            if not spec.src_root.exists():
                log(f"WARN: source not found, skipping: {spec.src_root}")
                continue
            sources_seen += 1
            for src in spec.src_root.glob(spec.pattern):
                if not src.is_file():
                    continue
                dest = spec.dest_root / src.relative_to(spec.src_root)
                result = _process_file_safe(
                    src, dest, spec.kind, args.force, args.dry_run, args.compress
                )
                apply_result(result, src, counts, errors, args.dry_run)
        else:
            if not spec.src_root.exists():
                log(f"WARN: single-file source not found, skipping: {spec.src_root}")
                continue
            sources_seen += 1
            result = _process_file_safe(
                spec.src_root, spec.dest_root, spec.kind, args.force, args.dry_run, args.compress
            )
            apply_result(result, spec.src_root, counts, errors, args.dry_run)

    total = archive_file_count(machine_root)
    size_str = archive_size_str(machine_root)
    free = free_gb(archive_dir)

    # Errors first, then the low-disk/no-source warnings, so the SUMMARY
    # line is always last (monitors tail the final line) and always matches
    # the frozen `... free_disk=X.XGB` format exactly -- no trailing tokens
    # a monitoring parser anchored on end-of-line wouldn't expect.
    if errors:
        log(f"ERRORS ({len(errors)}):")
        for e in errors:
            log(f"  {e}")

    no_sources = sources_seen == 0
    if no_sources:
        log(
            "ERROR: no transcript sources found (no ~/.claude/projects, ~/.claude/tasks, "
            "~/.codex/sessions, or ~/.codex/history.jsonl) -- archived nothing. "
            "Check HOME and the launchd/cron environment."
        )

    if free < FREE_DISK_WARN_GB:
        log(f"WARN: low disk space on archive volume: {free:.1f}GB free")

    log(
        f"SUMMARY | machine={machine_id} added={counts['added']} updated={counts['updated']} "
        f"skipped={counts['skipped']} kept_larger={counts['kept']} errors={counts['error']} | "
        f"archive_total={total} files | archive_size={size_str} | free_disk={free:.1f}GB"
    )

    sys.exit(1 if (counts["error"] or no_sources) else 0)


if __name__ == "__main__":
    main()
