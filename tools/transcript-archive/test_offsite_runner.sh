#!/usr/bin/env bash
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
runner="$script_dir/run-offsite.sh"
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

mkdir -p "$tmp/archive/mac" "$tmp/bin"

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
exit "${RCLONE_RC:-0}"
EOF
chmod +x "$tmp/bin/python3" "$tmp/bin/rclone"

run_runner() {
  CALLS="$tmp/calls" \
  PYTHON_BIN="$tmp/bin/python3" \
  RCLONE_BIN="$tmp/bin/rclone" \
  TRANSCRIPT_ARCHIVE_DIR="$tmp/archive" \
  TRANSCRIPT_ARCHIVE_MACHINE_ID=mac \
  TRANSCRIPT_ARCHIVE_REMOTE=remote:transcripts \
    "$runner" "$@"
}

run_runner --compress
grep -Fq "python3 <$script_dir/backup.py> <--compress>" "$tmp/calls"
grep -Fq "rclone <copy> <$tmp/archive/mac/> <remote:transcripts/mac/>" "$tmp/calls"
! grep -Fq '<sync>' "$tmp/calls"

: > "$tmp/calls"
set +e
PYTHON_RC=7 run_runner
rc=$?
set -e
[[ "$rc" == 7 ]]
! grep -Fq '^rclone' "$tmp/calls"

: > "$tmp/calls"
set +e
RCLONE_RC=9 run_runner
rc=$?
set -e
[[ "$rc" == 9 ]]

: > "$tmp/calls"
run_runner --compress --prune-source-screenshots-days 30
mapfile -t ordered_calls < "$tmp/calls"
[[ "${ordered_calls[0]}" == *'<--compress>'* ]]
[[ "${ordered_calls[0]}" != *'prune-source'* ]]
[[ "${ordered_calls[1]}" == rclone* ]]
[[ "${ordered_calls[2]}" == *'<--prune-source-screenshots-days> <30>'* ]]
[[ "${ordered_calls[3]}" == rclone* ]]

: > "$tmp/calls"
set +e
RCLONE_RC=9 run_runner --compress --prune-source-screenshots-days 30
rc=$?
set -e
[[ "$rc" == 9 ]]
[[ $(grep -c '^python3' "$tmp/calls") == 1 ]]

echo "offsite runner tests: 14 passed"
