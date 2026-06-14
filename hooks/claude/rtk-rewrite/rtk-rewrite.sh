#!/usr/bin/env bash
# PreToolUse (Bash) hook: transparently rewrite verbose commands through `rtk`
# (Rust Token Killer) to compress their output before it hits the model's context.
#
# rtk decides which commands are worth rewriting (find/ps/npm/cargo/wc/test runners
# and friends). Plain commands it doesn't know how to compress are passed through
# untouched. Output-heavy rewrites are also auto-allowed so they don't trip a
# permission prompt for a command the user already approved in its raw form.
#
# Requires: rtk on PATH (`brew install rtk`) and jq. If rtk is missing the hook
# is a no-op, so it's safe to wire up before installing rtk.
set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[[ -z "$COMMAND" ]] && exit 0

# rtk find doesn't support compound predicates — pass those through untouched
if echo "$COMMAND" | grep -qE '\bfind\b' && echo "$COMMAND" | grep -qE '\-not\b|\-exec\b| -o | -a |\-prune\b'; then
  exit 0
fi

if ! command -v rtk &>/dev/null; then
  exit 0
fi

set +e
REWRITTEN=$(rtk rewrite "$COMMAND" 2>/dev/null)
EXIT_CODE=$?
set -e

# rtk rewrite exit codes:
#   0 = rewrite available (no-op if identical to input)
#   1/2 = nothing to do / error → pass through untouched
#   3 = rewrite available, but do NOT auto-allow (just substitute the command)
case $EXIT_CODE in
  0)
    [ "$COMMAND" = "$REWRITTEN" ] && exit 0
    ;;
  1|2)
    exit 0
    ;;
  3)
    ;;
  *)
    exit 0
    ;;
esac

ORIGINAL_INPUT=$(echo "$INPUT" | jq -c '.tool_input')
UPDATED_INPUT=$(echo "$ORIGINAL_INPUT" | jq --arg cmd "$REWRITTEN" '.command = $cmd')

if [ "$EXIT_CODE" -eq 3 ]; then
  jq -n \
    --argjson updated "$UPDATED_INPUT" \
    '{
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "updatedInput": $updated
      }
    }'
else
  jq -n \
    --argjson updated "$UPDATED_INPUT" \
    '{
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "RTK auto-rewrite",
        "updatedInput": $updated
      }
    }'
fi
