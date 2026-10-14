"""install.sh and check-install.py under a throwaway HOME.

Nothing in the real ~/.claude or ~/.codex tree is touched.
"""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
INSTALL_SH = REPO_ROOT / "scripts" / "install.sh"
CHECK_INSTALL_PY = REPO_ROOT / "scripts" / "check-install.py"

AGENT_NAMES = tuple(sorted(path.name for path in (REPO_ROOT / "agents").glob("*.md")))
SHARED_SKILL_NAMES = ("authenticity-check", "humanizer", "zero")


def _run(command: list[str], home: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        command, env={**os.environ, "HOME": str(home)}, cwd=str(REPO_ROOT), check=False,
        capture_output=True, text=True,
    )


def _install(home: Path) -> subprocess.CompletedProcess:
    result = _run(["bash", str(INSTALL_SH)], home)
    assert result.returncode == 0, f"install.sh failed:\n{result.stdout}\n{result.stderr}"
    return result


def _check_install(home: Path) -> subprocess.CompletedProcess:
    return _run(["python3", str(CHECK_INSTALL_PY)], home)


@pytest.fixture
def temp_home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    return tmp_path_factory.mktemp("skill-issue-test-home")


def test_fresh_install_links_everything_and_rerun_is_idempotent(temp_home: Path) -> None:
    _install(temp_home)
    expected_links = {
        temp_home / ".claude" / "agents" / name: REPO_ROOT / "agents" / name for name in AGENT_NAMES
    } | {
        temp_home / ".claude" / "skills" / name: REPO_ROOT / "skills" / "shared" / name
        for name in SHARED_SKILL_NAMES
    }
    for link, target in expected_links.items():
        assert link.is_symlink() and link.resolve() == target.resolve(), link
    check_result = _check_install(temp_home)
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr

    _install(temp_home)
    for link, target in expected_links.items():
        assert link.resolve() == target.resolve(), f"{link} changed on rerun"


def test_check_install_fails_when_agent_symlink_missing(temp_home: Path) -> None:
    _install(temp_home)
    (temp_home / ".claude" / "agents" / "worker.md").unlink()
    check_result = _check_install(temp_home)
    assert check_result.returncode != 0
    assert "worker.md" in check_result.stdout + check_result.stderr


@pytest.mark.parametrize("managed_dir", [".claude/agents", ".claude/skills", ".codex/skills"])
def test_install_does_not_clobber_externally_managed_dir(temp_home: Path, managed_dir: str) -> None:
    external_dir = temp_home / "external"
    external_dir.mkdir()
    stub = external_dir / "worker.md"
    stub.write_text("externally managed\n")
    link = temp_home / managed_dir
    link.parent.mkdir()
    link.symlink_to(external_dir, target_is_directory=True)

    result = _install(temp_home)
    assert "externally managed" in result.stdout and "skipping" in result.stdout
    assert list(external_dir.iterdir()) == [stub]
    assert stub.read_text() == "externally managed\n"


def test_check_install_skips_symlinked_agents_dir(temp_home: Path) -> None:
    _install(temp_home)
    agents_dir = temp_home / ".claude" / "agents"
    shutil.rmtree(agents_dir)
    external_dir = temp_home / "external-agents"
    external_dir.mkdir()
    agents_dir.symlink_to(external_dir, target_is_directory=True)

    check_result = _check_install(temp_home)
    assert check_result.returncode == 0, check_result.stdout + check_result.stderr
    skip_count = check_result.stdout.count(f"SKIP: {agents_dir} is externally managed")
    assert skip_count == len(AGENT_NAMES), check_result.stdout
