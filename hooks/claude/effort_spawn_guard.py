#!/usr/bin/env python3
"""PreToolUse guard on Agent/Workflow: every spawn must name a custom agent type
so it carries an explicit effort level instead of inheriting the main thread's low.

Blocks Agent calls using built-in types (general-purpose/claude/Plan) or omitting
subagent_type, and Workflow scripts whose agent() calls never pass agentType.
Built-in Explore stays allowed (cheap low-effort lookups are its point).

Disable anytime with CLAUDE_EFFORT_GUARD_OFF=1.
"""
import json
import os
import sys

ALLOWED_BUILTINS = {"Explore", "claude-code-guide", "statusline-setup"}
BLOCKED_BUILTINS = {"general-purpose", "claude", "Plan"}
CUSTOM_TYPES = "worker / bulk / opus-worker / explore-mid"


def deny(reason: str) -> None:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }))
    sys.exit(0)


def main() -> None:
    if os.environ.get("CLAUDE_EFFORT_GUARD_OFF"):
        sys.exit(0)

    data = json.load(sys.stdin)
    tool = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}

    if tool == "Agent":
        subagent = tool_input.get("subagent_type", "")
        if subagent and subagent not in BLOCKED_BUILTINS:
            sys.exit(0)
        deny(
            f"Effort guard: '{subagent or '(none)'}' inherits the main thread's low effort. "
            f"Use a custom agent type instead: {CUSTOM_TYPES} "
            "(Explore is allowed for cheap lookups). Set CLAUDE_EFFORT_GUARD_OFF=1 to bypass."
        )

    if tool == "Workflow":
        script = tool_input.get("script", "")
        script_path = tool_input.get("scriptPath", "")
        if not script and script_path:
            try:
                with open(script_path) as f:
                    script = f.read()
            except OSError:
                sys.exit(0)
        if not script or "agent(" not in script or "agentType" in script:
            sys.exit(0)
        deny(
            "Effort guard: workflow script has agent() calls without agentType — they run at "
            f"low effort. Pass agentType: 'worker' (or {CUSTOM_TYPES}) on each agent() call. "
            "Set CLAUDE_EFFORT_GUARD_OFF=1 to bypass."
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
