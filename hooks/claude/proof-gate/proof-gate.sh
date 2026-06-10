#!/usr/bin/env bash
# Stop hook: "no 'done' without proof."
#
# A transcript sweep of one project over 3 weeks found ~29 sessions where Claude
# signed off as "done/fixed/shipped" while the repo still had uncommitted edits or
# commits that hadn't been pushed. The user then had to manually ask "did you push?"
# This hook converts that silent skip into one explicit checkpoint.
#
# How it works
# ------------
# On Stop, the hook checks:
#   1. Does the closing assistant message claim completion? (keyword regex)
#   2. Does the message contain an explicit local-only/WIP disclaimer? (pass silently)
#   3. Are there dirty tracked code files OR commits ahead of the upstream?
#
# If (1) and (3) but not (2): block ONCE per session and demand either the proof
# artifact or a conscious local-only statement. The agent satisfies the gate by
# appending "this is local-only" or "WIP" or by actually pushing.
#
# Fires at most once per session (marker file). Respects stop_hook_active so it
# cannot loop. Fail-open: any error (missing jq, not a git repo, etc.) exits 0.
#
# Configuration (env vars, all optional)
# --------------------------------------
# PROOF_GATE_CODE_REGEX    grep -E pattern for extensions counted as code
#                          default: \.(py|mjs|js|ts|tsx|jsx|sh|sql|toml|css|html)$
# PROOF_GATE_EXCLUDE_REGEX grep -E pattern for paths to ignore (docs/tests/etc.)
#                          default: (^|/)(docs|tests?|spec)/ or \.(md|txt|csv|json|lock)$
# PROOF_GATE_DEPLOY_CMD    name of your project's deploy command, shown in the
#                          remediation message (e.g. "just push-main")
#                          default: "git push"

set -u

# ── Read stdin (Claude Stop hook contract) ────────────────────────────────────
input="$(cat 2>/dev/null || true)"
sid="$(printf '%s' "$input"   | jq -r '.session_id     // empty' 2>/dev/null || true)"
cwd="$(printf '%s' "$input"   | jq -r '.cwd            // empty' 2>/dev/null || true)"
tpath="$(printf '%s' "$input" | jq -r '.transcript_path // empty' 2>/dev/null || true)"
active="$(printf '%s' "$input" | jq -r '.stop_hook_active // false' 2>/dev/null || true)"

# Never re-enter; bail without a session handle.
[ "$active" = "true" ] && exit 0
[ -z "$sid" ]          && exit 0

# ── Locate the git repo from cwd ─────────────────────────────────────────────
root=""
if [ -n "$cwd" ]; then
  root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || true)"
fi
[ -z "$root" ] && exit 0   # not a git repo — fail open

# ── Fire at most once per session ────────────────────────────────────────────
mark_dir="${TMPDIR:-/tmp}/claude-proof-gate"
mkdir -p "$mark_dir" 2>/dev/null || true
marker="$mark_dir/$sid"
[ -f "$marker" ] && exit 0

# ── Config with sane defaults ────────────────────────────────────────────────
CODE_REGEX="${PROOF_GATE_CODE_REGEX:-\.(py|mjs|js|ts|tsx|jsx|sh|sql|toml|css|html)$}"
EXCLUDE_REGEX="${PROOF_GATE_EXCLUDE_REGEX:-(^|/)(docs|tests?|spec)/|\.(md|txt|csv|json|lock)$}"
DEPLOY_CMD="${PROOF_GATE_DEPLOY_CMD:-git push}"

# ── Is there undeployed code? ─────────────────────────────────────────────────
# Dirty tracked code files (not docs/tests).
dirty_code=0
mapfile -t dirty_files < <(
  git -C "$root" status --porcelain 2>/dev/null \
  | awk '{print $2}' \
  | grep -E "$CODE_REGEX" \
  | grep -vE "$EXCLUDE_REGEX" \
  || true
)
[ "${#dirty_files[@]}" -gt 0 ] && dirty_code=1

# Commits ahead of upstream (tolerate no upstream — treat as 0).
ahead=0
ahead_raw="$(git -C "$root" rev-list --count '@{upstream}..HEAD' 2>/dev/null || true)"
if [[ "$ahead_raw" =~ ^[0-9]+$ ]]; then
  ahead="$ahead_raw"
fi

# Nothing undeployed → silent pass.
if [ "$dirty_code" -eq 0 ] && [ "$ahead" -eq 0 ]; then
  exit 0
fi

# ── Read the last assistant text turn from the transcript ────────────────────
last=""
if [ -n "$tpath" ] && [ -f "$tpath" ]; then
  last="$(
    tail -n 80 "$tpath" 2>/dev/null \
    | jq -rc 'select(.type=="assistant") | .message.content[]? | select(.type=="text") | .text' 2>/dev/null \
    | tail -n 1 \
    || true
  )"
fi
[ -z "$last" ] && exit 0

low="$(printf '%s' "$last" | tr '[:upper:]' '[:lower:]')"

# ── Explicit local-only / WIP disclaimer → respect it, stay silent ───────────
if printf '%s' "$low" | grep -qE \
  'local[ -]?only|not (deploy|push)|won.?t (deploy|push)|no push|skipping (push|deploy)|\bwip\b|work in progress|investigat|exploring|draft|not done|still (working|in progress)'; then
  exit 0
fi

# ── Completion claim? If it doesn't read as "finished", don't nag ────────────
if ! printf '%s' "$low" | grep -qE \
  "\b(done|fixed|shipped|deployed|landed|complete|completed|resolved|all set|works now|working now|good to go|ready)\b|✓|✅"; then
  exit 0
fi

# ── Block once, with a concrete remediation ───────────────────────────────────
touch "$marker"

reason="PROOF-GATE: you're signing off as done, but the repo at $root has undeployed code"
[ "$dirty_code" -ne 0 ] && reason="$reason (uncommitted code edits in tracked files)"
[ "$ahead" -gt 0 ]      && reason="$reason (${ahead} commit(s) ahead of upstream, not pushed)"
reason="${reason}. Do ONE of: (1) run \`${DEPLOY_CMD}\` and confirm it succeeded"
reason="${reason}, or (2) state explicitly that this is intentionally local-only / WIP."
reason="${reason} Don't claim done without one of those."

jq -nc --arg r "$reason" '{decision:"block", reason:$r}'
exit 0
