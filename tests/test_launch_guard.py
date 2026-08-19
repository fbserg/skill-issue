"""Subprocess tests for scripts/launch-guard.sh."""
from __future__ import annotations

import json
import os
import subprocess
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_GUARD = REPO_ROOT / "scripts" / "launch-guard.sh"


def _run_guard(
    state_dir: Path, cwd: Path, *arguments: str
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(LAUNCH_GUARD), *arguments],
        cwd=cwd,
        env={**os.environ, "LAUNCH_GUARD_DIR": str(state_dir)},
        capture_output=True,
        text=True,
        timeout=5,
    )


@contextmanager
def _live_guard(
    state_dir: Path, cwd: Path, prompt: str
) -> Iterator[subprocess.Popen[str]]:
    process = subprocess.Popen(
        [str(LAUNCH_GUARD), "--prompt", prompt, "--", "sleep", "30"],
        cwd=cwd,
        env={**os.environ, "LAUNCH_GUARD_DIR": str(state_dir)},
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        entries = list(state_dir.glob("*.json")) if state_dir.exists() else []
        if entries:
            data = json.loads(entries[0].read_text())
            if data["pid"] == process.pid:
                break
        if process.poll() is not None:
            stdout, stderr = process.communicate()
            pytest.fail(
                f"guarded sleep exited early ({process.returncode}): "
                f"stdout={stdout!r}, stderr={stderr!r}"
            )
        time.sleep(0.01)
    else:
        pytest.fail("guarded sleep did not write its state entry")

    try:
        yield process
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=5)


def test_first_launch_runs_and_writes_entry(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    cwd = tmp_path / "checkout"
    cwd.mkdir()

    result = _run_guard(
        state_dir,
        cwd,
        "--prompt",
        "  inspect\n  this checkout  ",
        "--",
        "sh",
        "-c",
        "echo ran",
    )

    assert result.returncode == 0
    assert result.stdout.strip() == "ran"
    entries = list(state_dir.glob("*.json"))
    assert len(entries) == 1
    data = json.loads(entries[0].read_text())
    assert isinstance(data["pid"], int)
    assert data["prompt_head"] == "inspect this checkout"


def test_live_duplicate_is_refused(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    cwd = tmp_path / "checkout"
    cwd.mkdir()

    with _live_guard(state_dir, cwd, "same prompt"):
        result = _run_guard(
            state_dir,
            cwd,
            "--prompt",
            "same prompt",
            "--",
            "sh",
            "-c",
            "echo should-not-run",
        )

    assert result.returncode == 3
    assert "Refusing" in result.stderr
    assert result.stdout == ""


def test_dead_process_entry_is_pruned_and_launch_runs(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    cwd = tmp_path / "checkout"
    cwd.mkdir()
    prompt = "reusable prompt"

    first = _run_guard(
        state_dir, cwd, "--prompt", prompt, "--", "sh", "-c", "exit 0"
    )
    assert first.returncode == 0

    second = _run_guard(
        state_dir, cwd, "--prompt", prompt, "--", "sh", "-c", "echo ran"
    )
    assert second.returncode == 0
    assert second.stdout.strip() == "ran"


def test_force_runs_despite_live_duplicate(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    cwd = tmp_path / "checkout"
    cwd.mkdir()

    with _live_guard(state_dir, cwd, "same prompt"):
        result = _run_guard(
            state_dir,
            cwd,
            "--force",
            "--prompt",
            "same prompt",
            "--",
            "sh",
            "-c",
            "echo forced",
        )

    assert result.returncode == 0
    assert result.stdout.strip() == "forced"
    assert "warning" in result.stderr


def test_same_prompt_in_different_cwd_runs(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    first_cwd = tmp_path / "checkout-one"
    second_cwd = tmp_path / "checkout-two"
    first_cwd.mkdir()
    second_cwd.mkdir()

    with _live_guard(state_dir, first_cwd, "same prompt"):
        result = _run_guard(
            state_dir,
            second_cwd,
            "--prompt",
            "same prompt",
            "--",
            "sh",
            "-c",
            "echo ran",
        )

    assert result.returncode == 0
    assert result.stdout.strip() == "ran"


def test_prompt_difference_after_character_200_is_refused(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    cwd = tmp_path / "checkout"
    cwd.mkdir()
    shared_prefix = "x" * 200

    with _live_guard(state_dir, cwd, f"{shared_prefix} first suffix"):
        result = _run_guard(
            state_dir,
            cwd,
            "--prompt",
            f"{shared_prefix} second suffix",
            "--",
            "sh",
            "-c",
            "echo should-not-run",
        )

    assert result.returncode == 3
    assert "Refusing" in result.stderr


def test_missing_separator_is_usage_error(tmp_path: Path) -> None:
    cwd = tmp_path / "checkout"
    cwd.mkdir()

    result = _run_guard(tmp_path / "state", cwd, "--prompt", "prompt")

    assert result.returncode == 2
    assert result.stderr.startswith("Usage:")


def test_prompt_defaults_to_last_command_argument(tmp_path: Path) -> None:
    state_dir = tmp_path / "state"
    cwd = tmp_path / "checkout"
    cwd.mkdir()

    result = _run_guard(
        state_dir,
        cwd,
        "--",
        "sh",
        "-c",
        'printf "%s" "$1"',
        "placeholder",
        "prompt from argv",
    )

    assert result.returncode == 0
    assert result.stdout == "prompt from argv"
    entry = json.loads(next(state_dir.glob("*.json")).read_text())
    assert entry["prompt_head"] == "prompt from argv"
