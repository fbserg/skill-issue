#!/usr/bin/env python3
"""Run one command in a bounded process group while holding its lock."""

from __future__ import annotations

import argparse
import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path


def duration_seconds(raw: str) -> float:
    match = re.fullmatch(r"([0-9]+(?:\.[0-9]+)?)([smh]?)", raw)
    if not match:
        raise argparse.ArgumentTypeError(f"invalid duration: {raw}")
    value = float(match.group(1))
    multiplier = {"": 1, "s": 1, "m": 60, "h": 3600}[match.group(2)]
    return value * multiplier


def process_group_exists(process_group: int) -> bool:
    try:
        os.killpg(process_group, 0)
    except ProcessLookupError:
        return False
    return True


def stop_process_group(process: subprocess.Popen, grace_seconds: float) -> None:
    # Teardown must finish before the caller removes the shared lock. Repeated
    # launchd signals cannot interrupt this section and orphan descendants.
    for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, signal.SIG_IGN)

    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        process.wait()
        return

    deadline = time.monotonic() + grace_seconds
    while process_group_exists(process.pid) and time.monotonic() < deadline:
        time.sleep(0.05)
    if process_group_exists(process.pid):
        os.killpg(process.pid, signal.SIGKILL)
    process.wait()


def remove_lock(lock_dir: Path) -> None:
    try:
        (lock_dir / "pid").unlink()
        lock_dir.rmdir()
    except FileNotFoundError:
        pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--timeout", required=True, type=duration_seconds)
    parser.add_argument("--kill-after", required=True, type=duration_seconds)
    parser.add_argument("--lock-dir", required=True, type=Path)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if not args.command:
        parser.error("a command is required")
    return args


def main() -> int:
    args = parse_args()
    process: subprocess.Popen | None = None
    shutdown_signal: int | None = None
    handled_signals = (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
    original_handlers = {signum: signal.getsignal(signum) for signum in handled_signals}

    def request_shutdown(signum: int, _frame: object) -> None:
        nonlocal shutdown_signal
        if shutdown_signal is None:
            shutdown_signal = signum

    for signum in handled_signals:
        signal.signal(signum, request_shutdown)

    try:
        process = subprocess.Popen(args.command, start_new_session=True)
        deadline = time.monotonic() + args.timeout
        while shutdown_signal is None:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                stop_process_group(process, args.kill_after)
                return 124
            try:
                return process.wait(timeout=min(remaining, 0.2))
            except subprocess.TimeoutExpired:
                pass

        stop_process_group(process, args.kill_after)
        return 128 + shutdown_signal
    finally:
        remove_lock(args.lock_dir)
        for signum, handler in original_handlers.items():
            signal.signal(signum, handler)


if __name__ == "__main__":
    sys.exit(main())
