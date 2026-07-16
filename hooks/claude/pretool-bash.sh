#!/usr/bin/env bash
# Consolidated PreToolUse hook for Bash commands.
# Runs three checks sequentially so only one JSON output path exists:
#   1. Block catastrophic/destructive commands (exit 2 = block)
#   2. Filter verbose test output to failures only (rewrite)
#   3. RTK token-saving rewrite (rewrite + auto-allow)
set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# ============================================================
# PHASE 0: Pre-push gate (tsc + vite build + vitest)
# ============================================================

if { [[ -z "${SKIP_PREPUSH_GATE:-}" ]] && ! grep -q 'SKIP_PREPUSH_GATE=1' <<<"$COMMAND"; } \
   && grep -Eq '(^|[;&|[:space:]])git[[:space:]]+push(\b|$)' <<<"$COMMAND" \
   && ! grep -Eq 'git[[:space:]]+push[[:space:]]+(-h\b|--help\b|--dry-run\b)' <<<"$COMMAND"; then
  _proj="${CLAUDE_PROJECT_DIR:-$PWD}"
  _has_tsconfig() { [[ -f "$_proj/tsconfig.json" ]]; }
  # Cache all dep names from package.json in one jq call (newline-separated)
  if [[ -f "$_proj/package.json" ]]; then
    _pkg_deps=$(jq -r '((.dependencies // {}) + (.devDependencies // {})) | keys[]' "$_proj/package.json" 2>/dev/null || true)
  else
    _pkg_deps=""
  fi
  _has_dep() { [[ -n "$_pkg_deps" ]] && printf '%s\n' "$_pkg_deps" | grep -qxF "$1"; }

  # Fail fast if deps look required but node_modules is missing/broken —
  # don't let tsc/vite/vitest spew hundreds of "module not found" errors.
  _deps_broken=0
  if [[ -n "$_pkg_deps" ]]; then
    if [[ ! -d "$_proj/node_modules" ]] && (_has_dep typescript || _has_dep vite || _has_dep vitest); then
      _deps_broken=1
    elif [[ -d "$_proj/node_modules" ]] && _has_dep typescript && ! (cd "$_proj" && npx --no-install tsc --version) >/dev/null 2>&1; then
      _deps_broken=1
    fi
  fi
  if (( _deps_broken )); then
    echo "BLOCKED: node_modules missing in $_proj — run npm install first (or SKIP_PREPUSH_GATE=1)." >&2
    exit 2
  fi

  _run_step() {
    local label="$1"; shift
    echo ">>> pre-push gate: $label (120s timeout, SKIP_PREPUSH_GATE=1 to bypass)" >&2
    local rc=0
    local logf
    logf=$(mktemp /tmp/prepush-gate-XXXXXX)
    (cd "$_proj" && timeout 120 "$@") >"$logf" 2>&1 || rc=$?
    if (( rc != 0 )); then
      local total_lines
      total_lines=$(wc -l <"$logf" | tr -d ' ')
      local tail_lines=30
      if (( total_lines > tail_lines )); then
        echo "… $(( total_lines - tail_lines )) earlier lines suppressed, full log: $logf" >&2
        tail -n "$tail_lines" "$logf" >&2
      else
        cat "$logf" >&2
      fi
      echo "" >&2
      if (( rc == 124 )); then
        echo "BLOCKED: '$label' timed out after 120s — fix or rerun with SKIP_PREPUSH_GATE=1." >&2
      else
        echo "BLOCKED: '$label' failed (exit $rc) — fix before pushing, or rerun with SKIP_PREPUSH_GATE=1." >&2
      fi
      exit 2
    fi
    rm -f "$logf"
  }

  _ran=0
  if _has_tsconfig && _has_dep typescript && ! _has_dep astro; then
    _run_step "tsc -b" npx --no-install tsc -b; _ran=1
  fi
  if _has_dep vite && ! _has_dep astro; then
    _run_step "vite build" npx --no-install vite build; _ran=1
  fi
  if _has_dep vitest; then
    _run_step "vitest run" npx --no-install vitest run; _ran=1
  fi
  (( _ran )) && echo "✓ pre-push gate passed" >&2
fi

# ============================================================
# PHASE 1: Block catastrophic commands
# ============================================================

# git stash safety gate: block bare stash when working tree is dirty
if echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])git[[:space:]]+stash\b' && ! echo "$COMMAND" | grep -qE '(--keep-index|-p|--patch|-k|pop|apply|list|show|drop|branch)'; then
  UNSTAGED_COUNT=$(git -C "${CLAUDE_PROJECT_DIR:-$PWD}" status --porcelain 2>/dev/null | wc -l)
  if (( UNSTAGED_COUNT > 10 )); then
    echo "BLOCKED: working tree has $UNSTAGED_COUNT unstaged changes — \`git stash\` will sweep them all in. Stage only your files, then \`git stash --keep-index\`. Or \`git diff <files> > /tmp/patch && git checkout -- <files>\` for surgical set-aside." >&2
    exit 2
  fi
