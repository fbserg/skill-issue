"""Boundary tests for issue #1: install.sh agent symlinks + shared skill dedup.

Runs scripts/install.sh and scripts/check-install.py under a throwaway
temp HOME so nothing in the real ~/.claude / ~/.codex tree is touched.
Run with: python3 -m pytest tests/test_B_1_install.py -v
"""
from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
CHECK_INSTALL_PY = REPO_ROOT / "scripts" / "check-install.py"

AGENT_NAMES = ("bulk.md", "explore-mid.md", "opus-worker.md", "worker.md")
SHARED_SKILL_NAMES = (
    "authentic-writing",
    "authenticity-check",
    "humanizer",
    "ww",
    "zero",
)


def _run_install(home: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["bash", str(INSTALL_SH)],
        env={**os.environ, "HOME": str(home)},
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


def _run_check_install(home: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", str(CHECK_INSTALL_PY)],
        env={**os.environ, "HOME": str(home)},
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def temp_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("skill-issue-test-home")


def test_B_1_A_fresh_install_creates_all_four_agent_symlinks(temp_home: Path) -> None:
    result = _run_install(temp_home)
    assert result.returncode == 0, f"install.sh failed:\n{result.stdout}\n{result.stderr}"

    agents_dir = temp_home / ".claude" / "agents"
    for name in AGENT_NAMES:
        link = agents_dir / name
        assert link.is_symlink(), f"{link} was not created as a symlink"
        expected_target = (REPO_ROOT / "agents" / name).resolve()
        assert link.resolve() == expected_target, (
            f"{link} resolves to {link.resolve()}, expected {expected_target}"
        )


def test_B_1_B_install_is_idempotent(temp_home: Path) -> None:
    first = _run_install(temp_home)
    assert first.returncode == 0, f"first install.sh run failed:\n{first.stderr}"

    agents_dir = temp_home / ".claude" / "agents"
    links_before = {
        name: (agents_dir / name).resolve() for name in AGENT_NAMES
    }

    second = _run_install(temp_home)
    assert second.returncode == 0, f"second install.sh run failed:\n{second.stderr}"

    links_after = {
        name: (agents_dir / name).resolve() for name in AGENT_NAMES
    }
    assert links_before == links_after, "agent symlink targets changed across reruns"


def test_B_1_C_shared_skills_resolve_to_skills_shared_only(temp_home: Path) -> None:
    result = _run_install(temp_home)
    assert result.returncode == 0, f"install.sh failed:\n{result.stderr}"

    claude_skills_dir = temp_home / ".claude" / "skills"
    for name in SHARED_SKILL_NAMES:
        link = claude_skills_dir / name
        assert link.is_symlink(), f"{link} was not created as a symlink"
        resolved = link.resolve()
        expected_target = (REPO_ROOT / "skills" / "shared" / name).resolve()
        assert resolved == expected_target, (
            f"{link} resolves to {resolved}, expected {expected_target} "
            "(skills/shared/ must be the sole canonical source)"
        )


def test_B_1_D_check_install_passes_against_temp_home_install(temp_home: Path) -> None:
    install_result = _run_install(temp_home)
    assert install_result.returncode == 0, f"install.sh failed:\n{install_result.stderr}"

    check_result = _run_check_install(temp_home)
    assert check_result.returncode == 0, (
        f"check-install.py failed against a fresh install:\n"
        f"stdout={check_result.stdout}\nstderr={check_result.stderr}"
    )


def test_B_1_E_check_install_fails_when_agent_symlink_missing(temp_home: Path) -> None:
    install_result = _run_install(temp_home)
    assert install_result.returncode == 0, f"install.sh failed:\n{install_result.stderr}"

    # Sabotage one agent symlink to prove check-install.py actually covers agents/.
    missing_link = temp_home / ".claude" / "agents" / "worker.md"
    assert missing_link.is_symlink()
    missing_link.unlink()

    check_result = _run_check_install(temp_home)
    assert check_result.returncode != 0, (
        "check-install.py should fail when an expected agent symlink is missing, "
        f"but exited 0. stdout={check_result.stdout}"
    )
    assert "worker.md" in check_result.stderr or "worker.md" in check_result.stdout
