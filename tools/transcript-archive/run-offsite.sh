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

[[ "$machine_id" =~ ^[a-z0-9-]+$ ]] || {
  echo "run-offsite.sh: TRANSCRIPT_ARCHIVE_MACHINE_ID must match [a-z0-9-]+" >&2
  exit 2
}

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
  "$rclone_bin" copy \
    "$archive_dir/$machine_id/" \
    "${remote%/}/$machine_id/" \
    --checksum \
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
  "$python_bin" "$script_dir/backup.py" "${archive_args[@]}" "${prune_args[@]}"
  copy_offsite
fi
