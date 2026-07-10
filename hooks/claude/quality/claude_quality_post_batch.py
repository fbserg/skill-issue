#!/usr/bin/env python3
"""PostToolBatch: drain touched paths staged by PostToolUse, run formatters once,
record feedback, and surface a single batch-level context message.

This is where the actual format/lint work happens — once per batch instead of once
per edit, which keeps system-reminder pressure off the context window."""
from claude_quality_lib import (
    claude_batch_context,
    cwd_from_payload,
    disabled,
    drain_staged,
    format_touched,
    git_root,
    load_json,
    read_payload,
    record_feedback,
    state_file,
)


def main() -> int:
    payload = read_payload()
    if disabled():
        return 0
    root = git_root(cwd_from_payload(payload))
    if not root:
        return 0

    touched = drain_staged(payload, root)
    formatted: list[str] = []
    if touched:
        formatted, failures = format_touched(root, touched)
        record_feedback(payload, formatted, failures, touched)

    data = load_json(state_file(payload, "feedback"), {})
    items = data.get("failure_items") or []
    root_s = str(root)
    items = [item for item in items if item.get("root", "") in ("", root_s)]
    failures_msg = [item.get("summary", "") for item in items] or (data.get("failures") or [])

    if failures_msg:
        claude_batch_context("Quality hook failures remain:\n\n" + "\n\n".join(failures_msg[-3:]))
    elif formatted:
        claude_batch_context("Quality hook formatted touched files: " + ", ".join(formatted[:12]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
