"""check-install.py's hook guard-marker parity check.

hooks/claude/*.sh in this repo is a mirror only — scripts/install.sh does not
install it (see hooks/claude/README.md). The harness actually executes
whatever ~/.claude/hooks (normally a symlink into a separate `etc` checkout)
points at. PR #23 added a worktree-escape guard to the mirror only, so the
harness never ran it. This reproduces that failure mode and proves
check-install.py now catches it.

Run with: python3 -m pytest tests/test_check_install_hook_guard_parity.py -v
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check-install.py"
SPEC = importlib.util.spec_from_file_location("check_install", MODULE_PATH)
assert SPEC and SPEC.loader
CHECK_INSTALL = importlib.util.module_from_spec(SPEC)
sys.argv = ["check-install.py"]
try:
    SPEC.loader.exec_module(CHECK_INSTALL)
except SystemExit:
    pass


def _fake_live_hooks_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, pretool_bash_content: str) -> Path:
    """Points ~/.claude/hooks (under a throwaway HOME) at a fake live hooks
    dir containing a fake pretool-bash.sh, mimicking the real ~/.claude/hooks
    -> etc/configs/claude/hooks symlink without touching the real one."""
    live_dir = tmp_path / "fake-etc-hooks"
    live_dir.mkdir()
    (live_dir / "pretool-bash.sh").write_text(pretool_bash_content)

    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    (home / ".claude" / "hooks").symlink_to(live_dir, target_is_directory=True)
    monkeypatch.setenv("HOME", str(home))
    return live_dir


def test_reproduces_pr_23_defect_mirror_guard_missing_from_live_hook_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The exact PR #23 defect: mirror has the worktree-escape guard's
    _RE markers, the live hook doesn't (it's a plain script with none)."""
    _fake_live_hooks_dir(tmp_path, monkeypatch, "#!/usr/bin/env bash\necho no guards ported here\n")

    with pytest.raises(SystemExit) as exc_info:
        CHECK_INSTALL.check_hook_guard_marker_parity()
    assert exc_info.value.code == 1


def test_passes_when_live_hook_has_every_mirror_guard_marker(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A live hook that has been ported (here: byte-identical, which
    trivially has every marker) must not be flagged."""
    mirror_file = CHECK_INSTALL.REPO_ROOT / "hooks" / "claude" / "pretool-bash.sh"
    _fake_live_hooks_dir(tmp_path, monkeypatch, mirror_file.read_text())

    CHECK_INSTALL.check_hook_guard_marker_parity()  # must not raise


def test_passes_when_live_hook_has_diverged_structure_but_keeps_all_markers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Not byte-parity: a live hook with extra unrelated content (its own
    PHASE 1.5 block, say) still passes as long as every mirror guard marker
    name is present somewhere in it."""
    mirror_file = CHECK_INSTALL.REPO_ROOT / "hooks" / "claude" / "pretool-bash.sh"
    diverged = (
        "#!/usr/bin/env bash\n"
        "# PHASE 1.5: some live-only guard the mirror has never heard of\n"
        "echo live-only-feature\n"
        + mirror_file.read_text()
    )
    _fake_live_hooks_dir(tmp_path, monkeypatch, diverged)

    CHECK_INSTALL.check_hook_guard_marker_parity()  # must not raise


def test_skips_when_hooks_are_not_installed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """scripts/install.sh does not install hooks — a checkout with no
    ~/.claude/hooks symlink at all must not be treated as a failure."""
    home = tmp_path / "home-no-hooks"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    CHECK_INSTALL.check_hook_guard_marker_parity()  # must not raise
