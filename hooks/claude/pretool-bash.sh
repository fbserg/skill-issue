#!/usr/bin/env bash
# PreToolUse hook for Bash commands: catastrophic/destructive blocks (exit 2 = block).
# 2026-09-06 subtraction: pre-push gate moved to each JS repo's .githooks/pre-push
# (covers Codex too); hold-merge guard deleted (8 real blocks vs 44 blind refusals
# in 90 days). 2026-08-07: heartwood VM guards moved to heartwood/.claude/hooks/.
set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

if [[ -z "$COMMAND" ]]; then
  exit 0
fi

# ============================================================
# PHASE 2: Block catastrophic commands
# ============================================================

# Worktree escape guard: a session isolated in .claude/worktrees/<name> must
# not use Bash to cd, redirect, or otherwise write into the shared checkout
# by absolute path — Edit/Write/git-tool calls already refuse this, Bash did
# not (observed this session: `cd /Users/serg/projects/skill-issue && python3
# ...` silently wrote into the shared checkout from a worktree agent). Reads
# of the shared checkout (git -C <root> diff/log/status, cat, grep, ls, …)
# stay allowed — an agent legitimately diffs against the main checkout.
WORKTREE_PWD="${CLAUDE_PROJECT_DIR:-$PWD}"
if [[ "$WORKTREE_PWD" == *"/.claude/worktrees/"* ]]; then
  SHARED_ROOT="${WORKTREE_PWD%%/.claude/worktrees/*}"
  # shellcheck disable=SC2016  # literal sed regex, no expansion intended
  ESC_ROOT=$(printf '%s' "$SHARED_ROOT" | sed -e 's/[.[\*^$()+?{|]/\\&/g')
  # shellcheck disable=SC2016  # literal sed regex, no expansion intended
  ESC_WORKTREE=$(printf '%s' "$WORKTREE_PWD" | sed -e 's/[.[\*^$()+?{|]/\\&/g')

  # An absolute path into THIS agent's own worktree (.claude/worktrees/<name>/…)
  # is a subpath of SHARED_ROOT but is not an escape — strip those tokens
  # before matching so the checks below only see references that land
  # directly in the shared checkout (or a sibling worktree).
  CHECK_CMD=$(echo "$COMMAND" | sed -E "s#${ESC_WORKTREE}(/[^\"'[:space:]]*)?##g")

  # cd/pushd straight into the shared checkout — the exact observed escape.
  CD_ESCAPE_RE="(^|[;&|[:space:]])(cd|pushd)[[:space:]]+[\"']?${ESC_ROOT}([\"']?([[:space:]]|/|\$))"
  # Redirection (>, >>) or tee writing a file under the shared checkout.
  REDIR_ESCAPE_RE="(^|[[:space:]])>>?[[:space:]]*[\"']?${ESC_ROOT}(/|[\"']|[[:space:]]|\$)|(^|[;&|[:space:]])tee([[:space:]]+-a)?[[:space:]]+[\"']?${ESC_ROOT}"
  # sed -i editing a file under the shared checkout in place.
  SEDI_ESCAPE_RE="(^|[;&|[:space:]])sed[[:space:]]+(-i|--in-place)([[:space:]]|=).*${ESC_ROOT}"
  # git -C <shared root> paired with a write subcommand (reads stay allowed).
  GITC_ESCAPE_RE="git[[:space:]]+-C[[:space:]]+[\"']?${ESC_ROOT}[\"']?[[:space:]]+(commit|push|reset|checkout|stash|merge|rebase|cherry-pick|revert|apply|add|mv|rm|clean|tag|branch|worktree|gc|filter-branch|submodule)\b"
  # python/perl opening a path under the shared checkout in a write mode.
  PYWRITE_ESCAPE_RE="${ESC_ROOT}.*(open\\([^)]*['\"][wax]['\"]|write_text\\(|\\.write\\()|(open\\([^)]*['\"][wax]['\"]|write_text\\(|\\.write\\().*${ESC_ROOT}"

  if echo "$CHECK_CMD" | grep -qE "$CD_ESCAPE_RE" \
     || echo "$CHECK_CMD" | grep -qE "$REDIR_ESCAPE_RE" \
     || echo "$CHECK_CMD" | grep -qE "$SEDI_ESCAPE_RE" \
     || echo "$CHECK_CMD" | grep -qE "$GITC_ESCAPE_RE" \
     || echo "$CHECK_CMD" | grep -qE "$PYWRITE_ESCAPE_RE"; then
    echo "BLOCKED: this session is isolated in the worktree $WORKTREE_PWD — this command writes into (or cd's into) the shared checkout $SHARED_ROOT by absolute path. Use $WORKTREE_PWD instead. Read-only commands against $SHARED_ROOT (cat, grep, ls, git -C <root> diff/log/status, …) are fine." >&2
    exit 2
  fi
fi

# git stash safety gate: block bare stash when working tree is dirty
if echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])git[[:space:]]+stash\b' && ! echo "$COMMAND" | grep -qE '(--keep-index|-p|--patch|-k|pop|apply|list|show|drop|branch)'; then
  UNSTAGED_COUNT=$(git -C "${CLAUDE_PROJECT_DIR:-$PWD}" status --porcelain 2>/dev/null | wc -l)
  if (( UNSTAGED_COUNT > 10 )); then
    echo "BLOCKED: working tree has $UNSTAGED_COUNT unstaged changes — \`git stash\` will sweep them all in. Stage only your files, then \`git stash --keep-index\`. Or \`git diff <files> > /tmp/patch && git checkout -- <files>\` for surgical set-aside." >&2
    exit 2
  fi
fi

