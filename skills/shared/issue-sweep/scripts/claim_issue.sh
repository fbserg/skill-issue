#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: claim_issue.sh <issue-number>" >&2
  exit 2
fi

issue="$1"
assignee="${ISSUE_SWEEP_ASSIGNEE:-@me}"

command -v gh >/dev/null

# The assignee IS the claim. No label, no comment: issue selection skips
# assigned issues, and the eventual PR's Closes line is the only notification
# the maintainer needs.
gh issue edit "$issue" --add-assignee "$assignee" >/dev/null
printf 'assigned #%s to %s\n' "$issue" "$assignee"
