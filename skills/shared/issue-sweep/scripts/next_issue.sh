#!/usr/bin/env bash
set -euo pipefail

default_skip_labels="${ISSUE_SWEEP_SKIP_LABELS:-blocked,wontfix,duplicate,needs-info,decision-needed}"
prefer_labels="${ISSUE_SWEEP_PREFER_LABELS:-}"
default_search="is:open sort:created-asc no:assignee"
IFS=',' read -r -a skip_label_parts <<<"$default_skip_labels"
for label in "${skip_label_parts[@]}"; do
  label="${label#"${label%%[![:space:]]*}"}"
  label="${label%"${label##*[![:space:]]}"}"
  if [[ -n "$label" ]]; then
    default_search+=" -label:\"$label\""
  fi
done
SEARCH="${1:-$default_search}"
LIMIT="${ISSUE_SWEEP_LIMIT:-50}"
SKIP_NUMBERS="${ISSUE_SWEEP_SKIP_NUMBERS:-}"

command -v gh >/dev/null
command -v git >/dev/null
command -v jq >/dev/null

issues_json="$(gh issue list \
  --state open \
  --search "$SEARCH" \
  --limit "$LIMIT" \
  --json number,title,labels,assignees,createdAt,url)"

count="$(jq 'length' <<<"$issues_json")"
if [[ "$count" -eq 0 ]]; then
  printf '{}\n'
  exit 0
fi

# Preferred labels jump the oldest-first queue: cheap-to-review issues land at
# the top of the maintainer's queue first. Order within each group is stable.
if [[ -n "$prefer_labels" ]]; then
  issues_json="$(jq --arg prefer "$prefer_labels" '
    ($prefer | split(",") | map(gsub("^\\s+|\\s+$"; "")) | map(select(length > 0))) as $p
    | map(. + {_prefer: ([.labels[].name] | any(. as $n | ($p | index($n)) != null))})
    | (map(select(._prefer)) + map(select(._prefer | not)))
    | map(del(._prefer))
  ' <<<"$issues_json")"
fi

# One remote-refs fetch for the whole candidate list: a pushed-but-unPRed
# branch for an issue means another run already owns it.
remote_heads="$(git ls-remote --heads origin 2>/dev/null || true)"

for number in $(jq -r '.[].number' <<<"$issues_json"); do
  if [[ " $SKIP_NUMBERS " == *" $number "* ]]; then
    continue
  fi

  # Any assignee means a human or another run is on it.
  if [[ "$(jq --argjson n "$number" '[.[] | select(.number == $n)][0].assignees | length' <<<"$issues_json")" -gt 0 ]]; then
    continue
  fi

  # Only OPEN PRs block an issue; a closed or rejected PR must not block it
  # forever.
  pr_json="$(gh pr list \
    --state open \
    --search "Closes #$number OR Fixes #$number" \
    --json number \
    --limit 20)"
  if [[ "$(jq 'length' <<<"$pr_json")" -gt 0 ]]; then
    continue
  fi

  if grep -qE "refs/heads/(fix/issue-$number(-|\$)|issue-sweep-$number-)" <<<"$remote_heads"; then
    continue
  fi

  jq --argjson n "$number" '.[] | select(.number == $n)' <<<"$issues_json"
  exit 0
done

printf '{}\n'
