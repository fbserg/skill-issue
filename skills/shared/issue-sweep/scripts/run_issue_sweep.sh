#!/usr/bin/env bash
set -euo pipefail

skill_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
agent="codex"
limit="10"
model=""
forever="0"
sleep_seconds="60"
parallel="3"
worktree_root="${ISSUE_SWEEP_WORKTREE_ROOT:-$HOME/.codex/worktrees/issue-sweep}"
claim_label="${ISSUE_SWEEP_CLAIM_LABEL:-assigned-to-me}"
assignee="${ISSUE_SWEEP_ASSIGNEE:-@me}"

usage() {
  cat <<'EOF'
usage: run_issue_sweep.sh [--agent codex|claude] [--limit N|--forever] [--parallel N] [--sleep SECONDS] [--model MODEL]

Fixes oldest eligible GitHub issues in isolated worktrees, then lands them.
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --agent)
      agent="${2:?missing --agent value}"
      shift 2
      ;;
    --limit)
      limit="${2:?missing --limit value}"
      shift 2
      ;;
    --model)
      model="${2:?missing --model value}"
      shift 2
      ;;
    --forever)
      forever="1"
      shift
      ;;
    --sleep)
      sleep_seconds="${2:?missing --sleep value}"
      shift 2
      ;;
    --parallel)
      parallel="${2:?missing --parallel value}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if ! [[ "$limit" =~ ^[0-9]+$ ]] || [[ "$limit" -lt 1 ]]; then
  echo "--limit must be a positive integer" >&2
  exit 2
fi

if ! [[ "$sleep_seconds" =~ ^[0-9]+$ ]]; then
  echo "--sleep must be a non-negative integer" >&2
  exit 2
fi

if ! [[ "$parallel" =~ ^[0-9]+$ ]] || [[ "$parallel" -lt 1 ]]; then
  echo "--parallel must be a positive integer" >&2
  exit 2
fi

case "$agent" in
  codex|claude) ;;
  *)
    echo "--agent must be codex or claude" >&2
    exit 2
    ;;
esac

command -v gh >/dev/null
command -v git >/dev/null
command -v jq >/dev/null
command -v "$agent" >/dev/null

gh auth status >/dev/null

if [[ -n "$(git status --short)" ]]; then
  echo "working tree is dirty; stop before automated issue sweep" >&2
  exit 1
fi

default_branch="$(gh repo view --json defaultBranchRef --jq .defaultBranchRef.name)"
git fetch origin "$default_branch" >/dev/null
mkdir -p "$worktree_root"

attempted=()
results=()

run_worker() {
  local issue="$1"
  local worktree="$2"
  local prompt
  prompt="$(cat <<EOF
Handle GitHub issue #$issue end-to-end without opening a PR.

You are one worker in an automated issue sweep. You are not alone in the
codebase; do not revert or overwrite changes made by others.

You are already inside an isolated git worktree. Fix only this issue. Run the
narrowest useful validation. Commit the fix on the current branch. Do not push,
do not open a PR, and do not close the issue; the orchestrator lands and closes.

Return only a concise result: issue number, commit hash, tests run, and any
blocker.
EOF
)"

  case "$agent" in
    codex)
      local cmd=(codex exec --ask-for-approval never --sandbox danger-full-access -C "$worktree")
      if [[ -n "$model" ]]; then
        cmd+=(--model "$model")
      fi
      cmd+=("$prompt")
      "${cmd[@]}"
      ;;
    claude)
      local cmd=(claude --print --permission-mode dontAsk)
      if [[ -n "$model" ]]; then
        cmd+=(--model "$model")
      fi
      cmd+=("$prompt")
      (cd "$worktree" && "${cmd[@]}")
      ;;
  esac
}

start_worker() {
  local issue="$1"
  local title="$2"
  local suffix branch worktree log

  suffix="$(openssl rand -hex 4)"
  branch="issue-sweep-$issue-$suffix"
  worktree="$worktree_root/$branch"
  log="$worktree/worker.log"

  git worktree add -b "$branch" "$worktree" "origin/$default_branch" >/dev/null
  echo "issue #$issue: $title" >"$log"
  run_worker "$issue" "$worktree" >>"$log" 2>&1 &
  worker_pid="$!"
  worker_issue="$issue"
  worker_branch="$branch"
  worker_worktree="$worktree"
  worker_log="$log"
}

