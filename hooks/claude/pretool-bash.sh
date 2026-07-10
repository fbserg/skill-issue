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
# PHASE 1.5: Heartwood VM / hw CLI guards
# ============================================================
# Scoped to the heartwood VM (100.120.251.71) and heartwood tool
# names so it never misfires on other projects. Blocks the recurring
# avoidable failures seen in transcript analysis:
#   - git over ssh on the VM (rsync-deployed, has NO .git)
#   - inline `ssh ... python3 -c "..."` (CLAUDE.md bans this)
#   - raw burl/td-ar/snag invocations over ssh (must go via `hw report`)
#   - journalctl/systemctl/sqlite3 over ssh on the VM (use hw vm logs/status/sql)
#   - manual scp+run of a .py to the VM (use hw vm eval)
#   - foreground `sleep N && cmd` (harness blocks it)
# Plus a belt-and-suspenders rewrite of bare `hw` -> absolute venv path
# for shells that didn't pick up the ~/.local/bin/hw symlink.

# git over ssh on the heartwood VM -> block
if echo "$COMMAND" | grep -qE 'ssh.*100\.120\.251\.71.*\bgit\b'; then
  echo "BLOCKED: the heartwood VM is rsync-deployed and has NO .git directory." >&2
  echo "Use \`hw ...\` instead (e.g. \`hw show\`, \`hw report status\`) — see CLAUDE.md VM Diagnostics." >&2
  exit 2
fi

# inline ssh-python on the heartwood VM -> block
if echo "$COMMAND" | grep -qE 'ssh.*100\.120\.251\.71.*python3?[[:space:]]+-c'; then
  echo "BLOCKED: CLAUDE.md bans inline ssh-python on the VM." >&2
  echo "Write a local script, \`scp\` it over, then run it — or use the \`hw\` CLI." >&2
  exit 2
fi

# raw burl/td-ar/snag tools over ssh on the heartwood VM -> block
if echo "$COMMAND" | grep -qE 'ssh.*100\.120\.251\.71.*(burl/tools/burl|burl\.py|bin/td-ar|[[:space:]]snag[[:space:]])'; then
  echo "BLOCKED: don't invoke burl/td-ar/snag over ssh." >&2
  echo "Route report ops through \`hw report ...\` — see CLAUDE.md." >&2
  exit 2
fi

# journalctl over ssh on the heartwood VM -> block
if echo "$COMMAND" | grep -qE 'ssh.*100\.120\.251\.71.*journalctl'; then
  echo "BLOCKED: don't tail VM logs over raw ssh." >&2
  echo "Use \`hw vm logs <service>\` (burl-worker|burl-server|heartwood-board|heartwood-reconcile)." >&2
  exit 2
fi

# systemctl over ssh on the heartwood VM -> block
# Sanctioned escape hatch: the operator-gated Mac-migration P3 teardown needs
# `systemctl --user disable --now` on the VM (one-time, hw has no stop/disable
# verb). Set HW_ALLOW_VM_TEARDOWN=1 inline to allow + log it.
if echo "$COMMAND" | grep -qE 'ssh.*100\.120\.251\.71.*systemctl'; then
  if [ "${HW_ALLOW_VM_TEARDOWN:-}" = "1" ] || echo "$COMMAND" | grep -qE '(^|[;&|]+[[:space:]]*)HW_ALLOW_VM_TEARDOWN=1([[:space:]]|$)'; then
    echo ">>> HW_ALLOW_VM_TEARDOWN=1: allowing sanctioned systemctl-over-ssh (P3 VM teardown)" >&2
  else
    echo "BLOCKED: don't poke VM services over raw ssh." >&2
    echo "Use \`hw vm status\` (health) or \`hw vm restart\` (bounce burl)." >&2
    echo "(P3 teardown only: prefix HW_ALLOW_VM_TEARDOWN=1 to allow stop/disable.)" >&2
    exit 2
  fi
fi

# sqlite3 over ssh on the heartwood VM -> block
if echo "$COMMAND" | grep -qE 'ssh.*100\.120\.251\.71.*sqlite3'; then
  echo "BLOCKED: query the BURL DB through hw, not raw ssh+sqlite3." >&2
  echo "Use \`hw query <table> --where key=value\` (read-only PostgREST)." >&2
  exit 2
fi

# manual scp+run workaround (.py to VM) -> block, redirect to hw vm eval
if echo "$COMMAND" | grep -qE 'scp.*100\.120\.251\.71.*\.py' \
   || echo "$COMMAND" | grep -qE 'ssh.*100\.120\.251\.71.*python3?[[:space:]]+/tmp/'; then
  echo "BLOCKED: the manual scp+run workaround is now one command." >&2
  echo "Use \`hw vm eval <script.py>\` — it scp's, runs under the VM venv, and cleans up." >&2
  exit 2
fi

# foreground `sleep N && cmd` chain -> block
if echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])sleep[[:space:]]+[0-9]+([.][0-9]+)?[[:space:]]*&&'; then
  echo "BLOCKED: foreground \`sleep N && ...\` is blocked by the harness." >&2
  echo "Use run_in_background + Monitor, or schedule a wakeup instead." >&2
  exit 2
fi

# belt-and-suspenders: bare `hw` at line start -> absolute venv path
if echo "$COMMAND" | grep -qE '^[[:space:]]*hw[[:space:]]'; then
  NEW_COMMAND=$(echo "$COMMAND" | sed -E 's#^([[:space:]]*)hw[[:space:]]#\1/Users/serg/projects/heartwood/.venv/bin/hw #')
  echo "$INPUT" | jq --arg cmd "$NEW_COMMAND" '.tool_input.command = $cmd'
  exit 0
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
  0)
    [ "$COMMAND" = "$REWRITTEN" ] && exit 0
    ;;
  1|2)
    exit 0
    ;;
  3)
    ;;
  *)
    exit 0
    ;;
esac

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