# Projects dir is backed up — allow rm freely within it ($HOME-relative: /Users/serg on the Mac, /home/ubuntu on the VM)
PROJECTS_DIR="$HOME/projects/"
if echo "$COMMAND" | grep -qE '^rm\b' && echo "$COMMAND" | grep -qF "$PROJECTS_DIR" && ! echo "$COMMAND" | grep -qF "$PROJECTS_DIR.." ; then
  exit 0
fi

# shellcheck disable=SC2016  # literal $HOME etc. are intended in the regex
BLOCKED_RE='rm -rf (/|~|\$HOME|/Users|/System|/Library|/Applications|\.\s*$|\*\s*$|\./\s*$)|git push (--force|-f).*(main|master)|git reset --hard|DROP (TABLE|DATABASE)|truncate table|chmod -R 777 /|mkfs\.|dd if=.* of=/dev/|> /dev/sda|launchctl unload.*com\.apple|networksetup.*-setdnsservers|defaults delete |pkill -9 -u|killall Finder && killall Dock|tccutil reset|spctl --master-disable'

# BLOCKED_RE's `/` alternative is a bare prefix (no anchor after it), so it
# matches the first "/" of ANY absolute path right after `rm -rf ` — meaning
# `rm -rf /tmp/x` trips it exactly like `rm -rf /` does. Measured 2026-08
# (fbserg/etc#44): ~90% of a 25-command false-positive sample were safe
# scratch-dir cleanups under /tmp, /private/tmp (its resolved form), or
# /var/folders (macOS $TMPDIR) — including over ssh. Strip those path
# occurrences to an opaque token before running BLOCKED_RE against them, so
# the destructive check never sees a leading "/" for them; every other
# absolute path (bare /, ~, $HOME, /Users, /System, /var/lib/foo, /etc/foo,
# …) is untouched and still blocks. This is a check-time substitution only —
# $COMMAND itself, and every other check below, still sees the real command.
BLOCKED_CHECK_CMD=$(printf '%s' "$COMMAND" | sed -E 's#(/private/tmp/|/tmp/|/var/folders/)[^[:space:]"'"'"']*#TMPDIR_SAFE#g')

if echo "$BLOCKED_CHECK_CMD" | grep -qiE "$BLOCKED_RE"; then
  echo "BLOCKED: Destructive command detected." >&2
  echo "If you really need this, ask the user to run it manually with ! prefix." >&2
  exit 2
fi

# The two blocks below protect a macOS workstation (its /etc, launchd plists, and the TCC
# per-app popup storm). On a Linux VM (oracle-dev and friends) the session owns the box with
# passwordless sudo and there is no TCC: system-path commands like `update-locale` or
# `cat /etc/default/locale` are the job, not a hazard. Both blocks are Darwin-only.
HOST_OS="$(uname -s 2>/dev/null || echo unknown)"

if [[ "$HOST_OS" == Darwin ]] && echo "$COMMAND" | grep -qE '(^|\s)/etc/\S|.*/System/|/Library/Launch(Daemons|Agents)' && ! echo "$COMMAND" | grep -qE '(/Users/[^/]+/Library/|~/Library/)' && ! echo "$COMMAND" | grep -qE '^\s*(ssh|sshpass)\s'; then
  echo "BLOCKED: Command targets sensitive system path." >&2
  echo "If you really need this, ask the user to run it manually with ! prefix." >&2
  exit 2
fi

# foreground `sleep N && cmd` chain -> block (harness blocks foreground sleep)
if echo "$COMMAND" | grep -qE '(^|[;&|[:space:]])sleep[[:space:]]+[0-9]+([.][0-9]+)?[[:space:]]*&&'; then
  echo "BLOCKED: foreground \`sleep N && ...\` is blocked by the harness." >&2
  echo "Use run_in_background + Monitor, or schedule a wakeup instead." >&2
  exit 2
fi

# Whole-disk / whole-home filesystem walks -> block (macOS TCC prompt storm).
# A `find|bfs|fd` whose FIRST path argument is / or $HOME descends into every app's protected data
# dir (~/Library/Application Support/<App>, Containers, Group Containers, …).
# macOS asks once PER APP ("Ghostty would like to access data from other
# apps"), so a single scan produces an endless popup queue and each Allow
# grants only that one app. Scope the search, or prune ~/Library explicitly.
WALK_TOOL_RE='(^|[;&|[:space:]])(sudo[[:space:]]+)?(find|bfs|fd)[[:space:]]'
# shellcheck disable=SC2016  # literal $HOME in the regex, no expansion intended
WALK_ROOT_RE='(^|[;&|[:space:]])(sudo[[:space:]]+)?(find|bfs|fd)[[:space:]]+(-[a-zA-Z]+[[:space:]]+)*(/|~|\$HOME|/Users/[A-Za-z0-9_.-]+)([[:space:]]|$)'
if [[ "$HOST_OS" == Darwin ]] \
   && echo "$COMMAND" | grep -qE "$WALK_TOOL_RE" \
   && echo "$COMMAND" | grep -qE "$WALK_ROOT_RE" \
   && ! echo "$COMMAND" | grep -qE 'Library.*(-prune|--exclude|-not|!)|(-prune|--exclude|-not|!).*Library'; then
  echo "BLOCKED: whole-disk/whole-home filesystem walk. Scanning / or \$HOME enters every app's protected data directory and triggers a macOS TCC popup per app (\"… would like to access data from other apps\") — hundreds of them, one Allow each." >&2
  echo "Scope it (~/projects, a specific repo), or prune the protected dirs, e.g.:" >&2
  echo "  bfs ~ -name 'X*' -not -path '*/Library/*' -not -path '*/.Trash/*'" >&2
  echo "  find /Users/serg/projects -type d -name X" >&2
  exit 2
fi
