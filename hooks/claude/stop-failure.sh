#!/usr/bin/env bash
# StopFailure hook: fires when a turn ends due to an API error (rate_limit,
# overloaded, server_error, etc.) — output/exit code are ignored by the
# harness. Logs a durable trace so background-fleet sessions leave evidence
# of silent deaths instead of vanishing without one.
set -uo pipefail

LOG_DIR="$HOME/.claude/logs"
LOG_FILE="$LOG_DIR/stop-failures.jsonl"
mkdir -p "$LOG_DIR" 2>/dev/null || true

INPUT=$(cat 2>/dev/null || true)

if LINE=$(printf '%s' "$INPUT" | jq -c '. + {logged_at: (now | todate)}' 2>/dev/null); then
  printf '%s\n' "$LINE" >> "$LOG_FILE" 2>/dev/null || true
else
  printf '%s\n' "$INPUT" >> "$LOG_FILE" 2>/dev/null || true
fi

if [ -w /dev/tty ] 2>/dev/null; then
  { printf '\a' > /dev/tty; } 2>/dev/null || true
fi

exit 0
