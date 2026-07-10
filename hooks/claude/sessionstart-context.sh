#!/bin/bash
[ -z "${CLAUDE_PROJECT_DIR:-}" ] && exit 0
BRANCH=$(git -C "$CLAUDE_PROJECT_DIR" branch --show-current 2>/dev/null)
COMMITS=$(git -C "$CLAUDE_PROJECT_DIR" log --oneline -5 2>/dev/null)
CONTEXT="Branch: ${BRANCH}
Recent commits:
${COMMITS}"

python3 -c "
import json, sys
print(json.dumps({'hookSpecificOutput':{'hookEventName':'SessionStart','additionalContext':sys.argv[1]}}))
" "$CONTEXT"
