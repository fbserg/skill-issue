#!/usr/bin/env python3
"""Local full-text search over archived + live Claude Code transcripts.

Companion to backup.py: the archiver mirrors transcripts into
TRANSCRIPT_ARCHIVE_DIR; this builds a disposable SQLite FTS5 index over that
archive (every machine namespace) plus the live ~/.claude/projects tree, so
"when did we discuss X" is a sub-second query instead of a zgrep crawl.

Usage:
  search.py index                     # incremental ingest (stat-skip unchanged)
  search.py search QUERY [filters]    # FTS5 MATCH query, ranked, with snippets
      --project SUBSTR    filter by project dir substring
      --role ROLE         user | assistant | tool_use | tool_result
      --since / --until   ISO date bounds on message timestamp
      --limit N           max results (default 20)
      --files             print matching transcript paths only
  search.py status                    # index freshness + size

Design notes (2026-07-30):
  - SQLite FTS5 external-content table; text stored once in `messages`,
    plain unicode61 tokenizer, no stemming (this corpus is code). Compound
    identifiers split on punctuation on BOTH sides, so `ninja_cli.py` or
    `/tmp/zebra_dir` as a query matches via AND of its parts — maximum
    recall, which is what incident archaeology wants.
  - Incremental refresh skips any file whose (mtime, size) is unchanged, so
    a nightly re-index only reads new bytes. Dehydrated cloud files are
    stat-only until they actually change.
  - The DB is a regenerable cache, never authoritative. Delete it freely.
  - Query syntax is FTS5 MATCH: bare words AND together, "double quotes"
    for phrases, OR/NOT supported. For raw substring/regex needs, fall back
    to ripgrep/zgrep on the archive itself.
"""

from __future__ import annotations

import argparse
import gzip
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

DEFAULT_DB = Path.home() / ".cache/transcript-search/transcripts.db"
TEXT_CAP = 20_000  # chars per message row; single blocks beyond this are truncated


def db_path() -> Path:
    raw = os.environ.get("TRANSCRIPT_SEARCH_DB", "").strip()
    return Path(raw).expanduser() if raw else DEFAULT_DB


def resolve_sources() -> dict[str, Path]:
    """Archive roots (all machine namespaces) plus the live projects tree."""
    sources: dict[str, Path] = {}
    raw = os.environ.get("TRANSCRIPT_ARCHIVE_DIR", "").strip()
    if raw:
        archive_root = Path(raw).expanduser()
        for machine_dir in sorted(archive_root.glob("*/claude/projects")):
            machine = machine_dir.parts[len(archive_root.parts)]
            sources[f"archive:{machine}"] = machine_dir
    else:
        print(
            "note: TRANSCRIPT_ARCHIVE_DIR not set — indexing live transcripts only",
            file=sys.stderr,
        )
    live = Path.home() / ".claude/projects"
    if live.exists():
        sources["live"] = live
    return sources


SCHEMA = """
CREATE TABLE IF NOT EXISTS sources (
    path TEXT PRIMARY KEY,
    mtime REAL NOT NULL,
    size INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY,
    src TEXT NOT NULL,
    project TEXT NOT NULL,
    session TEXT NOT NULL,
    path TEXT NOT NULL,
    role TEXT NOT NULL,
    ts TEXT NOT NULL,
    text TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_messages_path ON messages(path);
CREATE INDEX IF NOT EXISTS idx_messages_project_ts ON messages(project, ts);
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text,
    content='messages', content_rowid='id',
    tokenize="unicode61 remove_diacritics 2"
);
CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, text) VALUES (new.id, new.text);
END;
CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, text)
    VALUES ('delete', old.id, old.text);
END;
"""


def connect() -> sqlite3.Connection:
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.executescript(SCHEMA)
    return con


