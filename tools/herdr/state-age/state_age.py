#!/usr/bin/env python3
"""Show actionable agent-state ages in Herdr's sidebar."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import signal
import subprocess
import sys
import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from socket_rpc import rpc

PLUGIN_ID = "serg.state-age"
METADATA_SOURCE = f"plugin:{PLUGIN_ID}"
SYMBOLS = {"blocked": "◆", "working": "◐", "done": "●", "idle": "○", "unknown": "·"}
TOKEN_NAMES = (
    "blocked_age",
    "working_age",
    "done_age",
    *(f"symbol_{state}" for state in SYMBOLS),
)
VISIBLE_STATUSES = frozenset({"blocked", "working", "done"})
KNOWN_STATUSES = VISIBLE_STATUSES | {"idle", "unknown"}
WORKING_THRESHOLD_SECONDS = 15 * 60
REFRESH_SECONDS = 30
METADATA_TTL_MS = 90_000
MAX_CONSECUTIVE_REFRESH_FAILURES = 3


def current_epoch_seconds() -> float:
    override = os.environ.get("HERDR_STATE_AGE_NOW_EPOCH")
    if override is not None:
        return float(override)
    return time.time()


def format_age(elapsed_seconds: float) -> str:
    seconds = max(0, int(elapsed_seconds))
    if seconds < 60:
        return "<1m"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    if hours < 24:
        remainder_minutes = minutes % 60
        return f"{hours}h{remainder_minutes}m" if remainder_minutes else f"{hours}h"
    days = hours // 24
    remainder_hours = hours % 24
    return f"{days}d{remainder_hours}h" if remainder_hours else f"{days}d"


def desired_tokens(status: str, elapsed_seconds: float) -> dict[str, str]:
    tokens = {f"symbol_{status}": SYMBOLS[status]}
    if status == "working" and elapsed_seconds < WORKING_THRESHOLD_SECONDS:
        return tokens
    if status in VISIBLE_STATUSES:
        tokens[f"{status}_age"] = format_age(elapsed_seconds)
    return tokens


def reconcile_states(
    previous: dict[str, dict[str, Any]],
    panes: list[dict[str, Any]],
    now_epoch: float,
) -> dict[str, dict[str, Any]]:
    reconciled: dict[str, dict[str, Any]] = {}
    for pane in panes:
        pane_id = pane.get("pane_id")
        agent = pane.get("agent")
        status = pane.get("agent_status")
        if not isinstance(pane_id, str) or not isinstance(agent, str):
            continue
        if status not in KNOWN_STATUSES:
            continue

        old_entry = previous.get(pane_id, {})
        old_status = old_entry.get("status")
        old_since = old_entry.get("since_epoch")
        if old_status == status and isinstance(old_since, (int, float)):
            since_epoch = float(old_since)
        else:
            since_epoch = now_epoch
        reconciled[pane_id] = {"status": status, "since_epoch": since_epoch}
    return reconciled


def status_change_from_event(event: dict[str, Any]) -> tuple[str, str] | None:
    data = event.get("data")
    if not isinstance(data, dict):
        return None
    pane_id = data.get("pane_id")
    status = data.get("agent_status")
    if not isinstance(pane_id, str) or status not in KNOWN_STATUSES:
        return None
    return pane_id, status


def state_directory() -> Path:
    configured = os.environ.get("HERDR_PLUGIN_STATE_DIR")
    base = Path(configured) if configured else Path.home() / ".local" / "state" / "herdr-state-age"
    session = hashlib.sha256(os.environ["HERDR_SOCKET_PATH"].encode()).hexdigest()[:20]
    return base / session


def state_path() -> Path:
    return state_directory() / "state.json"


def daemon_pid_path() -> Path:
    return state_directory() / "daemon.pid"


def log_path() -> Path:
    return state_directory() / "daemon.log"


@contextmanager
def state_lock() -> Iterator[None]:
    directory = state_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "state.lock").open("a+", encoding="utf-8") as lock_file:
        fcntl.flock(lock_file, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)


def load_states_unlocked() -> dict[str, dict[str, Any]]:
    try:
        content = state_path().read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    data = json.loads(content)
    panes = data.get("panes")
    if not isinstance(panes, dict):
        raise TypeError("state file has no panes object")
    return panes


def save_states_unlocked(states: dict[str, dict[str, Any]]) -> None:
    directory = state_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=directory,
        prefix="state.",
        suffix=".tmp",
        delete=False,
    ) as temporary:
        json.dump({"panes": states}, temporary, sort_keys=True)
        temporary.write("\n")
        temporary_path = Path(temporary.name)
    os.replace(temporary_path, state_path())


def list_panes() -> list[dict[str, Any]]:
    return rpc("pane.list", {})["panes"]


def report_tokens(pane_id: str, tokens: dict[str, str]) -> None:
    rpc(
        "pane.report_metadata",
        {
            "pane_id": pane_id,
            "source": METADATA_SOURCE,
            "tokens": {name: tokens.get(name) for name in TOKEN_NAMES},
            "ttl_ms": METADATA_TTL_MS,
            "seq": time.time_ns(),
        },
    )


def refresh_all_panes() -> None:
    now_epoch = current_epoch_seconds()
    with state_lock():
        # Keep the live snapshot, saved transition, and metadata report ordered
        # against event handlers. Otherwise a refresh can publish a stale state
        # after a newer pane.agent_status_changed event.
        panes = list_panes()
        previous = load_states_unlocked()
        states = reconcile_states(previous, panes, now_epoch)
        save_states_unlocked(states)
        for pane_id, entry in states.items():
            tokens = desired_tokens(
                str(entry["status"]),
                now_epoch - float(entry["since_epoch"]),
            )
            report_tokens(pane_id, tokens)


def record_event(event: dict[str, Any]) -> None:
    change = status_change_from_event(event)
    if change is None:
        return
    pane_id, status = change
    now_epoch = current_epoch_seconds()
    with state_lock():
        states = load_states_unlocked()
        old_entry = states.get(pane_id, {})
        if old_entry.get("status") != status:
            states[pane_id] = {"status": status, "since_epoch": now_epoch}
        save_states_unlocked(states)
        entry = states[pane_id]
        tokens = desired_tokens(status, now_epoch - float(entry["since_epoch"]))
        report_tokens(pane_id, tokens)


def process_exists(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def daemon_process_exists(pid: int) -> bool:
    if not process_exists(pid):
        return False
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        check=False,
        text=True,
        timeout=2,
    )
    script_path = str(Path(__file__).resolve())
    return (
        result.returncode == 0
        and script_path in result.stdout
        and " daemon" in result.stdout
    )


def read_daemon_pid() -> int | None:
    try:
        return int(daemon_pid_path().read_text(encoding="utf-8").strip())
    except (FileNotFoundError, ValueError):
        return None


def ensure_daemon() -> None:
    if os.environ.get("HERDR_STATE_AGE_NO_DAEMON") == "1":
        return
    directory = state_directory()
    directory.mkdir(parents=True, exist_ok=True)
    with (directory / "daemon-start.lock").open("a+", encoding="utf-8") as start_lock:
        fcntl.flock(start_lock, fcntl.LOCK_EX)
        pid = read_daemon_pid()
        if pid is not None and daemon_process_exists(pid):
            return

        environment = os.environ.copy()
        environment.pop("HERDR_PLUGIN_EVENT", None)
        environment.pop("HERDR_PLUGIN_EVENT_JSON", None)
        environment.pop("HERDR_PLUGIN_CONTEXT_JSON", None)
        with log_path().open("a", encoding="utf-8") as daemon_log:
            process = subprocess.Popen(
                [sys.executable, str(Path(__file__).resolve()), "daemon"],
                cwd=Path(__file__).resolve().parent,
                env=environment,
                stdin=subprocess.DEVNULL,
                stdout=daemon_log,
                stderr=subprocess.STDOUT,
                start_new_session=True,
                close_fds=True,
            )
        daemon_pid_path().write_text(f"{process.pid}\n", encoding="utf-8")


def remove_own_pid_file() -> None:
    pid_path = daemon_pid_path()
    if read_daemon_pid() != os.getpid():
        return
    try:
        pid_path.unlink()
    except FileNotFoundError:
        pass


def run_daemon() -> None:
    failures = 0
    try:
        while True:
            try:
                refresh_all_panes()
                failures = 0
            except (
                json.JSONDecodeError,
                OSError,
                subprocess.SubprocessError,
                TypeError,
                ValueError,
            ) as error:
                failures += 1
                print(f"state-age refresh failed ({failures}): {error}", flush=True)
                if failures >= MAX_CONSECUTIVE_REFRESH_FAILURES:
                    raise
            time.sleep(REFRESH_SECONDS)
    finally:
        remove_own_pid_file()


def stop_daemon() -> None:
    pid = read_daemon_pid()
    if pid is None:
        return
    if daemon_process_exists(pid):
        os.kill(pid, signal.SIGTERM)
    try:
        daemon_pid_path().unlink()
    except FileNotFoundError:
        pass


def event_from_environment() -> dict[str, Any]:
    raw_event = os.environ.get("HERDR_PLUGIN_EVENT_JSON", "{}")
    event = json.loads(raw_event)
    if not isinstance(event, dict):
        raise TypeError("HERDR_PLUGIN_EVENT_JSON is not an object")
    return event


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        choices=("start", "event", "once", "daemon", "stop"),
    )
    return parser.parse_args()


def main() -> int:
    mode = parse_args().mode
    if mode == "start":
        refresh_all_panes()
        ensure_daemon()
    elif mode == "event":
        record_event(event_from_environment())
        ensure_daemon()
    elif mode == "once":
        refresh_all_panes()
    elif mode == "daemon":
        run_daemon()
    elif mode == "stop":
        stop_daemon()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