land_worker_commit() {
  local issue="$1"
  local branch="$2"
  local worktree="$3"
  local log="$4"
  local base head validation commit

  base="$(git -C "$worktree" merge-base "origin/$default_branch" HEAD)"
  head="$(git -C "$worktree" rev-parse HEAD)"
  if [[ "$base" == "$head" ]]; then
    echo "#$issue produced no commit" >&2
    gh issue edit "$issue" --remove-label "$claim_label" >/dev/null || true
    return 1
  fi

  git fetch origin "$default_branch" >/dev/null
  git checkout "$default_branch" >/dev/null
  git pull --ff-only origin "$default_branch" >/dev/null

  if ! git cherry-pick "$base..$branch" >/dev/null; then
    git cherry-pick --abort >/dev/null || true
    echo "#$issue could not be landed cleanly; see $log" >&2
    gh issue edit "$issue" --remove-label "$claim_label" >/dev/null || true
    return 1
  fi

  git push origin "$default_branch" >/dev/null
  commit="$(git rev-parse --short HEAD)"
  validation="$(grep -Ei 'test|validation|pre-commit|lint|typecheck' "$log" | tail -5 | sed 's/^/- /' || true)"
  if [[ -z "$validation" ]]; then
    validation="- see worker log: $log"
  fi

  gh issue close "$issue" --comment "Fixed in $commit.

Validation:
$validation" >/dev/null
  git worktree remove "$worktree" --force >/dev/null || true
  git branch -D "$branch" >/dev/null 2>&1 || true
  results+=("#$issue landed $commit")
}

iteration=0
while [[ "$forever" == "1" || "$iteration" -lt "$limit" ]]; do
  batch_pids=()
  batch_issues=()
  batch_branches=()
  batch_worktrees=()
  batch_logs=()

  while [[ "${#batch_pids[@]}" -lt "$parallel" && ( "$forever" == "1" || "$iteration" -lt "$limit" ) ]]; do
    skip="${attempted[*]:-}"
    issue_json="$(ISSUE_SWEEP_SKIP_NUMBERS="$skip" "$skill_dir/scripts/next_issue.sh")"
    issue="$(jq -r '.number // empty' <<<"$issue_json")"

    if [[ -z "$issue" ]]; then
      break
    fi

    title="$(jq -r '.title // ""' <<<"$issue_json")"
    attempted+=("$issue")
    iteration=$((iteration + 1))
    if [[ "$forever" == "1" ]]; then
      echo "[forever:$iteration] claim issue #$issue: $title"
    else
      echo "[$iteration/$limit] claim issue #$issue: $title"
    fi
    "$skill_dir/scripts/claim_issue.sh" "$issue"

    start_worker "$issue" "$title"
    batch_pids+=("$worker_pid")
    batch_issues+=("$worker_issue")
    batch_branches+=("$worker_branch")
    batch_worktrees+=("$worker_worktree")
    batch_logs+=("$worker_log")
  done

  if [[ "${#batch_pids[@]}" -eq 0 ]]; then
    echo "No eligible issues remain."
    if [[ "$forever" == "1" ]]; then
      sleep "$sleep_seconds"
      continue
    fi
    break
  fi

  for index in "${!batch_pids[@]}"; do
    pid="${batch_pids[$index]}"
    issue="${batch_issues[$index]}"
    branch="${batch_branches[$index]}"
    worktree="${batch_worktrees[$index]}"
    log="${batch_logs[$index]}"

    if wait "$pid"; then
      cat "$log"
      if ! land_worker_commit "$issue" "$branch" "$worktree" "$log"; then
        results+=("#$issue failed landing; log $log")
        echo "Landing failed; stopping sweep." >&2
        break 2
      fi
    else
      status="$?"
      cat "$log" >&2 || true
      gh issue edit "$issue" --remove-label "$claim_label" >/dev/null || true
      gh issue edit "$issue" --remove-assignee "$assignee" >/dev/null || true
      git worktree remove "$worktree" --force >/dev/null || true
      git branch -D "$branch" >/dev/null 2>&1 || true
      results+=("#$issue worker failed exit=$status")
      echo "Worker failed; stopping sweep." >&2
      break 2
    fi
  done
done

echo
echo "Issue sweep summary:"
for result in "${results[@]}"; do
  echo "- $result"
done
