#!/usr/bin/env bash
# PreToolUse hook for Edit/Write — blocks settings.json writes containing fields that do not belong there.
set -euo pipefail
INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')
[[ "$FILE" == *settings.json || "$FILE" == *settings.local.json ]] || exit 0
NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty')
if grep -q '"mcpServers"' <<<"$NEW_CONTENT"; then
  echo "BLOCKED: \"mcpServers\" is not a settings.json field. MCP servers live in ~/.claude.json (claude mcp add <name> -- <command>)." >&2
  exit 2
fi
if grep -q '"disabledSkills"' <<<"$NEW_CONTENT"; then
  echo "BLOCKED: \"disabledSkills\" is not a settings.json field. Use skillOverrides." >&2
  exit 2
fi
exit 0
