#!/usr/bin/env python3
from claude_quality_lib import disabled, read_payload, record_pre


def main() -> int:
    payload = read_payload()
    if disabled():
        return 0
    tool = payload.get("tool_name") or ""
    if tool == "Bash":
        record_pre(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
