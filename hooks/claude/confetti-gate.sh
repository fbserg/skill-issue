#!/bin/bash
# Stop hook: fire Raycast confetti once after a successful `just push-main`.
# push-main touches ~/.claude/.confetti-pending on success; this clears it and celebrates.
[ -f "$HOME/.claude/.confetti-pending" ] || exit 0
open -g "raycast://confetti" && rm -f "$HOME/.claude/.confetti-pending"
exit 0
