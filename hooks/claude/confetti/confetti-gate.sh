#!/bin/bash
# Stop hook: fire Raycast confetti once after a successful deploy/push.
#
# Usage: your deploy script touches ~/.claude/.confetti-pending on success.
# This hook clears the marker and triggers the confetti animation.
#
# Requirements: macOS + Raycast installed (raycast:// URL scheme).
# Safe no-op on Linux or without Raycast — the marker just sits there.
[ -f "$HOME/.claude/.confetti-pending" ] || exit 0
open -g "raycast://confetti" && rm -f "$HOME/.claude/.confetti-pending"
exit 0
