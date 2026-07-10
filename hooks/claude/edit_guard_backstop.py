#!/usr/bin/env python3
"""Stop-event backstop for expensive_model_edit_guard.py.

The PreToolUse edit guard can silently stop firing (observed: client
bypassPermissions-mode regression made an entire session's 99 Edit/Write
calls invoke zero PreToolUse:Edit/Write hooks). This is an independent
detector that reads the same transcript after the fact and yells if the
hard cap was blown through with the guard never having run at all.

Fires only when BOTH are true:
  - direct (non-sidechain) Edit/Write/NotebookEdit calls > HARD_CAP
  - zero PreToolUse:Edit/Write(-family) hook executions recorded anywhere
    in the transcript

That second condition is the point: if the guard fired even once (e.g. a
warn-and-allow at edit #3), the primary hook is alive and this backstop
stays silent, even if edits blow past the cap afterward.

Fail-open: any exception exits 0 silently but is logged.
"""
import json
import os
import re
import sys
from pathlib import Path

EDIT_TOOLS = {"Edit", "Write", "NotebookEdit"}
HARD_CAP = 8
LOG_PATH = Path.home() / ".claude" / "logs" / "edit-guard-backstop.log"


def log(line: str) -> None:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LOG_PATH, "a") as fh:
        fh.write(line.rstrip("\n") + "\n")


def block(reason: str) -> None:
    print(json.dumps({"decision": "block", "reason": reason}))


def main() -> None:
    payload = json.load(sys.stdin)
    if payload.get("stop_hook_active"):
        return  # loop guard: never block twice on the same stop

    session_id = payload.get("session_id", "")
    if os.environ.get("EDIT_GUARD_OFF") == "1":
        return
    if session_id and Path(f"/tmp/edit-guard-off-{session_id}").exists():
        return
    if session_id and Path(f"/tmp/edit-guard-ran-{session_id}").exists():
        return  # primary guard is alive; transcript attachments undercount silent allows

    tpath = payload.get("transcript_path", "")
    if not tpath or not Path(tpath).exists():
        return

    model = ""
    edit_count = 0
    guard_hook_count = 0
    with open(tpath, "r", errors="replace") as fh:
        for line in fh:
            try:
                ev = json.loads(line)
            except ValueError:
                continue
            ev_type = ev.get("type")
            if ev_type == "assistant":
                side = bool(ev.get("isSidechain"))
                msg = ev.get("message") or {}
                if not side and msg.get("model"):
                    model = msg["model"]
                if side:
                    continue
                for b in msg.get("content") or []:
                    if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") in EDIT_TOOLS:
                        edit_count += 1
            elif ev_type == "attachment":
                a = ev.get("attachment") or {}
                hook_name = a.get("hookName", "")
                if hook_name.startswith("PreToolUse:") and ("Edit" in hook_name or "Write" in hook_name):
                    guard_hook_count += 1

    if not re.search(r"fable|opus", model, re.I):
        return
    if edit_count <= HARD_CAP or guard_hook_count > 0:
        return

    log(f"{__import__('datetime').datetime.now().isoformat()} session={session_id} edits={edit_count} guard_hook_count={guard_hook_count}")
    block(
        f"BACKSTOP: edit-guard never ran this session ({edit_count} direct edits, "
        "0 PreToolUse:Edit/Write hook executions recorded) — the primary "
        "expensive_model_edit_guard.py enforcement channel is dead (check for a "
        "bypassPermissions-mode regression or hook wiring break). Main thread should "
        "have been delegating implementation to a Sonnet subagent or worktree agent. "
        "Investigate why PreToolUse hooks aren't firing before continuing to edit directly."
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        try:
            log(f"{__import__('datetime').datetime.now().isoformat()} EXCEPTION {exc!r}")
        except Exception:
            pass
    sys.exit(0)