def iter_message_rows(path: Path):
    """Yield (role, ts, text) rows from one transcript jsonl(.gz) file."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", errors="replace") as fh:
        for line in fh:
            try:
                record = json.loads(line)
            except (json.JSONDecodeError, UnicodeDecodeError):
                continue
            role = record.get("type", "?")
            ts = (record.get("timestamp") or "")[:19]
            content = (record.get("message") or {}).get("content")
            if isinstance(content, str):
                if content.strip():
                    yield role, ts, content[:TEXT_CAP]
                continue
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                btype = block.get("type")
                if btype == "text" and block.get("text", "").strip():
                    yield role, ts, block["text"][:TEXT_CAP]
                elif btype == "tool_use":
                    payload = f"{block.get('name')}: {json.dumps(block.get('input', {}))}"
                    yield "tool_use", ts, payload[:TEXT_CAP]
                elif btype == "tool_result":
                    raw = block.get("content")
                    if isinstance(raw, str):
                        text = raw
                    elif isinstance(raw, list):
                        text = " ".join(
                            x.get("text", "") for x in raw if isinstance(x, dict)
                        )
                    else:
                        continue
                    if text.strip():
                        yield "tool_result", ts, text[:TEXT_CAP]


def project_and_session(src_root: Path, path: Path) -> tuple[str, str]:
    rel = path.relative_to(src_root)
    project = rel.parts[0] if len(rel.parts) > 1 else "?"
    stem = rel.parts[1] if len(rel.parts) > 1 else rel.name
    return project, stem.split(".")[0]


def cmd_index() -> None:
    con = connect()
    # Compare numerically: REAL round-trips the mtime double exactly, whereas
    # SQLite's float->string formatting does not match Python's repr.
    known = {
        path: (mtime, size)
        for path, mtime, size in con.execute("SELECT path, mtime, size FROM sources")
    }
    ingested = skipped = 0
    started = time.time()
    for src_name, src_root in resolve_sources().items():
        for path in src_root.rglob("*.jsonl*"):
            if path.suffix not in (".jsonl", ".gz"):
                continue
            st = path.stat()
            key = str(path)
            if known.get(key) == (st.st_mtime, st.st_size):
                skipped += 1
                continue
            project, session = project_and_session(src_root, path)
            con.execute("DELETE FROM messages WHERE path = ?", (key,))
            con.executemany(
                "INSERT INTO messages (src, project, session, path, role, ts, text)"
                " VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    (src_name, project, session, key, role, ts, text)
                    for role, ts, text in iter_message_rows(path)
                ),
            )
            con.execute(
                "INSERT OR REPLACE INTO sources (path, mtime, size) VALUES (?, ?, ?)",
                (key, st.st_mtime, st.st_size),
            )
            ingested += 1
            if ingested % 500 == 0:
                con.commit()
                print(f"  ...{ingested} files in {time.time() - started:.0f}s", flush=True)
    con.commit()
    total_rows = con.execute("SELECT count(*) FROM messages").fetchone()[0]
    print(
        f"indexed {ingested} new/changed files ({skipped} unchanged), "
        f"{total_rows} message rows, {time.time() - started:.0f}s, "
        f"db={db_path().stat().st_size / 1e6:.0f}MB"
    )
    con.close()


def cmd_search(args: argparse.Namespace) -> None:
    con = connect()
    where, params = ["messages_fts MATCH ?"], [args.query]
    if args.project:
        where.append("m.project LIKE ?")
        params.append(f"%{args.project}%")
    if args.role:
        where.append("m.role = ?")
        params.append(args.role)
    if args.since:
        where.append("m.ts >= ?")
        params.append(args.since)
    if args.until:
        where.append("m.ts <= ?")
        params.append(args.until + "~")  # '~' sorts after any timestamp suffix
    sql = f"""
        SELECT m.ts, m.project, m.session, m.role,
               snippet(messages_fts, 0, '>>>', '<<<', ' … ', 40), m.path
        FROM messages_fts JOIN messages m ON m.id = messages_fts.rowid
        WHERE {" AND ".join(where)}
        ORDER BY rank LIMIT ?
    """
    params.append(args.limit)
    rows = con.execute(sql, params).fetchall()
    if args.files:
        for path in dict.fromkeys(r[5] for r in rows):
            print(path)
        con.close()
        return
    for ts, project, session, role, snip, path in rows:
        print(f"[{ts}] {project} {session[:8]} {role}")
        print(f"  {' '.join(snip.split())[:400]}")
        print(f"  {path}\n")
    if not rows:
        print("no matches")
    con.close()


def cmd_status() -> None:
    path = db_path()
    if not path.exists():
        print(f"no index at {path} — run `search.py index` first")
        return
    con = connect()
    files, rows = con.execute(
        "SELECT (SELECT count(*) FROM sources), (SELECT count(*) FROM messages)"
    ).fetchone()
    newest = con.execute("SELECT max(ts) FROM messages").fetchone()[0]
    print(
        f"db={path} size={path.stat().st_size / 1e6:.0f}MB "
        f"files={files} rows={rows} newest_message={newest}"
    )
    con.close()


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Full-text search over archived + live Claude Code transcripts"
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("index")
    sub.add_parser("status")
    search = sub.add_parser("search")
    search.add_argument("query")
    search.add_argument("--project")
    search.add_argument("--role")
    search.add_argument("--since")
    search.add_argument("--until")
    search.add_argument("--limit", type=int, default=20)
    search.add_argument("--files", action="store_true")
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    if args.cmd == "index":
        cmd_index()
    elif args.cmd == "status":
        cmd_status()
    else:
        cmd_search(args)


if __name__ == "__main__":
    main()
