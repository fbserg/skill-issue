#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
runner="$script_dir/run-offsite.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/archive/mac" "$tmp/bin"
printf '{"nonce":"same"}\n' > "$tmp/archive/mac/.transcript-archive-identity"
cp "$tmp/archive/mac/.transcript-archive-identity" "$tmp/remote-identity"

cat > "$tmp/bin/python3" <<'EOF'
#!/usr/bin/env bash
printf 'python3' >> "$CALLS"
printf ' <%s>' "$@" >> "$CALLS"
printf '\n' >> "$CALLS"
exit "${PYTHON_RC:-0}"
EOF

cat > "$tmp/bin/rclone" <<'EOF'
#!/usr/bin/env bash
printf 'rclone' >> "$CALLS"
printf ' <%s>' "$@" >> "$CALLS"
printf '\n' >> "$CALLS"
if [[ "$1" == copyto ]]; then
  cp "$REMOTE_IDENTITY" "$3"
fi
if [[ "$1" == copy ]]; then
  if [[ "${RCLONE_COPY_IGNORE_TERM:-0}" == 1 ]]; then
    printf '%s\n' "$$" > "$RCLONE_CHILD_PID_FILE"
    trap '' TERM
    while :; do sleep 0.1; done
  fi
  [[ "${RCLONE_COPY_SLEEP:-0}" == 0 ]] || sleep "$RCLONE_COPY_SLEEP"
  exit "${RCLONE_COPY_RC:-0}"
fi
exit "${RCLONE_RC:-0}"
EOF
cat > "$tmp/bin/ps" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' "${LOCK_OWNER_COMMAND:-}"
EOF
chmod +x "$tmp/bin/python3" "$tmp/bin/rclone"
chmod +x "$tmp/bin/ps"

run_runner() {
  CALLS="$tmp/calls" \
  PYTHON_BIN="$tmp/bin/python3" \
  RCLONE_BIN="$tmp/bin/rclone" \
  PS_BIN="$tmp/bin/ps" \
  OFFSITE_TIMEOUT="${OFFSITE_TIMEOUT:-10s}" \
  OFFSITE_KILL_AFTER="${OFFSITE_KILL_AFTER:-1s}" \
  REMOTE_IDENTITY="$tmp/remote-identity" \
  TRANSCRIPT_ARCHIVE_DIR="$tmp/archive" \
  TRANSCRIPT_ARCHIVE_MACHINE_ID=mac \
  TRANSCRIPT_ARCHIVE_REMOTE=remote:transcripts \
    "$runner" "$@"
}

run_runner --compress
grep -Fq "python3 <$script_dir/backup.py> <--compress>" "$tmp/calls"
grep -Fq "rclone <copy> <$tmp/archive/mac/> <remote:transcripts/mac/>" "$tmp/calls"
grep -Fq "<--exclude> </.transcript-archive-identity>" "$tmp/calls"
if grep -Fq '<sync>' "$tmp/calls"; then
  exit 1
fi

: > "$tmp/calls"
set +e
PYTHON_RC=7 run_runner
rc=$?
set -e
[[ "$rc" == 7 ]]
if grep -Fq '^rclone' "$tmp/calls"; then
  exit 1
fi

: > "$tmp/calls"
set +e
RCLONE_COPY_RC=9 run_runner
rc=$?
set -e
[[ "$rc" == 9 ]]

: > "$tmp/calls"
run_runner --compress --prune-source-screenshots-days 30
mapfile -t ordered_calls < "$tmp/calls"
[[ "${ordered_calls[0]}" == *'<--compress>'* ]]
[[ "${ordered_calls[0]}" != *'prune-source'* ]]
[[ "${ordered_calls[1]}" == rclone*copyto* ]]
[[ "${ordered_calls[2]}" == rclone*copy* ]]
[[ "${ordered_calls[3]}" == *'<--prune-only> <--prune-source-screenshots-days> <30>'* ]]
[[ "${ordered_calls[4]}" == rclone*copyto* ]]
[[ "${ordered_calls[5]}" == rclone*copy* ]]

: > "$tmp/calls"
set +e
RCLONE_COPY_RC=9 run_runner --compress --prune-source-screenshots-days 30
rc=$?
set -e
[[ "$rc" == 9 ]]
[[ $(grep -c '^python3' "$tmp/calls") == 1 ]]

: > "$tmp/calls"
printf '{"nonce":"different"}\n' > "$tmp/remote-identity"
set +e
run_runner --compress
rc=$?
set -e
[[ "$rc" == 2 ]]
if grep -q '^rclone <copy>' "$tmp/calls"; then
  exit 1
fi

cp "$tmp/archive/mac/.transcript-archive-identity" "$tmp/remote-identity"
mkdir "$tmp/archive/.offsite-mac.lock"
printf '%s\n' "$$" > "$tmp/archive/.offsite-mac.lock/pid"
: > "$tmp/calls"
set +e
LOCK_OWNER_COMMAND="$runner --compress" run_runner --compress
rc=$?
set -e
[[ "$rc" == 75 ]]
[[ ! -s "$tmp/calls" ]]
rm "$tmp/archive/.offsite-mac.lock/pid"
rmdir "$tmp/archive/.offsite-mac.lock"

mkdir "$tmp/archive/.offsite-mac.lock"
printf '999999\n' > "$tmp/archive/.offsite-mac.lock/pid"
: > "$tmp/calls"
run_runner --compress
grep -q '^rclone <copy>' "$tmp/calls"
[[ ! -e "$tmp/archive/.offsite-mac.lock" ]]

: > "$tmp/calls"
set +e
RCLONE_CHILD_PID_FILE="$tmp/resistant-child.pid" \
RCLONE_COPY_IGNORE_TERM=1 \
OFFSITE_TIMEOUT=0.2s \
OFFSITE_KILL_AFTER=0.2s \
  run_runner --compress
rc=$?
set -e
[[ "$rc" == 124 ]]
child_pid=$(cat "$tmp/resistant-child.pid")
if kill -0 "$child_pid" 2>/dev/null; then
  kill -KILL "$child_pid" 2>/dev/null || true
  exit 1
fi
[[ ! -e "$tmp/archive/.offsite-mac.lock" ]]

echo "offsite runner tests: 25 passed"
