#!/usr/bin/env python3
"""Extract sessions from an exporter-markdown archive (<user>/YYYY-MM-DD.md files, see
METHODOLOGY.md §1) into grade_in.jsonl, tolerant of all known formats.
Usage: extract_exporter_md.py <archive-root> --out work/grade_in.jsonl

Never hard-fails on a file: unknown formats are emitted with format='freeform' so nothing
silently disappears from the denominator. Session text is budgeted head+tail so a 2.4 MB
session still fits a grader context window. Read-only on the archive.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys

DATE_FILE = re.compile(r"^(\d{4}-\d{2}-\d{2})\.md$")
ANY_MD = re.compile(r"^(\d{4}-\d{2}-\d{2}).*\.md$")
SESSION_HEADER = re.compile(
    r"^### (?P<start>\S+)–(?P<end>\S+) · (?P<source>[^ ·]+) · (?P<title>.+)$"
)
META = re.compile(r"^`(?P<sid>[^`]+)` · (?P<rest>.+)$")
PROJECT = re.compile(r"^## (?!#)(.+)$")
ROLE = re.compile(r"^\*\*(User|Assistant):\*\*\s*$")
TOOL = re.compile(r"(?m)^\s*→ used tool (\S+)\s*$")
SKIP_DIRS = {"tools", ".git", ".idea", "metrics", "__pycache__"}


def budget_text(text: str, budget: int) -> tuple[str, bool]:
    if len(text) <= budget:
        return text, False
    head = int(budget * 0.6)
    tail = budget - head
    return (
        text[:head]
        + f"\n\n[... {len(text) - budget:,} characters elided from the middle ...]\n\n"
        + text[-tail:],
        True,
    )


def parse_exporter_file(path: str, text: str, user: str, date: str, budget: int) -> list[dict]:
    lines = text.splitlines()
    out: list[dict] = []
    project = ""
    i = 0
    while i < len(lines):
        pm = PROJECT.match(lines[i])
        if pm and not lines[i].startswith("### "):
            project = pm.group(1).strip()
            i += 1
            continue
        sm = SESSION_HEADER.match(lines[i]) if lines[i].startswith("### ") else None
        if not sm:
            i += 1
            continue
        start_line = i
        i += 1
        body: list[str] = []
        while i < len(lines) and not lines[i].startswith(("## ", "### ")):
            body.append(lines[i])
            i += 1
        raw = "\n".join(body)
        sid = ""
        for line in body[:5]:
            mm = META.match(line.strip())
            if mm:
                sid = mm.group("sid")
                break
        n_user = len(re.findall(r"(?m)^\*\*User:\*\*\s*$", raw))
        n_asst = len(re.findall(r"(?m)^\*\*Assistant:\*\*\s*$", raw))
        clipped, was_clipped = budget_text(raw, budget)
        out.append(
            {
                "user": user,
                "date": date,
                "path": path,
                "line": start_line + 1,
                "format": "exporter",
                "project": project,
                "source": sm.group("source"),
                "session_id": sid,
                "title": sm.group("title").strip(),
                "start": sm.group("start"),
                "end": sm.group("end"),
                "n_user": n_user,
                "n_assistant": n_asst,
                "n_tool_calls": len(TOOL.findall(raw)),
                "chars": len(raw),
                "clipped": was_clipped,
                "text": clipped,
            }
        )
    return out


def parse_freeform_file(path: str, text: str, user: str, date: str, budget: int) -> list[dict]:
    clipped, was_clipped = budget_text(text, budget)
    return [
        {
            "user": user,
            "date": date,
            "path": path,
            "line": 1,
            "format": "freeform",
            "project": "",
            "source": "unknown",
            "session_id": "",
            "title": text.splitlines()[0][:120] if text.strip() else "(empty)",
            "start": "",
            "end": "",
            "n_user": len(re.findall(r"(?mi)^\*\*(?:User|Пользователь|Користувач)", text)),
            "n_assistant": len(re.findall(r"(?mi)^\*\*(?:Assistant|Claude)", text)),
            "n_tool_calls": len(TOOL.findall(text)),
            "chars": len(text),
            "clipped": was_clipped,
            "text": clipped,
        }
    ]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--budget", type=int, default=60000)
    ap.add_argument("--out", default="-")
    args = ap.parse_args()

    records: list[dict] = []
    for user in sorted(os.listdir(args.root)):
        udir = os.path.join(args.root, user)
        if not os.path.isdir(udir) or user in SKIP_DIRS or user.startswith("."):
            continue
        for fn in sorted(os.listdir(udir)):
            m = ANY_MD.match(fn)
            if not m:
                continue
            path = os.path.join(udir, fn)
            text = open(path, encoding="utf-8", errors="replace").read()
            date = m.group(1)
            if text.startswith("# AI transcripts —") and "### " in text:
                recs = parse_exporter_file(path, text, user, date, args.budget)
                if not recs:
                    recs = parse_freeform_file(path, text, user, date, args.budget)
            else:
                recs = parse_freeform_file(path, text, user, date, args.budget)
            records.extend(recs)

    sink = sys.stdout if args.out == "-" else open(args.out, "w", encoding="utf-8")
    for rec in records:
        sink.write(json.dumps(rec, ensure_ascii=False) + "\n")
    if sink is not sys.stdout:
        sink.close()
    print(f"extracted {len(records)} sessions", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