fi

# Projects dir is backed up — allow rm freely within it
if echo "$COMMAND" | grep -qE '^rm\b' && echo "$COMMAND" | grep -qE '/Users/serg/projects/' && ! echo "$COMMAND" | grep -qE '/Users/serg/projects/\.\.' ; then
  exit 0
fi

# gstack skills dir — allow destructive git commands for upgrades
if echo "$COMMAND" | grep -qE '(git reset --hard|git stash)' && echo "$COMMAND" | grep -qE '(\.claude/skills|\.gstack)'; then
  exit 0
fi
# Also allow when cd'd into skills dir mid-command
if echo "$COMMAND" | grep -qE 'cd.*\.claude/skills.*&&.*git (reset --hard|stash)'; then
  exit 0
fi

# shellcheck disable=SC2016  # literal $HOME etc. are intended in the regex
BLOCKED_RE='rm -rf (/|~|\$HOME|/Users|/System|/Library|/Applications|\.\s*$|\*\s*$|\./\s*$)|git push (--force|-f).*(main|master)|git reset --hard|DROP (TABLE|DATABASE)|truncate table|chmod -R 777 /|mkfs\.|dd if=.* of=/dev/|> /dev/sda|launchctl unload.*com\.apple|networksetup.*-setdnsservers|defaults delete |pkill -9 -u|killall Finder && killall Dock'

if echo "$COMMAND" | grep -qiE "$BLOCKED_RE"; then
  echo "BLOCKED: Destructive command detected." >&2
  echo "If you really need this, ask the user to run it manually with ! prefix." >&2
  exit 2
fi

if echo "$COMMAND" | grep -qE '(^|\s)/etc/\S|.*/System/|/Library/Launch(Daemons|Agents)' && ! echo "$COMMAND" | grep -qE '(/Users/[^/]+/Library/|~/Library/)' && ! echo "$COMMAND" | grep -qE '^\s*(ssh|sshpass)\s'; then
  echo "BLOCKED: Command targets sensitive system path." >&2
  echo "If you really need this, ask the user to run it manually with ! prefix." >&2
  exit 2
fi

# ============================================================
# PHASE 2: Filter test output to failures only
# ============================================================

# Only rewrite simple single-command test invocations (no && or ; chaining)
if echo "$COMMAND" | grep -qE '^\s*(npm test|npm run test|npx jest|pytest|yarn test)'; then
  if ! echo "$COMMAND" | grep -qE '&&|;|grep.*(FAIL|ERROR|FAILED)'; then
    FILTER_PAT='(FAIL|FAILED|ERROR|error:|ERRORS|AssertionError|TypeError|Exception|summary|passed|failed|Tests:|short test)'
    NEW_COMMAND="__out=\$(${COMMAND} 2>&1); __rc=\$?; printf '%s\\n' \"\$__out\" | grep -B 3 -A 15 -E '${FILTER_PAT}' | head -200; exit \$__rc"
    echo "$INPUT" | jq --arg cmd "$NEW_COMMAND" '.tool_input.command = $cmd'
    exit 0
  fi
fi

# ============================================================
# PHASE 3: RTK token-saving rewrite
# ============================================================

# rtk find doesn't support compound predicates — pass those through untouched
if echo "$COMMAND" | grep -qE '\bfind\b' && echo "$COMMAND" | grep -qE '\-not\b|\-exec\b| -o | -a |\-prune\b'; then
  exit 0
fi

if ! command -v rtk &>/dev/null; then
  exit 0
fi

set +e
REWRITTEN=$(rtk rewrite "$COMMAND" 2>/dev/null)
EXIT_CODE=$?
set -e

case $EXIT_CODE in
  0|3)
    ;;
  1|2)
    exit 0
    ;;
  *)
    exit 0
    ;;
esac

# Idempotency short-circuit: covers both exit 0 (no-op rewrite) and exit 3
# (already-rtk-prefixed commands rtk echoes back unchanged).
[ "$COMMAND" = "$REWRITTEN" ] && exit 0

ORIGINAL_INPUT=$(echo "$INPUT" | jq -c '.tool_input')
UPDATED_INPUT=$(echo "$ORIGINAL_INPUT" | jq --arg cmd "$REWRITTEN" '.command = $cmd')

if [ "$EXIT_CODE" -eq 3 ]; then
  jq -n \
    --argjson updated "$UPDATED_INPUT" \
    '{
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "updatedInput": $updated
      }
    }'
else
  jq -n \
    --argjson updated "$UPDATED_INPUT" \
    '{
      "hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "allow",
        "permissionDecisionReason": "RTK auto-rewrite",
        "updatedInput": $updated
      }
    }'
fi
