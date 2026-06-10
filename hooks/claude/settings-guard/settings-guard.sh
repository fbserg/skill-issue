#!/usr/bin/env bash
# PreToolUse hook for Edit/Write — guards Claude Code settings files.
#
# Blocks writes to settings.json / settings.local.json that contain fields
# that don't belong there and will be silently ignored or cause confusion:
#
#   mcpServers  — lives in ~/.claude.json, not settings.json
#   disabledSkills — not a real field; skills use skillOverrides

set -euo pipefail

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only care about settings.json / settings.local.json
if [[ "$FILE" != *settings.json && "$FILE" != *settings.local.json ]]; then
  exit 0
fi

# Grab whichever content field this tool uses (Edit uses new_string, Write uses content)
NEW_CONTENT=$(echo "$INPUT" | jq -r '.tool_input.new_string // .tool_input.content // empty')

if [[ -z "$NEW_CONTENT" ]]; then
  exit 0
fi

# Fields that do NOT belong in settings.json
BANNED_FIELDS=("mcpServers" "disabledSkills")

for field in "${BANNED_FIELDS[@]}"; do
  if echo "$NEW_CONTENT" | grep -q "\"$field\""; then
    echo "BLOCKED: \"$field\" is not a valid settings.json field." >&2
    echo "" >&2
    case "$field" in
      mcpServers)
        echo "MCP servers live in ~/.claude.json, not settings.json." >&2
        echo "Add them with: claude mcp add <name> -- <command> [args...]" >&2
        echo "Or edit ~/.claude.json directly under the \"mcpServers\" key." >&2
        ;;
      disabledSkills)
        echo "Skills are managed via skillOverrides in settings.json, not disabledSkills." >&2
        ;;
    esac
    # Exit 2 = block the tool call
    exit 2
  fi
done

exit 0
