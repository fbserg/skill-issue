#!/usr/bin/env python3
"""Claude Code spend analyzer.

Stolen from hong (https://github.com/hyang0129/dot-claude — tools/weekly-spend.py
and the skill-token-analysis methodology), adapted for general per-project use.

Scans ~/.claude/projects/**/*.jsonl for sessions, rolls up token usage and
estimated cost per session and per skill invocation.

Correctness notes:
- Deduplicates usage by message.id (not record UUID) — one API response can
  appear across multiple JSONL records (one per content block).
- Accounts for cache_creation (5m and 1h tiers) vs cache_read tiers.
- Flags long-context (>200k total tokens) with 2x surcharge on non-cache-read.
- Identifies skill invocations via the Skill tool_use blocks.

Usage:
    python tools/claude-spend/spend.py [--days N] [--project PATH] [--skill NAME]

Options:
    --days N        Analyse sessions with activity in last N days [default: 30]
    --project PATH  Project root to filter sessions by (repeatable); omit for all projects
    --skill NAME    Filter to sessions invoking a specific skill name
    --top N         Show top N sessions by cost [default: 20]
    --json          Emit raw JSON instead of tables
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator


# ---------------------------------------------------------------------------
# Pricing table (USD per million tokens, June 2026)
# IMPORTANT: Verify against https://www.anthropic.com/api before relying on
# these numbers for billing decisions. Marked for easy editing.
# ---------------------------------------------------------------------------
PRICING: dict[str, dict[str, float]] = {
    # claude-opus-4, claude-opus-4-5, older opus-3
    "opus": {
        "in": 15.00,  # input tokens
        "out": 75.00,  # output tokens
        "cache_5m": 18.75,  # cache-creation (5-minute ephemeral)
        "cache_1h": 30.00,  # cache-creation (1-hour ephemeral)  -- 2x input
        "cache_read": 1.50,  # cache-read
    },
    # claude-sonnet-4, claude-sonnet-3-7, claude-sonnet-3-5
    "sonnet": {
        "in": 3.00,
        "out": 15.00,
        "cache_5m": 3.75,
        "cache_1h": 6.00,
        "cache_read": 0.30,
    },
    # claude-haiku-3-5, older haiku
    "haiku": {
        "in": 1.00,
        "out": 5.00,
        "cache_5m": 1.25,
        "cache_1h": 2.00,
        "cache_read": 0.10,
    },
}

LONG_CTX_THRESHOLD = 200_000  # tokens; surcharge triggers above this
LONG_CTX_MULTIPLIER = 2.0


def model_family(model: str) -> str | None:
    if not model:
        return None
    m = model.lower()
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return None


def compute_cost(model: str, usage: dict) -> float:
    """Compute USD cost for one deduplicated assistant message."""
    fam = model_family(model)
    if fam is None:
        return 0.0
    p = PRICING[fam]

    inp = usage.get("input_tokens", 0) or 0
    out = usage.get("output_tokens", 0) or 0
    cr = usage.get("cache_read_input_tokens", 0) or 0
    cc = usage.get("cache_creation_input_tokens", 0) or 0

    # Try to get the detailed cache_creation breakdown (5m vs 1h).
    cc_detail = usage.get("cache_creation") or {}
    cc_5m = cc_detail.get("ephemeral_5m_input_tokens", 0) or 0
    cc_1h = cc_detail.get("ephemeral_1h_input_tokens", 0) or 0
    if cc_5m + cc_1h == 0:
        # No breakdown — assume all 5m (conservative; real cost may differ).
        cc_5m = cc

    # Long-context surcharge applies to non-cache-read tokens.
    total_ctx = inp + cr + cc
    mult = LONG_CTX_MULTIPLIER if total_ctx > LONG_CTX_THRESHOLD else 1.0

    cost = (
        inp * p["in"] * mult
        + out * p["out"] * mult
        + cc_5m * p["cache_5m"] * mult
        + cc_1h * p["cache_1h"] * mult
        + cr * p["cache_read"]  # cache_read not surcharged
    ) / 1_000_000

    return cost


def cache_hit_pct(usage: dict) -> float | None:
    """Return cache hit % or None if no cache data present."""
    cr = usage.get("cache_read_input_tokens", 0) or 0
    cc = usage.get("cache_creation_input_tokens", 0) or 0
    inp = usage.get("input_tokens", 0) or 0
    total = inp + cc + cr
    if total == 0:
        return None
    return cr / total * 100.0


# ---------------------------------------------------------------------------
# Session scanning
# ---------------------------------------------------------------------------

def project_dir_prefix(project_root: Path) -> str:
    """Claude encodes a project path as its absolute path with '/' and '.' -> '-'."""
    return str(project_root.resolve()).replace("/", "-").replace(".", "-")


def find_session_jsonl_files(projects_root: Path, project_roots: list[Path]) -> list[Path]:
    """Return main-thread session JSONL files, optionally filtered to projects.

    A project filter matches its own dir plus subdirectories/worktrees
    (Claude encodes those as the same prefix with extra '-' segments).
    """
    prefixes = [project_dir_prefix(p) for p in project_roots]
    files: list[Path] = []
    for d in projects_root.iterdir():
        if not d.is_dir():
            continue
        name = d.name
        if prefixes and not any(name == p or name.startswith(p + "-") for p in prefixes):
            continue
        for f in d.glob("*.jsonl"):
            # Skip subagent transcripts in root of project dir
            if "subagents" in f.parts or "workflows" in f.parts:
                continue
            files.append(f)
    return sorted(files)


def iter_records(path: Path) -> Iterator[dict]:
    """Yield parsed JSON records from a JSONL file, skipping bad lines."""
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    except OSError:
        return


class SessionStats:
    """Aggregated stats for one session file."""

    def __init__(self, path: Path):
        self.path = path
        self.session_id: str | None = None
        self.first_ts: str | None = None
        self.last_ts: str | None = None

        # per-family cost and token totals
        self.cost_by_family: dict[str, float] = defaultdict(float)
        self.tokens_by_family: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self.total_cost: float = 0.0
        self.long_ctx_turns: int = 0

        # skill invocations: list of {skill, tool_use_id, line}
        self.skills: list[dict] = []

        # cache stats for smell detection
        self.cache_writes: list[int] = []  # cc per turn
        self.cache_reads: list[int] = []  # cr per turn

        # seen message IDs for deduplication
        self._seen_msg_ids: set[str] = set()

        # pending skill tool_use blocks (id -> entry)
        self._pending_skills: dict[str, dict] = {}

    def process(self, cutoff: datetime | None = None) -> None:
        """Read the JSONL file and populate stats."""
        for rec in iter_records(self.path):
            # Track session ID
            sid = rec.get("sessionId")
            if sid and not self.session_id:
                self.session_id = sid

            ts = rec.get("timestamp")
            if ts:
                if not self.first_ts or ts < self.first_ts:
                    self.first_ts = ts
                if not self.last_ts or ts > self.last_ts:
                    self.last_ts = ts

            msg = rec.get("message") or {}
            role = msg.get("role")
            model = msg.get("model", "")
            usage = msg.get("usage")
            msg_id = msg.get("id")

            # Detect skill invocations from assistant tool_use blocks
            content = msg.get("content") or []
            if isinstance(content, list):
                for part in content:
                    if not isinstance(part, dict):
                        continue
                    ptype = part.get("type")
                    if role == "assistant" and ptype == "tool_use" and part.get("name") == "Skill":
                        tu_id = part.get("id") or ""
                        inp = part.get("input") or {}
                        self._pending_skills[tu_id] = {
                            "skill": inp.get("skill"),
                            "args": inp.get("args"),
                            "ts": ts,
                        }
                    elif role == "user" and ptype == "tool_result":
                        tu_id = part.get("tool_use_id")
                        if tu_id in self._pending_skills:
                            entry = self._pending_skills.pop(tu_id)
                            self.skills.append(entry)

            # Cost accounting — deduplicate by message ID
            if not (model and usage and msg_id):
                continue
            if msg_id in self._seen_msg_ids:
                continue
            self._seen_msg_ids.add(msg_id)

            # Apply cutoff filter
            if cutoff and ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    if dt < cutoff:
                        continue
                except Exception:
                    pass

            fam = model_family(model)
            if fam is None:
                continue

            inp_tok = usage.get("input_tokens", 0) or 0
            out_tok = usage.get("output_tokens", 0) or 0
            cr_tok = usage.get("cache_read_input_tokens", 0) or 0
            cc_tok = usage.get("cache_creation_input_tokens", 0) or 0

            total_ctx = inp_tok + cr_tok + cc_tok
            if total_ctx > LONG_CTX_THRESHOLD:
                self.long_ctx_turns += 1

            c = compute_cost(model, usage)
            self.cost_by_family[fam] += c
            self.total_cost += c

            tf = self.tokens_by_family[fam]
            tf["in"] += inp_tok
            tf["out"] += out_tok
            tf["cr"] += cr_tok
            tf["cc"] += cc_tok

            self.cache_writes.append(cc_tok)
            self.cache_reads.append(cr_tok)

    def cache_hit_pct_overall(self) -> float | None:
        total_cr = sum(self.cache_reads)
        total_cc = sum(self.cache_writes)
        total_in = sum(self.tokens_by_family[f]["in"] for f in self.tokens_by_family)
        denom = total_in + total_cc + total_cr
        if denom == 0:
            return None
        return total_cr / denom * 100.0

    def has_cache_invalidation_smell(self) -> bool:
        """Detect mid-session spike in cache writes after a period of reads.

        Pattern: turns with high cache_write after turns where cache_read
        dominated (suggests a tool schema load or large context change).
        """
        if len(self.cache_writes) < 4:
            return False
        # Look for a big cache-write spike in the second half of the session
        mid = len(self.cache_writes) // 2
        early_cw = sum(self.cache_writes[:mid])
        late_cw = sum(self.cache_writes[mid:])
        # Smell: late cache writes > 2x early, and early reads > early writes
        early_cr = sum(self.cache_reads[:mid])
        if late_cw > 2 * max(early_cw, 1) and early_cr > early_cw:
            return True
        return False


def scan_sessions(
    projects_root: Path,
    project_roots: list[Path],
    days: int = 30,
    skill_filter: str | None = None,
) -> list[SessionStats]:
    """Scan matching session files and return SessionStats objects."""
    files = find_session_jsonl_files(projects_root, project_roots)
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    results: list[SessionStats] = []
    for path in files:
        stat = SessionStats(path)
        stat.process(cutoff=cutoff)
        # Only include if there's cost data in the window
        if stat.total_cost == 0.0 and not stat.skills:
            continue
        if skill_filter and not any((s.get("skill") or "").lower() == skill_filter.lower() for s in stat.skills):
            continue
        results.append(stat)

    results.sort(key=lambda s: s.total_cost, reverse=True)
    return results


# ---------------------------------------------------------------------------
# Skill rollup
# ---------------------------------------------------------------------------


def rollup_by_skill(sessions: list[SessionStats]) -> dict[str, dict]:
    """Aggregate cost and session count by skill name."""
    skill_data: dict[str, dict] = defaultdict(lambda: {"sessions": 0, "invocations": 0, "cost": 0.0})
    for s in sessions:
        skills_in_session = {entry["skill"] for entry in s.skills if entry.get("skill")}
        for sk in skills_in_session:
            skill_data[sk]["sessions"] += 1
            skill_data[sk]["cost"] += s.total_cost
        for entry in s.skills:
            sk = entry.get("skill")
            if sk:
                skill_data[sk]["invocations"] += 1
    return skill_data


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def fmt_usd(v: float) -> str:
    return f"${v:.4f}"


def fmt_tokens(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(n)


def print_session_table(sessions: list[SessionStats], top: int = 20) -> None:
    shown = sessions[:top]
    print(
        f"\n{'Rank':<5} {'Cost':>9} {'Opus':>9} {'Sonnet':>9} {'Haiku':>9} "
        f"{'LongCtx':>8} {'HitPct':>7} {'Skills':<30} {'SessionFile'}"
    )
    print("-" * 120)
    for i, s in enumerate(shown, 1):
        opus = s.cost_by_family.get("opus", 0)
        sonnet = s.cost_by_family.get("sonnet", 0)
        haiku = s.cost_by_family.get("haiku", 0)
        hit = s.cache_hit_pct_overall()
        skills = ", ".join(sorted({e["skill"] for e in s.skills if e.get("skill")}))[:28]
        smell = " SMELL" if s.has_cache_invalidation_smell() else ""
        hit_str = f"{hit:.0f}%" if hit is not None else "n/a"
        fname = s.path.name[:40]
        print(
            f"{i:<5} {fmt_usd(s.total_cost):>9} {fmt_usd(opus):>9} "
            f"{fmt_usd(sonnet):>9} {fmt_usd(haiku):>9} "
            f"{s.long_ctx_turns:>8} {hit_str:>7} {skills:<30} {fname}{smell}"
        )


def print_skill_table(skill_data: dict[str, dict]) -> None:
    print(f"\n{'Skill':<35} {'Sessions':>9} {'Invoc':>7} {'Cost':>10}")
    print("-" * 65)
    for sk, d in sorted(skill_data.items(), key=lambda kv: -kv[1]["cost"]):
        print(f"{sk:<35} {d['sessions']:>9} {d['invocations']:>7} {fmt_usd(d['cost']):>10}")


def print_summary(sessions: list[SessionStats], days: int) -> None:
    total = sum(s.total_cost for s in sessions)
    by_fam: dict[str, float] = defaultdict(float)
    for s in sessions:
        for fam, cost in s.cost_by_family.items():
            by_fam[fam] += cost

    smells = [s for s in sessions if s.has_cache_invalidation_smell()]
    long_ctx = [s for s in sessions if s.long_ctx_turns > 0]

    print(f"\n=== Claude Spend — Last {days} Days ===")
    print(f"Sessions with activity:  {len(sessions)}")
    print(f"Total estimated cost:    {fmt_usd(total)}")
    print(f"  Opus:                  {fmt_usd(by_fam.get('opus', 0))}")
    print(f"  Sonnet:                {fmt_usd(by_fam.get('sonnet', 0))}")
    print(f"  Haiku:                 {fmt_usd(by_fam.get('haiku', 0))}")
    print(f"Sessions with long-ctx:  {len(long_ctx)}")
    print(f"Cache-invalidation smells: {len(smells)}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> int:
    ap = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    ap.add_argument("--days", type=int, default=30, help="Analyse activity in last N days [default: 30]")
    ap.add_argument("--skill", metavar="NAME", help="Filter to sessions invoking this skill")
    ap.add_argument("--top", type=int, default=20, help="Show top N sessions by cost [default: 20]")
    ap.add_argument("--json", action="store_true", help="Emit raw JSON instead of formatted tables")
    ap.add_argument(
        "--projects-root", default=str(Path.home() / ".claude" / "projects"), help="Root of ~/.claude/projects"
    )
    ap.add_argument(
        "--project",
        action="append",
        default=[],
        metavar="PATH",
        help="Project root to filter sessions by (repeatable); omit for all projects",
    )
    args = ap.parse_args()

    projects_root = Path(args.projects_root)
    if not projects_root.exists():
        print(f"ERROR: projects root not found: {projects_root}", file=sys.stderr)
        return 1

    project_roots = [Path(p) for p in args.project]
    scope = ", ".join(str(p) for p in project_roots) or "all projects"
    print(f"Scanning sessions in {projects_root} for {scope} (last {args.days} days)...", file=sys.stderr)
    sessions = scan_sessions(projects_root, project_roots, days=args.days, skill_filter=args.skill)
    print(f"Found {len(sessions)} sessions with spend.", file=sys.stderr)

    if args.json:
        out = []
        for s in sessions:
            out.append(
                {
                    "session_file": str(s.path),
                    "session_id": s.session_id,
                    "first_ts": s.first_ts,
                    "last_ts": s.last_ts,
                    "total_cost_usd": round(s.total_cost, 6),
                    "cost_by_family": {k: round(v, 6) for k, v in s.cost_by_family.items()},
                    "long_ctx_turns": s.long_ctx_turns,
                    "cache_hit_pct": s.cache_hit_pct_overall(),
                    "cache_invalidation_smell": s.has_cache_invalidation_smell(),
                    "skills": s.skills,
                }
            )
        json.dump(out, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    print_summary(sessions, args.days)
    print_session_table(sessions, top=args.top)
    skill_data = rollup_by_skill(sessions)
    if skill_data:
        print("\n=== Per-Skill Rollup ===")
        print_skill_table(skill_data)
    return 0


if __name__ == "__main__":
    sys.exit(main())
