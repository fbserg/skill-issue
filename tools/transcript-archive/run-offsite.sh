#!/usr/bin/env bash
# Archive to durable local storage, then copy this machine's namespace to an
# off-site rclone remote. `copy` is intentional: a damaged or incomplete local
# stage must never delete older remote history.
set -euo pipefail

script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
archive_dir=${TRANSCRIPT_ARCHIVE_DIR:?TRANSCRIPT_ARCHIVE_DIR is required}
machine_id=${TRANSCRIPT_ARCHIVE_MACHINE_ID:?TRANSCRIPT_ARCHIVE_MACHINE_ID is required}
remote=${TRANSCRIPT_ARCHIVE_REMOTE:?TRANSCRIPT_ARCHIVE_REMOTE is required}
python_bin=${PYTHON_BIN:-python3}
rclone_bin=${RCLONE_BIN:-rclone}
lock_dir="$archive_dir/.offsite-$machine_id.lock"
remote_identity_tmp=""

[[ "$machine_id" =~ ^[a-z0-9-]+$ ]] || {
  echo "run-offsite.sh: TRANSCRIPT_ARCHIVE_MACHINE_ID must match [a-z0-9-]+" >&2
  exit 2
}

mkdir -p "$archive_dir"
if ! mkdir "$lock_dir" 2>/dev/null; then
  echo "run-offsite.sh: another off-site archive run holds $lock_dir" >&2
  exit 75
fi
cleanup() {
  [[ -z "$remote_identity_tmp" ]] || rm -f "$remote_identity_tmp"
  rmdir "$lock_dir"
}
trap cleanup EXIT

archive_args=()
prune_args=()
while (($#)); do
  if [[ "$1" == "--prune-source-screenshots-days" ]]; then
    (($# >= 2)) || {
      echo "run-offsite.sh: --prune-source-screenshots-days requires a value" >&2
      exit 2
    }
    prune_args=("$1" "$2")
    shift 2
    continue
  fi
  archive_args+=("$1")
  shift
done

copy_offsite() {
  local local_identity="$archive_dir/$machine_id/.transcript-archive-identity"
  remote_identity_tmp=$(mktemp "${TMPDIR:-/tmp}/transcript-remote-identity.XXXXXX")
  if ! "$rclone_bin" copyto \
    "${remote%/}/$machine_id/.transcript-archive-identity" "$remote_identity_tmp"; then
    echo "run-offsite.sh: remote identity is missing or unreadable; refusing bulk copy" >&2
    return 2
  fi
  if ! cmp -s "$local_identity" "$remote_identity_tmp"; then
    echo "run-offsite.sh: remote identity does not match the local stage; refusing bulk copy" >&2
    return 2
  fi
  rm -f "$remote_identity_tmp"
  remote_identity_tmp=""

  "$rclone_bin" copy \
    "$archive_dir/$machine_id/" \
    "${remote%/}/$machine_id/" \
    --checksum \
    --exclude '/.transcript-archive-identity' \
    --fast-list \
    --transfers 2 \
    --checkers 4 \
    --retries 3 \
    --low-level-retries 5 \
    --stats-one-line \
    --stats 5m
}

"$python_bin" "$script_dir/backup.py" "${archive_args[@]}"
copy_offsite

if ((${#prune_args[@]})); then
  "$python_bin" "$script_dir/backup.py" "${archive_args[@]}" --prune-only "${prune_args[@]}"
  copy_offsite
fi
