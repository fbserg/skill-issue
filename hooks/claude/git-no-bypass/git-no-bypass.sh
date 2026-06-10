#!/usr/bin/env bash
# PreToolUse hook: block git hook-bypass flags.
#
# Prevents the agent from silently skipping pre-commit/pre-push hooks via:
#   git commit --no-verify / -n
#   git push --no-verify
#   git -c core.hooksPath=... (override the hooks directory)
#
# If a hook is failing, fix the failure — don't paper over it.
# The user can still bypass deliberately by running the git command directly
# in their terminal (outside Claude Code).

input=$(cat)
GUARD_INPUT="$input" python3 - <<'PY'
import json
import os
import re
import sys

try:
    data = json.loads(os.environ.get("GUARD_INPUT", ""))
except Exception:
    sys.exit(0)

cmd = (data.get("tool_input") or {}).get("command", "") or ""
if not cmd:
    sys.exit(0)


def block(*lines):
    for line in lines:
        print(line, file=sys.stderr)
    sys.exit(2)


# Block core.hooksPath overrides
if re.search(
    r"(^|[;&|\s])git\s+("
    r"-c\s+core\.hooksPath="
    r"|.*\s-c\s+core\.hooksPath="
    r"|--config-env[= ]core\.hooksPath"
    r"|.*\s--config-env[= ]core\.hooksPath"
    r")",
    cmd,
    re.S,
):
    block(
        "BLOCKED: git core.hooksPath override bypasses project hooks.",
        "Git hooks exist for a reason; fix the failure or ask the user to bypass deliberately.",
    )

# Block git commit --no-verify / -n
if re.search(r"(^|[;&|\s])git\s+commit(\s.*)?(\s--no-verify|\s-n)(\s|$)", cmd, re.S):
    block(
        "BLOCKED: git commit --no-verify skips pre-commit hooks.",
        "Git hooks exist for a reason; fix the failure or ask the user to bypass deliberately.",
    )

# Block git push --no-verify
if re.search(r"(^|[;&|\s])git\s+push(\s.*)?\s--no-verify(\s|$)", cmd, re.S):
    block(
        "BLOCKED: git push --no-verify skips pre-push hooks.",
        "Git hooks exist for a reason; fix the failure or ask the user to bypass deliberately.",
    )
PY
