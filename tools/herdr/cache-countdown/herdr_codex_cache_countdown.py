#!/usr/bin/env python3
"""Print the focused Herdr Codex pane's prompt-cache countdown."""

from __future__ import annotations

import json
import mmap
import os
import re
import sqlite3
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from socket_rpc import rpc

GPT_5_6_CACHE_TTL_SECONDS = 30 * 60
EXACT_TTL_MODEL = re.compile(r"^gpt-(\d+)\.(\d+)(?:[-.].*)?$")


def focused_codex_session_id() -> str | None:
    pane_id = os.environ.get("HERDR_ACTIVE_PANE_ID")
    if not pane_id:
        return None

    agent = next(
        (
            p
            for p in rpc("pane.list", {}, timeout=1)["panes"]
            if p["pane_id"] == pane_id
        ),
        None,
    )
    if agent is None or agent.get("agent") != "codex" or not agent.get("agent_session"):
        return None

    session_id = agent["agent_session"]["value"]
    if str(uuid.UUID(session_id)) != session_id:
        raise ValueError(
            f"Herdr returned a non-canonical Codex session ID: {session_id!r}"
        )
    return session_id


def thread_rollout(codex_home: Path, session_id: str) -> tuple[Path, str] | None:
    database_path = codex_home / "state_5.sqlite"
    if not database_path.is_file():
        return None

    database_uri = f"file:{database_path}?mode=ro"
    with sqlite3.connect(database_uri, uri=True, timeout=0.25) as database:
        row = database.execute(
            "SELECT rollout_path, COALESCE(model, '') FROM threads WHERE id = ?",
            (session_id,),
        ).fetchone()
    if row is None:
        return None

    rollout_path, model = row
    rollout = Path(rollout_path)
    if not rollout.is_file():
        return None
    return rollout, model


def model_has_exact_thirty_minute_ttl(model: str) -> bool:
    match = EXACT_TTL_MODEL.fullmatch(model)
    if match is None:
        return False
    major, minor = (int(part) for part in match.groups())
    return major > 5 or (major == 5 and minor >= 6)


def latest_token_count_timestamp(rollout_path: Path) -> datetime | None:
    with rollout_path.open("rb") as rollout_file:
        if rollout_path.stat().st_size == 0:
            return None
        with mmap.mmap(rollout_file.fileno(), 0, access=mmap.ACCESS_READ) as rollout:
            end = len(rollout)
            if rollout[end - 1 : end] == b"\n":
                end -= 1
            while end > 0:
                start = rollout.rfind(b"\n", 0, end)
                line = rollout[start + 1 : end]
                if b'"token_count"' in line:
                    event: dict[str, Any] = json.loads(line)
                    if (
                        event.get("type") == "event_msg"
                        and event.get("payload", {}).get("type") == "token_count"
                    ):
                        timestamp = event.get("timestamp")
                        if not isinstance(timestamp, str):
                            raise ValueError("Codex token_count event has no timestamp")
                        return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                if start < 0:
                    break
                end = start
    return None


def current_epoch_seconds() -> float:
    override = os.environ.get("CODEX_CACHE_COUNTDOWN_NOW_EPOCH")
    if override is not None:
        return float(override)
    return datetime.now(timezone.utc).timestamp()


def render_countdown(last_activity: datetime) -> str:
    remaining_seconds = int(
        last_activity.timestamp() + GPT_5_6_CACHE_TTL_SECONDS - current_epoch_seconds()
    )
    if remaining_seconds <= 0:
        return "cache cold"
    minutes, seconds = divmod(remaining_seconds, 60)
    return f"cache {minutes}:{seconds:02d}"


def main() -> int:
    session_id = focused_codex_session_id()
    if session_id is None:
        return 0

    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    thread = thread_rollout(codex_home, session_id)
    if thread is None:
        return 0
    rollout_path, model = thread
    if not model_has_exact_thirty_minute_ttl(model):
        return 0

    last_activity = latest_token_count_timestamp(rollout_path)
    if last_activity is None:
        return 0
    print(render_countdown(last_activity))
    return 0


if __name__ == "__main__":
    sys.exit(main())
