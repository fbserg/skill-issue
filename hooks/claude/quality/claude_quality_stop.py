#!/usr/bin/env python3
import shutil
import subprocess
from pathlib import Path

from claude_quality_lib import claude_stop_block, cwd_from_payload, disabled, file_hash, git_root, load_json, read_payload, state_file


def _ruff_still_fails(item: dict, root: Path) -> bool:
    """Re-run ruff on cited paths to confirm the failure is still live.

    Needed because the stored hash can equal the current file hash even after
    a fix (e.g. when ruff --fix modified the file in-place during the same batch
    that triggered the failure, so the post-batch hook recorded the post-fix hash
    alongside the pre-fix error output). Re-running ruff is the authoritative check.
    """
    paths = [p for p in item.get("paths", []) if p]
    if not paths or not shutil.which("ruff"):
        return True
    try:
        result = subprocess.run(
            ["ruff", "check", *paths],
            cwd=str(root),
            capture_output=True,
            timeout=30,
        )
        return result.returncode != 0
    except Exception:
        return True


def _still_relevant(item: dict) -> bool:
    """Drop entries whose cited files have changed (or vanished) since the failure was recorded.

    Catches the case where a failure gets fixed via a path that doesn't trigger the post-tool
    hook (git checkout/reset, merge conflict resolution, manual edits). If the file content
    differs from when the failure was recorded, we can't trust the cached error.
    """
    hashes = item.get("hashes") or {}
    root_s = item.get("root") or ""
    if not hashes or not root_s:
        return True
    root = Path(root_s)
    if not root.is_dir():
        return True
    if not all(file_hash(root / rel) == stored for rel, stored in hashes.items()):
        return False
    # Hash matches (file unchanged since failure recorded), but re-verify with the
    # linter to catch cases where the hash was captured post-fix in the same batch.
    summary = item.get("summary", "")
    if summary.startswith("ruff"):
        return _ruff_still_fails(item, root)
    return True


def main() -> int:
    payload = read_payload()
    if disabled():
        return 0
    # Loop guard (claude-code #55754): if this Stop event was itself triggered by a
    # previous Stop-hook block, let the agent stop — never block twice in a row.
    if payload.get("stop_hook_active"):
        return 0
    data = load_json(state_file(payload, "feedback"), {"formatted": [], "failures": []})
    items = data.get("failure_items") or []
    root = git_root(cwd_from_payload(payload))
    root_s = str(root) if root else ""
    if root_s:
        items = [item for item in items if item.get("root", "") in ("", root_s)]
    items = [item for item in items if _still_relevant(item)]
    failures = [item.get("summary", "") for item in items if item.get("summary")]
    if failures:
        claude_stop_block("Quality hook saw unresolved failures. Fix or explicitly validate before committing:\n\n" + "\n\n".join(failures[-3:]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
