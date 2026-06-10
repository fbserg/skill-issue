#!/usr/bin/env python3
"""PreToolUse guard: expensive models (Fable/Opus) orchestrate, they don't implement.

Warns (deny once) at 3 direct Edit/Write/NotebookEdit calls in a session,
hard-denies at 8+. Sonnet/Haiku sessions and subagent (sidechain) calls pass.
Override: EDIT_GUARD_OFF=1 or touch /tmp/edit-guard-off-<session_id>.
Fail-open on any error.
"""
import json
import os
import re
import sys
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}
EXEMPT_SUFFIXES = (".md", ".txt")
WARN_AT = 3
HARD_CAP = 8


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def is_exempt_path(raw: str) -> bool:
    if not raw:
        return True
    p = raw.lower()
    if p.endswith(EXEMPT_SUFFIXES):
        return True
    if "/.claude/" in p or p.startswith(str(Path.home() / ".claude").lower()):
        return True
    name = Path(p).name
    if name == "justfile":
        return True
    if name.endswith((".toml", ".json", ".yaml", ".yml")):
        # treat as config exemption only when not nested under src/lib-ish source trees
        parts = Path(raw).parts
        if not any(s in parts for s in ("src", "lib", "app")):
            return True
    return False


def main() -> None:
    data = json.load(sys.stdin)
    session_id = data.get("session_id", "")
    if os.environ.get("EDIT_GUARD_OFF") == "1":
        return
    if session_id and Path(f"/tmp/edit-guard-off-{session_id}").exists():
        return

    tpath = data.get("transcript_path", "")
    if not tpath or not Path(tpath).exists():
        return

    file_path = (data.get("tool_input") or {}).get("file_path") or (
        data.get("tool_input") or {}).get("notebook_path") or ""
    if is_exempt_path(file_path):
        return

    model = ""
    edit_count = 0
    last_sidechain = False
    with open(tpath, "r", errors="replace") as fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            side = bool(ev.get("isSidechain"))
            if ev.get("type") == "assistant":
                msg = ev.get("message") or {}
                if not side and msg.get("model"):
                    model = msg["model"]
                for block in msg.get("content") or []:
                    if (isinstance(block, dict) and block.get("type") == "tool_use"
                            and block.get("name") in EDIT_TOOLS):
                        last_sidechain = side
                        if not side:
                            edit_count += 1

    if not re.search(r"fable|opus", model, re.I):
        return
    if last_sidechain:
        # this call most likely belongs to a subagent transcript stream
        return

    if edit_count >= HARD_CAP:
        deny(
            f"{edit_count} direct edits this session on an expensive model ({model}). "
            "Main thread is orchestrator-only: dispatch a Sonnet subagent "
            "(Agent tool, model:'sonnet') or a worktree agent to do the implementation, "
            "then review its result. Say 'edit guard off' to lift "
            f"(touch /tmp/edit-guard-off-{session_id})."
        )
    if edit_count == WARN_AT:
        marker = Path(f"/tmp/edit-guard-warned-{session_id}")
        if not marker.exists():
            marker.touch()
            deny(
                "3 direct edits this session on an expensive model — delegate remaining "
                "implementation to a Sonnet subagent (Agent tool, model:'sonnet') or a "
                "worktree agent. Re-attempt if this specific edit is genuinely trivial."
            )


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
