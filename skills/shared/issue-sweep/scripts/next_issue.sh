#!/usr/bin/env bash
set -euo pipefail

default_skip_labels="${ISSUE_SWEEP_SKIP_LABELS:-blocked,wontfix,duplicate,needs-info,decision-needed,assigned-to-me}"
default_search="is:open sort:created-asc"
IFS=',' read -r -a skip_label_parts <<<"$default_skip_labels"
for label in "${skip_label_parts[@]}"; do
  label="${label#"${label%%[![:space:]]*}"}"
  label="${label%"${label##*[![:space:]]}"}"
  if [[ -n "$label" ]]; then
    default_search+=" -label:$label"
  fi
done
SEARCH="${1:-$default_search}"
LIMIT="${ISSUE_SWEEP_LIMIT:-50}"
SKIP_NUMBERS="${ISSUE_SWEEP_SKIP_NUMBERS:-}"

command -v gh >/dev/null
command -v jq >/dev/null

issues_json="$(gh issue list \
  --state open \
  --search "$SEARCH" \
  --limit "$LIMIT" \
  --json number,title,labels,createdAt,url)"

count="$(jq 'length' <<<"$issues_json")"
if [[ "$count" -eq 0 ]]; then
  printf '{}\n'
  exit 0
fi

for number in $(jq -r '.[].number' <<<"$issues_json"); do
  if [[ " $SKIP_NUMBERS " == *" $number "* ]]; then
    continue
  fi

  pr_json="$(gh pr list \
    --state all \
    --search "Closes #$number OR Fixes #$number OR issue-$number" \
    --json number,state,title,url,headRefName \
    --limit 20)"

  if [[ "$(jq 'length' <<<"$pr_json")" -gt 0 ]]; then
    continue
  fi

  jq --argjson n "$number" '.[] | select(.number == $n)' <<<"$issues_json"
  exit 0
done

printf '{}\n'
