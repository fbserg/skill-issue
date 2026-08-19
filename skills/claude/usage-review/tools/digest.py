#!/usr/bin/env python3
"""Render a non-punitive digest from graded sessions (output of grade.py). Usage: digest.py graded.jsonl

Deliberately: no composite score, no leaderboard, no cost column. Per-user the
manager sees one strength, one coaching note, and any risk that needs a human
look. Org-level shows the dimension that is actually moving and the risk queue.
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import statistics
import sys

DIMS = ["goal_clarity", "context_grounding", "verification",
        "iteration_efficiency", "outcome", "delegation_fit"]
HOME = os.path.expanduser("~")


def short_path(p: str) -> str:
    return p.replace(HOME, "~", 1) if p.startswith(HOME) else p


HUMAN_REVIEW = {"credentials_in_transcript", "client_prod_system_touched",
                "destructive_operation", "production_data_touched",
                "security_relevant_change"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("graded_jsonl")
    args = ap.parse_args()
    rows = [json.loads(line) for line in open(args.graded_jsonl, encoding="utf-8")]
    ok = [r for r in rows if "error" not in r]
    gradable = [r for r in ok if r["grade"]["gradable"]]
    skipped = [r for r in ok if not r["grade"]["gradable"]]

    out = []
    out.append("# AI usage digest")
    out.append("")
    out.append(f"{len(gradable)} sessions graded, {len(skipped)} skipped as export artifacts "
               f"({dict(collections.Counter(r['grade']['not_gradable_reason'] for r in skipped))}).")
    out.append("")
    out.append("## Where the org actually varies")
    out.append("")
    out.append("| dimension | mean | share scoring 0-1 |")
    out.append("|---|---|---|")
    for dim in DIMS:
        vals = [r["grade"][dim] for r in gradable]
        low = sum(1 for v in vals if v <= 1) / len(vals)
        out.append(f"| {dim} | {statistics.mean(vals):.2f}/4 | {low*100:.0f}% |")
    out.append("")

    queue = [r for r in gradable if HUMAN_REVIEW & set(r["grade"].get("risk_flags", []))]
    out.append(f"## Needs a human look ({len(queue)})")
    out.append("")
    for r in sorted(queue, key=lambda r: r["user"]):
        flags = ", ".join(sorted(HUMAN_REVIEW & set(r["grade"]["risk_flags"])))
        out.append(f"- **{r['user']}** {r['date']} `{short_path(r['path'])}:{r['line']}` "
                   f"— {flags} — {r['grade']['highlight']}")
    out.append("")

    out.append("## Per person")
    out.append("")
    by_user = collections.defaultdict(list)
    for r in gradable:
        by_user[r["user"]].append(r)
    for user in sorted(by_user):
        rs = by_user[user]
        means = {d: statistics.mean([r["grade"][d] for r in rs]) for d in DIMS}
        best = max(means, key=means.get)
        worst = min(means, key=means.get)
        strongest = max(rs, key=lambda r: sum(r["grade"][d] for d in DIMS))
        weakest = min(rs, key=lambda r: sum(r["grade"][d] for d in DIMS))
        out.append(f"### {user} ({len(rs)} sessions sampled)")
        out.append(f"- strongest dimension: {best} {means[best]:.1f}/4 · "
                   f"weakest: {worst} {means[worst]:.1f}/4")
        out.append(f"- worth reading: `{short_path(strongest['path'])}:{strongest['line']}` "
                   f"— {strongest['grade']['highlight']}")
        out.append(f"- coaching: {weakest['grade']['coaching_note']}")
        waste = collections.Counter(w for r in rs for w in r["grade"].get("waste_signals", []))
        if waste:
            out.append(f"- recurring waste: {', '.join(f'{k} x{v}' for k, v in waste.most_common(3))}")
        out.append("")
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
