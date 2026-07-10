#!/usr/bin/env bash
# PreToolUse hook for Edit/Write — guards sensitive config files.
#   1. Blocks all edits to ~/.claude/CLAUDE.md (edit manually if needed).
#   2. Blocks settings.json writes containing invalid fields (mcpServers etc).

set -euo pipefail

INPUT=$(cat)
FILE=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

GLOBAL_CLAUDE_MD="$HOME/.claude/CLAUDE.md"
if [[ "$FILE" == "$GLOBAL_CLAUDE_MD" ]]; then
  echo "BLOCKED: ~/.claude/CLAUDE.md is write-protected." >&2
  echo "Edit it manually if you really need to change it." >&2
  exit 2
fi

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
