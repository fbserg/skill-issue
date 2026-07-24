"""Worktree-escape guard in hooks/claude/pretool-bash.sh.

Reproduces the exact escape observed in this session — a Bash command run
from a `.claude/worktrees/<name>` session that `cd`s (or otherwise writes)
into the shared checkout by absolute path — and proves it is now blocked,
alongside proof that legitimate reads of the shared checkout still pass.

Run with: python3 -m pytest tests/test_pretool_bash_worktree_escape.py -v
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
HOOK = REPO_ROOT / "hooks" / "claude" / "pretool-bash.sh"


def _run_hook(command: str, project_dir: Path) -> subprocess.CompletedProcess:
    payload = json.dumps({"tool_input": {"command": command}})
    return subprocess.run(
        ["bash", str(HOOK)],
        input=payload,
        env={
            "PATH": "/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin",
            "CLAUDE_PROJECT_DIR": str(project_dir),
            "HOME": str(project_dir),
        },
        cwd=str(project_dir),
        capture_output=True,
        text=True,
    )


@pytest.fixture
def fake_worktree(tmp_path: Path) -> tuple[Path, Path]:
    """Builds <shared_root>/.claude/worktrees/<name> and returns both paths."""
    shared_root = tmp_path / "skill-issue"
    worktree = shared_root / ".claude" / "worktrees" / "wf_test123"
    worktree.mkdir(parents=True)
    (shared_root / "README.md").write_text("shared checkout file\n")
    return shared_root, worktree


def test_worktree_escape_exact_observed_case_is_blocked(fake_worktree: tuple[Path, Path]) -> None:
    """The exact defect observed this session: `cd <shared> && python3 ...write`."""
    shared_root, worktree = fake_worktree
    command = f"cd {shared_root} && python3 -c \"open('escaped.txt','w').write('x')\""

    result = _run_hook(command, worktree)

    assert result.returncode == 2, (
        f"expected the worktree-escape guard to block (exit 2), got {result.returncode}:\n"
        f"stdout={result.stdout}\nstderr={result.stderr}"
    )
    assert str(worktree) in result.stderr, (
        f"block message should name the worktree path the agent should use instead:\n{result.stderr}"
    )
    assert not (shared_root / "escaped.txt").exists()


@pytest.mark.parametrize(
    "command_template",
    [
        "echo hi > {shared}/escaped.txt",
        "sed -i '' 's/a/b/' {shared}/README.md",
        "git -C {shared} commit -am escape",
        "pushd {shared} && ls",
        "tee {shared}/escaped.txt <<< hi",
    ],
)
def test_worktree_escape_variants_are_blocked(
    fake_worktree: tuple[Path, Path], command_template: str
) -> None:
    shared_root, worktree = fake_worktree
    command = command_template.format(shared=shared_root)

    result = _run_hook(command, worktree)

    assert result.returncode == 2, (
        f"expected command to be blocked: {command!r}\n"
        f"got rc={result.returncode} stdout={result.stdout} stderr={result.stderr}"
    )


@pytest.mark.parametrize(
    "command_template",
    [
        "cat {shared}/README.md",
        "ls {shared}",
        "grep -rn README {shared}",
        "git -C {shared} diff main",
        "git -C {shared} log --oneline -5",
        "git -C {shared} status",
    ],
)
def test_legitimate_reads_of_shared_checkout_still_pass(
    fake_worktree: tuple[Path, Path], command_template: str
) -> None:
    shared_root, worktree = fake_worktree
    command = command_template.format(shared=shared_root)

    result = _run_hook(command, worktree)

    assert result.returncode == 0, (
        f"expected read-only command to pass: {command!r}\n"
        f"got rc={result.returncode} stdout={result.stdout} stderr={result.stderr}"
    )


def test_absolute_path_into_own_worktree_still_passes(fake_worktree: tuple[Path, Path]) -> None:
    """Writing into your OWN worktree by absolute path (not the shared checkout)
    is not an escape and must not be blocked."""
    shared_root, worktree = fake_worktree
    command = f"echo hi > {worktree}/own-file.txt"

    result = _run_hook(command, worktree)

    assert result.returncode == 0, (
        f"absolute-path write into the agent's own worktree should pass:\n"
        f"got rc={result.returncode} stdout={result.stdout} stderr={result.stderr}"
    )


def test_guard_is_a_noop_outside_a_worktree(tmp_path: Path) -> None:
    """Same escape-shaped command run from a normal (non-worktree) checkout
    must not be affected by this guard — fail-open posture."""
    plain_checkout = tmp_path / "not-a-worktree"
    plain_checkout.mkdir()
    command = f"cd {plain_checkout} && ls"

    result = _run_hook(command, plain_checkout)

    assert result.returncode == 0, (
        f"guard should be a no-op outside a worktree:\n"
        f"got rc={result.returncode} stdout={result.stdout} stderr={result.stderr}"
    )
