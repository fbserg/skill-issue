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
- Prices via pricing_generated.py: dated override -> exact model ID ->
  family fallback. Above-200k tier rates apply only where the registry
  carries them for that model (no blanket long-context multiplier);
  long-context sessions (>200k total tokens) are still flagged in output.
  Family-fallback and unpriced (unknown-family) messages are counted and
  surfaced, never silently costed $0.
- Output is labeled "API-equivalent cost": on Max-plan subscriptions this
  is a proxy for usage-cap consumption, not a real dollar charge.
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

from pricing_generated import (
    PRICING_BY_FAMILY,
    PRICING_BY_MODEL,
    PRICING_DATED,
    SNAPSHOT_VENDORED_AT,
)

SNAPSHOT_STALE_AFTER_DAYS = 120


def snapshot_age_warning(today: datetime | None = None) -> str | None:
    """One-line staleness warning when the vendored pricing snapshot is old.

    New-model staleness self-announces via the family-fallback report; this
    covers the other axis — same-ID price changes that only a re-vendor would
    pick up.
    """
    now = today or datetime.now(timezone.utc)
    vendored = datetime.strptime(SNAPSHOT_VENDORED_AT, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    age_days = (now - vendored).days
    if age_days <= SNAPSHOT_STALE_AFTER_DAYS:
        return None
    return (
        f"WARNING: pricing snapshot is {age_days} days old (vendored {SNAPSHOT_VENDORED_AT}) — "
        "refresh: python3 tools/claude-spend/vendor_pricing.py && "
        "python3 tools/claude-spend/generate_pricing.py tools/claude-spend/litellm_snapshot.json "
        "tools/claude-spend/pricing_overrides.json tools/claude-spend/pricing_generated.py"
    )

# ---------------------------------------------------------------------------
# Pricing lookup (USD per million tokens)
#
# Rates come from pricing_generated.py (regenerate via generate_pricing.py
# from litellm_snapshot.json + pricing_overrides.json — see
# tools/claude-spend/README or the module docstrings). Lookup order:
# dated override (pricing_overrides.json regimes, keyed by message
# timestamp) -> exact model-ID match -> family fallback. Family fallback
# and unpriced (unknown-family) messages are counted and surfaced in
# summary output rather than silently costing $0.
# ---------------------------------------------------------------------------

LONG_CTX_THRESHOLD = 200_000  # tokens; above-200k tier rates apply if the model has them


def model_family(model: str) -> str | None:
    if not model:
        return None
    m = model.lower()
    if "fable" in m or "mythos" in m:
        return "fable"
    if "opus" in m:
        return "opus"
    if "sonnet" in m:
        return "sonnet"
    if "haiku" in m:
        return "haiku"
    return None


def parse_ts(ts: str | None) -> datetime | None:
    if not ts:
        return None
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def resolve_rates(model: str, ts: str | None) -> tuple[dict[str, float] | None, str]:
    """Return (rates, source). source is one of 'dated', 'exact', 'family', 'unpriced'."""
    if not model:
        return None, "unpriced"

    dt = parse_ts(ts)
    for override in PRICING_DATED:
        if override["model"] != model:
            continue
        start = parse_ts(override["effective_from"])
        end = parse_ts(override["effective_until"])
        if dt is None:
            continue
        if start and dt < start:
            continue
        if end and dt > end:
            continue
        return override["rates"], "dated"

    if model in PRICING_BY_MODEL:
        return PRICING_BY_MODEL[model], "exact"

    fam = model_family(model)
    if fam and fam in PRICING_BY_FAMILY:
        return PRICING_BY_FAMILY[fam], "family"

    return None, "unpriced"


def compute_cost(model: str, usage: dict, ts: str | None = None) -> tuple[float, str]:
    """Compute USD cost for one deduplicated assistant message.

    Returns (cost, source) where source is 'dated', 'exact', 'family', or
    'unpriced' — callers use source to count fallback/unpriced messages
    instead of letting them silently cost $0.
    """
    rates, source = resolve_rates(model, ts)
    if rates is None:
        return 0.0, source

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

    # Above-200k tier rates apply only where the resolved entry carries
    # them (Claude 4.6+, Fable, Sonnet 5: standard pricing at any length —
    # no blanket surcharge).
    total_ctx = inp + cr + cc
    tiered = total_ctx > LONG_CTX_THRESHOLD and "in_200k" in rates

    def rate(field: str) -> float:
        if tiered:
            return rates.get(f"{field}_200k", rates[field])
        return rates[field]

    cost = (
        inp * rate("in")
        + out * rate("out")
        + cc_5m * rate("cache_5m")
        + cc_1h * rate("cache_1h")
        + cr * rate("cache_read")
    ) / 1_000_000

    return cost, source


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

        # pricing-source counts, keyed by the raw model string seen in the
        # transcript — never silently $0 (see resolve_rates)
        self.fallback_by_model: dict[str, int] = defaultdict(int)
        self.unpriced_by_model: dict[str, int] = defaultdict(int)

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
                self.unpriced_by_model[model] += 1
                continue

            cost, source = compute_cost(model, usage, ts)
            if source == "family":
                self.fallback_by_model[model] += 1

            inp_tok = usage.get("input_tokens", 0) or 0
            out_tok = usage.get("output_tokens", 0) or 0
            cr_tok = usage.get("cache_read_input_tokens", 0) or 0
            cc_tok = usage.get("cache_creation_input_tokens", 0) or 0

            total_ctx = inp_tok + cr_tok + cc_tok
            if total_ctx > LONG_CTX_THRESHOLD:
                self.long_ctx_turns += 1

            self.cost_by_family[fam] += cost
            self.total_cost += cost

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
        # Only include if there's cost data (or something worth reporting) in the window
        if stat.total_cost == 0.0 and not stat.skills and not stat.fallback_by_model and not stat.unpriced_by_model:
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
        f"\n{'Rank':<5} {'Cost':>9} {'Fable':>9} {'Opus':>9} {'Sonnet':>9} {'Haiku':>9} "
        f"{'LongCtx':>8} {'HitPct':>7} {'Skills':<30} {'SessionFile'}"
    )
    print("-" * 130)
    for i, s in enumerate(shown, 1):
        fable = s.cost_by_family.get("fable", 0)
        opus = s.cost_by_family.get("opus", 0)
        sonnet = s.cost_by_family.get("sonnet", 0)
        haiku = s.cost_by_family.get("haiku", 0)
        hit = s.cache_hit_pct_overall()
        skills = ", ".join(sorted({e["skill"] for e in s.skills if e.get("skill")}))[:28]
        smell = " SMELL" if s.has_cache_invalidation_smell() else ""
        hit_str = f"{hit:.0f}%" if hit is not None else "n/a"
        fname = s.path.name[:40]
        print(
            f"{i:<5} {fmt_usd(s.total_cost):>9} {fmt_usd(fable):>9} {fmt_usd(opus):>9} "
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
    fallback_by_model: dict[str, int] = defaultdict(int)
    unpriced_by_model: dict[str, int] = defaultdict(int)
    for s in sessions:
        for fam, cost in s.cost_by_family.items():
            by_fam[fam] += cost
        for model, n in s.fallback_by_model.items():
            fallback_by_model[model] += n
        for model, n in s.unpriced_by_model.items():
            unpriced_by_model[model] += n

    smells = [s for s in sessions if s.has_cache_invalidation_smell()]
    long_ctx = [s for s in sessions if s.long_ctx_turns > 0]

    print(f"\n=== Claude Spend — Last {days} Days ===")
    print(f"Sessions with activity:  {len(sessions)}")
    print(f"Total API-equivalent cost: {fmt_usd(total)}")
    print(f"  Fable:                 {fmt_usd(by_fam.get('fable', 0))}")
    print(f"  Opus:                  {fmt_usd(by_fam.get('opus', 0))}")
    print(f"  Sonnet:                {fmt_usd(by_fam.get('sonnet', 0))}")
    print(f"  Haiku:                 {fmt_usd(by_fam.get('haiku', 0))}")
    print(f"Sessions with long-ctx:  {len(long_ctx)}")
    print(f"Cache-invalidation smells: {len(smells)}")

    if fallback_by_model:
        total_fallback = sum(fallback_by_model.values())
        print(f"Priced via family fallback (no exact/dated model match): {total_fallback} message(s)")
        for model, n in sorted(fallback_by_model.items(), key=lambda kv: -kv[1]):
            print(f"  {model}: {n}")
    if unpriced_by_model:
        total_unpriced = sum(unpriced_by_model.values())
        print(f"UNPRICED (unknown model family, cost NOT counted above): {total_unpriced} message(s)")
        for model, n in sorted(unpriced_by_model.items(), key=lambda kv: -kv[1]):
            print(f"  {model}: {n}")

    stale = snapshot_age_warning()
    if stale:
        print(stale)


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
                    "fallback_by_model": dict(s.fallback_by_model),
                    "unpriced_by_model": dict(s.unpriced_by_model),
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
