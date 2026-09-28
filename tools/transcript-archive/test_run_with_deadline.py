from __future__ import annotations

import importlib.util
import signal
import sys
from pathlib import Path
from unittest.mock import patch


MODULE_PATH = Path(__file__).with_name("run_with_deadline.py")
SPEC = importlib.util.spec_from_file_location("run_with_deadline", MODULE_PATH)
assert SPEC and SPEC.loader
supervisor = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(supervisor)


def test_signal_during_spawn_is_deferred_until_process_group_stops(tmp_path: Path) -> None:
    real_popen = supervisor.subprocess.Popen
    real_remove_lock = supervisor.remove_lock
    spawned_process = None

    def spawn(*_args: object, **kwargs: object) -> supervisor.subprocess.Popen:
        nonlocal spawned_process
        spawned_process = real_popen(["/bin/sleep", "30"], **kwargs)
        handler = signal.getsignal(signal.SIGTERM)
        assert callable(handler)
        handler(signal.SIGTERM, None)
        return spawned_process

    def remove_lock_after_process_group_stops(lock_dir: Path) -> None:
        assert spawned_process is not None
        assert spawned_process.poll() is not None
        real_remove_lock(lock_dir)

    argv = [
        "run_with_deadline.py",
        "--timeout",
        "10s",
        "--kill-after",
        "1s",
        "--lock-dir",
        str(tmp_path),
        "fake-command",
    ]
    with (
        patch.object(sys, "argv", argv),
        patch.object(supervisor.subprocess, "Popen", side_effect=spawn),
        patch.object(
            supervisor,
            "remove_lock",
            side_effect=remove_lock_after_process_group_stops,
        ) as remove_lock,
    ):
        assert supervisor.main() == 128 + signal.SIGTERM

    remove_lock.assert_called_once_with(tmp_path)


def test_repeated_signal_during_teardown_is_ignored() -> None:
    process = real_process = supervisor.subprocess.Popen(
        ["/bin/sleep", "30"], start_new_session=True
    )
    real_killpg = supervisor.os.killpg

    def killpg(pid: int, sent_signal: int) -> None:
        if sent_signal == signal.SIGTERM:
            handler = signal.getsignal(signal.SIGTERM)
            assert handler == signal.SIG_IGN
        real_killpg(pid, sent_signal)

    original_handlers = {
        signum: signal.getsignal(signum)
        for signum in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM)
    }
    try:
        with patch.object(supervisor.os, "killpg", side_effect=killpg):
            supervisor.stop_process_group(process, 0.1)
    finally:
        for signum, handler in original_handlers.items():
            signal.signal(signum, handler)
    assert real_process.poll() is not None
