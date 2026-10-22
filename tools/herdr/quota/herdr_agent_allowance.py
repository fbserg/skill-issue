#!/usr/bin/env python3
"""Render the active agent's quota from CodexBar's shared, read-only snapshot."""

from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from socket_rpc import rpc

# ceiling: CodexBar 0.57 widget schema; update this reader if its snapshot changes.
SNAPSHOT = (
    Path.home()
    / "Library/Group Containers/Y5PE65HELJ.com.steipete.codexbar/widget-snapshot.json"
)
# CodexBar intentionally throttles background Claude CLI probes to 15 minutes.
STALE_SECONDS = {"codex": 180, "claude": 16 * 60}


def timestamp(value: str) -> float:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()


def render(entry: dict[str, Any], now: float) -> str:
    provider = entry["provider"].capitalize()
    windows = [entry[k] for k in ("primary", "secondary", "tertiary") if entry.get(k)]
    weekly = next((w for w in windows if w.get("windowMinutes") == 10080), None)
    if weekly is None:
        return f"{provider} weekly quota unavailable"
    reset = weekly.get("resetsAt")
    if reset is None:
        return f"{provider} {100 - round(weekly['usedPercent'])}% left · reset unknown"
    reset_epoch = timestamp(reset)
    if reset_epoch <= now:
        return f"{provider} reset passed · awaiting refresh"
    age = max(0, now - timestamp(entry["updatedAt"]))
    left = 100 - round(weekly["usedPercent"])
    if age > STALE_SECONDS[entry["provider"]]:
        return f"{provider} 7d {left}% left · stale {int(age // 60)}m"
    elapsed = (now - (reset_epoch - 7 * 86400)) * 100 / (7 * 86400)
    if not 0 <= elapsed <= 100:
        raise ValueError("Weekly reset lies outside its seven-day window")
    delta = round(weekly["usedPercent"]) - int(elapsed)
    if delta == 0:
        pace = "on pace"
    elif delta > 0:
        pace = f"↑{delta}"
    else:
        pace = f"↓{-delta}"
    cached = f" · cached {int(age // 60)}m" if age > 180 else ""
    return f"{provider} 7d {left}% left · {pace}{cached}"


def active_provider() -> str | None:
    pane = os.environ.get("HERDR_ACTIVE_PANE_ID")
    if not pane:
        return None
    return next(
        (
            p.get("agent")
            for p in rpc("pane.list", {}, timeout=1)["panes"]
            if p["pane_id"] == pane
        ),
        None,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("codex", "claude"))
    parser.add_argument("--snapshot", type=Path, default=SNAPSHOT)
    args = parser.parse_args()
    provider = args.provider or active_provider()
    if provider not in ("claude", "codex"):
        return
    try:
        snapshot = json.loads(args.snapshot.read_text())
    except FileNotFoundError:
        print(f"{provider.capitalize()} quota unavailable · start CodexBar")
        return
    entry = next((e for e in snapshot["entries"] if e["provider"] == provider), None)
    if entry is None:
        print(f"{provider.capitalize()} quota unavailable")
        return
    print(render(entry, time.time()))


if __name__ == "__main__":
    main()
