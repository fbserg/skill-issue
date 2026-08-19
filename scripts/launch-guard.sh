#!/usr/bin/env bash
# launch-guard.sh — refuse a live CLI-agent launch with the same cwd/prompt key.
#
# This prevents a measured failure where byte-identical Codex prompts launched
# 16 minutes apart in one checkout and both completed, wasting about $14 and
# risking concurrent writes. Usage:
#   launch-guard.sh [--force] [--window-min N] [--prompt-file F | --prompt "text"] -- <command> [args...]
# Without an explicit prompt option, the command's last positional argument is
# the prompt (matching `codex exec ... "PROMPT"` and `claude -p "PROMPT"`).
# Exit codes: 0 = the command's own exit via exec; 2 = usage error;
# 3 = live duplicate refused.
#
# The entry records this shell's pid, then exec replaces it with the command so
# no wrapper remains. Consequently an exit trap cannot clean up the entry;
# every invocation instead prunes entries whose pid is dead or age exceeds 24h.
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: launch-guard.sh [--force] [--window-min N] [--prompt-file F | --prompt "text"] -- <command> [args...]

If --prompt or --prompt-file is omitted, the command's last positional
argument is used as the prompt.
EOF
}

read_entry_metadata() {
  python3 -c 'import json, sys
with open(sys.argv[1], encoding="utf-8") as handle:
    entry = json.load(handle)
print(entry["pid"], entry["started_epoch"])' "$1"
}

force=false
window_min=30
prompt_source=""
prompt=""
prompt_file=""
separator_found=false

while (($# > 0)); do
  case "$1" in
    --force)
      force=true
      shift
      ;;
    --window-min)
      if (($# < 2)); then
        usage >&2
        exit 2
      fi
      window_min="$2"
      shift 2
      ;;
    --prompt)
      if (($# < 2)) || [[ -n "$prompt_source" ]]; then
        usage >&2
        exit 2
      fi
      prompt_source="argument"
      prompt="$2"
      shift 2
      ;;
    --prompt-file)
      if (($# < 2)) || [[ -n "$prompt_source" ]]; then
        usage >&2
        exit 2
      fi
      prompt_source="file"
      prompt_file="$2"
      shift 2
      ;;
    --help)
      usage
      exit 0
      ;;
    --)
      separator_found=true
      shift
      break
      ;;
    *)
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$separator_found" != true ]] || (($# == 0)); then
  usage >&2
  exit 2
fi

if [[ ! "$window_min" =~ ^[0-9]+$ ]]; then
  usage >&2
  exit 2
fi

if [[ "$prompt_source" == "file" ]]; then
  if [[ ! -f "$prompt_file" || ! -r "$prompt_file" ]]; then
    printf 'launch-guard: cannot read prompt file: %s\n' "$prompt_file" >&2
    exit 2
  fi
  prompt="$(<"$prompt_file")"
elif [[ -z "$prompt_source" ]]; then
  prompt="${!#}"
fi

prompt_head="$(python3 -c 'import sys; print(" ".join(sys.argv[1].split())[:200], end="")' "$prompt")"
key="$(python3 -c 'import hashlib, sys; print(hashlib.sha256((sys.argv[1] + "\n" + sys.argv[2]).encode()).hexdigest())' "$PWD" "$prompt_head")"

state_dir="${LAUNCH_GUARD_DIR:-$HOME/.claude/launch-guard}"
mkdir -p "$state_dir"
now_epoch="$(date +%s)"

shopt -s nullglob
for entry_file in "$state_dir"/*.json; do
  if ! metadata="$(read_entry_metadata "$entry_file" 2>/dev/null)"; then
    rm -f "$entry_file"
    continue
  fi
  read -r entry_pid entry_started <<<"$metadata"
  if [[ ! "$entry_pid" =~ ^[1-9][0-9]*$ || ! "$entry_started" =~ ^[0-9]+$ ]]; then
    rm -f "$entry_file"
    continue
  fi
  entry_age=$((now_epoch - entry_started))
  if ((entry_age > 86400)) || ! kill -0 "$entry_pid" 2>/dev/null; then
    rm -f "$entry_file"
  fi
done
shopt -u nullglob

entry_path="$state_dir/$key.json"
started_epoch="$(date +%s)"
temporary_entry="$(mktemp "$state_dir/.${key}.XXXXXX")"
if ! python3 -c 'import json, sys
entry = {
    "pid": int(sys.argv[1]),
    "cwd": sys.argv[2],
    "prompt_head": sys.argv[3],
    "started_epoch": int(sys.argv[4]),
    "argv0": sys.argv[5],
}
json.dump(entry, sys.stdout)
print()' "$$" "$PWD" "$prompt_head" "$started_epoch" "$1" >"$temporary_entry"; then
  rm -f "$temporary_entry"
  exit 1
fi

# Claim the key atomically: ln(2) fails with EEXIST when another launch already
# holds it, so two simultaneous launches cannot both pass a check-then-write
# (review reproduced exactly that race with the earlier `[[ -f ]]` + `mv -f`).
claim_entry() {
  ln "$temporary_entry" "$entry_path" 2>/dev/null
}

refuse_or_force() {
  local existing_pid="$1" age_minutes="$2"
  if [[ "$force" == true ]]; then
    printf 'launch-guard: warning: --force overriding a live launch (pid %s, started %s min ago) with the same prompt.\n' \
      "$existing_pid" "$age_minutes" >&2
    mv -f "$temporary_entry" "$entry_path"
    return 0
  fi
  printf 'launch-guard: a live launch (pid %s, started %s min ago) in this cwd began with the same prompt. Refusing. Re-run with --force to launch anyway, or attach/inspect that run.\n' \
    "$existing_pid" "$age_minutes" >&2
  rm -f "$temporary_entry"
  exit 3
}

if ! claim_entry; then
  metadata="$(read_entry_metadata "$entry_path")"
  read -r existing_pid existing_started <<<"$metadata"
  age_seconds=$((now_epoch - existing_started))
  if ((age_seconds < 0)); then
    age_seconds=0
  fi
  age_minutes=$((age_seconds / 60))
  window_seconds=$((window_min * 60))
  if ((age_seconds <= window_seconds)) && kill -0 "$existing_pid" 2>/dev/null; then
    refuse_or_force "$existing_pid" "$age_minutes"
  else
    # Stale (dead pid or outside the window): drop it and claim once more; if a
    # rival claimed in between, that rival is the live launch — refuse.
    rm -f "$entry_path"
    if ! claim_entry; then
      metadata="$(read_entry_metadata "$entry_path")"
      read -r existing_pid existing_started <<<"$metadata"
      refuse_or_force "$existing_pid" "$(( (now_epoch - existing_started) / 60 ))"
    fi
  fi
fi
rm -f "$temporary_entry"

exec "$@"
