#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  echo "usage: claim_issue.sh <issue-number>" >&2
  exit 2
fi

issue="$1"
label="${ISSUE_SWEEP_CLAIM_LABEL:-assigned-to-me}"
assignee="${ISSUE_SWEEP_ASSIGNEE:-@me}"

command -v gh >/dev/null

if ! gh label list --limit 200 --json name --jq '.[].name' | grep -Fxq "$label"; then
  gh label create "$label" --color "7357ff" --description "Assigned to me" >/dev/null
fi

gh issue edit "$issue" --add-label "$label" --add-assignee "$assignee" >/dev/null
printf 'assigned #%s to %s with label %s\n' "$issue" "$assignee" "$label"
