#!/usr/bin/env bash
# install.sh -- one-command setup for tools/transcript-archive/backup.py.
#
# Usage: ./install.sh <ARCHIVE_DIR> [--machine-id ID] [--time HH:MM] [--compress]
#
# Registers a daily scheduled run of backup.py (launchd on macOS, cron on
# Linux), then runs the first dump immediately in the foreground so the
# archive is populated right away. Safe to re-run: re-running with a new
# ARCHIVE_DIR / --time / --compress replaces the previous schedule for this
# machine -- re-running WITHOUT --compress removes it from the schedule too
# (the schedule is always fully re-rendered from this run's flags, never
# patched).
set -euo pipefail

DEFAULT_TIME="03:17"

usage() {
  cat <<'EOF'
Usage: install.sh <ARCHIVE_DIR> [--machine-id ID] [--time HH:MM] [--compress]

  ARCHIVE_DIR   Destination root for the transcript archive (required).
                Point this at a folder inside a synced drive (Dropbox,
                iCloud Drive, Google Drive, OneDrive, Syncthing) for
                automatic off-machine backup.
  --machine-id  Override the machine identifier used to namespace this
                machine's copy inside ARCHIVE_DIR (default:
                <os-username>-<short-hostname>, sanitized).
  --time HH:MM  Local time for the daily scheduled run (default: 03:17).
  --compress    Gzip every archived file (adds --compress to the scheduled
                command and to the immediate first dump). Re-run without
                this flag to drop it from the schedule again.

Schedules a daily run (launchd on macOS, cron on Linux) and then runs the
first dump immediately in the foreground. Re-run to change the destination,
time, or compression -- this script is idempotent.
EOF
}

die() {
  echo "install.sh: $*" >&2
  exit 1
}

sanitize_machine_id() {
  # Must match backup.py's sanitize_machine_id() exactly: lowercased, chars
  # outside [a-z0-9-] replaced with '-'. install.sh runs every machine id
  # (explicit --machine-id or the hostname-derived default) through this
  # before using it in any path or plist value, so install.sh and backup.py
  # can never disagree on which directory a given machine's archive lives
  # in.
  local h=$1
  h=$(printf '%s' "$h" | tr '[:upper:]' '[:lower:]')
  h=$(printf '%s' "$h" | sed -E 's/[^a-z0-9-]/-/g')
  printf '%s' "$h"
}

default_machine_id() {
  # '<os-username>-<short-hostname>', sanitized. Must stay in exact agreement
  # with backup.py's default_machine_id_raw()/resolve_machine_id() -- same
  # two inputs, same order, same sanitize rules -- so a manual `python3
  # backup.py` run (no install.sh, no explicit --machine-id/env override)
  # derives the identical machine id install.sh would have registered. A
  # bare hostname (the old default) is the most collision-prone value on a
  # team: default MacBook names, DHCP names, and corporate imaging all hand
  # out identical or near-identical hostnames (M1).
  local h u
  h=$(hostname -s 2>/dev/null || hostname)
  h=${h%%.*}
  u=$(id -un 2>/dev/null || whoami)
  sanitize_machine_id "${u}-${h}"
}

# Renders the plist template: replaces every @@TOKEN@@ placeholder with a
# real value in a single simultaneous pass. Delegates to python3 (already a
# hard requirement) rather than bash's ${var//pattern/replacement}: bash
# treats a literal '&' in the *replacement* operand as a sed-style
# backreference to the matched text, which silently corrupts any
# substituted value containing '&' (e.g. an ARCHIVE_DIR named
# "archive&dir") -- and chained sequential substitutions have their own
# hazard, where an earlier-substituted value that happens to literally
# contain a later @@TOKEN@@ string gets re-mangled by the later pass.
# python3's re.sub() with a single combined pattern replaces all tokens in
# one pass over the ORIGINAL template text, sidestepping both. Split out of
# the macOS install path so it can be exercised in isolation (see
# test_backup.py / manual verification) without touching real launchd
# state -- this function is never itself destructive, it only writes a
# file at the $output path it is given.
render_plist() {
  local template=$1 output=$2 python_bin=$3 backup_py=$4 archive_dir=$5
  local machine_id=$6 hour=$7 minute=$8 log_out=$9 log_err=${10} compress=${11}
  RP_TEMPLATE="$template" RP_OUTPUT="$output" \
  RP_PYTHON="$python_bin" RP_BACKUP_PY="$backup_py" RP_ARCHIVE_DIR="$archive_dir" \
  RP_MACHINE_ID="$machine_id" RP_HOUR="$hour" RP_MINUTE="$minute" \
  RP_LOG_OUT="$log_out" RP_LOG_ERR="$log_err" RP_COMPRESS="$compress" \
  "$python_bin" - <<'PYEOF'
import os
import re

# @@COMPRESS_ARG@@ renders to an extra <string>--compress</string>
# ProgramArguments entry when --compress was passed to install.sh this run,
# or to nothing (a blank line, harmless in plist XML) otherwise -- the whole
# plist is re-rendered from this run's flags every time, so re-running
# without --compress drops it from the schedule just like --time replaces
# the schedule time.
TOKENS = {
    "@@PYTHON@@": os.environ["RP_PYTHON"],
    "@@BACKUP_PY@@": os.environ["RP_BACKUP_PY"],
    "@@ARCHIVE_DIR@@": os.environ["RP_ARCHIVE_DIR"],
    "@@MACHINE_ID@@": os.environ["RP_MACHINE_ID"],
    "@@HOUR@@": os.environ["RP_HOUR"],
    "@@MINUTE@@": os.environ["RP_MINUTE"],
    "@@LOG_OUT@@": os.environ["RP_LOG_OUT"],
    "@@LOG_ERR@@": os.environ["RP_LOG_ERR"],
    "@@COMPRESS_ARG@@": "<string>--compress</string>" if os.environ["RP_COMPRESS"] == "1" else "",
}


def xml_escape(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# @@COMPRESS_ARG@@ is the one token whose value is itself a raw XML element
# (or empty), not text content -- every other token's value gets XML-escaped
# since it's substituted *inside* a <string>...</string>.
RAW_TOKENS = {"@@COMPRESS_ARG@@"}


def substitute(m: "re.Match") -> str:
    token = m.group(0)
    value = TOKENS[token]
    return value if token in RAW_TOKENS else xml_escape(value)


pattern = re.compile("|".join(re.escape(token) for token in TOKENS))
with open(os.environ["RP_TEMPLATE"], encoding="utf-8") as f:
    content = f.read()
content = pattern.sub(substitute, content)
with open(os.environ["RP_OUTPUT"], "w", encoding="utf-8") as f:
    f.write(content)
PYEOF
}

# Refuses (exit non-zero, backup.py's own loud stderr explanation) BEFORE
# the schedule gets registered if ARCHIVE_DIR/<machine-id> already carries an
# identity that doesn't agree with this machine's local state -- reuses
# backup.py's actual identity-handshake logic (imported as a module, dry_run
# so it makes zero writes either way) rather than re-implementing the nonce
# comparison in bash. Without this, a colliding --machine-id would still get
# a launchd/cron job installed even though every scheduled run would then
# refuse to write anything.
verify_identity_or_die() {
  local archive_dir=$1 machine_id=$2 backup_py=$3
  local script_dir
  script_dir=$(cd "$(dirname "$backup_py")" && pwd)
  if ! PYTHONPATH="$script_dir" python3 - "$archive_dir" "$machine_id" <<'PYEOF'
import sys
from pathlib import Path

import backup

archive_dir = Path(sys.argv[1])
machine_id = sys.argv[2]
machine_root = archive_dir / machine_id
try:
    backup.check_machine_identity(archive_dir, machine_root, machine_id, dry_run=True, adopt_archive=False)
except SystemExit as e:
    sys.exit(e.code if e.code is not None else 1)
sys.exit(0)
PYEOF
  then
    die "archive identity check failed for machine id '${machine_id}' at ${archive_dir} " \
      "(see the message above) -- refusing to register the schedule. Pass a distinct " \
      "--machine-id, or run backup.py directly with --adopt-archive if this really is " \
      "your own archive."
  fi
}

install_macos() {
  local archive_dir=$1 machine_id=$2 hour=$3 minute=$4 backup_py=$5 template=$6 compress=$7
  local python_bin label plist_dir plist_path log_dir log_out log_err compress_flag

  python_bin=$(command -v python3) || die "python3 not found on PATH"
  label="com.skill-issue.transcript-archive"
  plist_dir="${HOME}/Library/LaunchAgents"
  plist_path="${plist_dir}/${label}.plist"
  log_dir="${archive_dir}/${machine_id}"
  log_out="${log_dir}/launchd.out"
  log_err="${log_dir}/launchd.err"
  compress_flag=0
  [[ "$compress" == "1" ]] && compress_flag=1

  mkdir -p "$plist_dir"
  mkdir -p "$log_dir"

  render_plist "$template" "$plist_path" "$python_bin" "$backup_py" \
    "$archive_dir" "$machine_id" "$hour" "$minute" "$log_out" "$log_err" "$compress_flag"

  # Unload any previous registration for this label, then (re)register.
  # bootout fails (harmlessly) if the job wasn't loaded yet.
  launchctl bootout "gui/$(id -u)/${label}" >/dev/null 2>&1 || true
  launchctl bootstrap "gui/$(id -u)" "$plist_path"

  echo "install.sh: launchd job '${label}' installed -> ${plist_path}" >&2
  echo "install.sh: scheduled daily at ${hour}:${minute} (RunAtLoad=false); launchd logs -> ${log_dir}/launchd.{out,err}" >&2
}

install_linux() {
  local archive_dir=$1 machine_id=$2 hour=$3 minute=$4 backup_py=$5 compress=$6
  local python_bin cron_out cron_line existing filtered new_crontab compress_suffix

  python_bin=$(command -v python3) || die "python3 not found on PATH"
  mkdir -p "${archive_dir}/${machine_id}"
  cron_out="${archive_dir}/${machine_id}/cron.out"
  compress_suffix=""
  [[ "$compress" == "1" ]] && compress_suffix=" --compress"

  # shellcheck disable=SC2016
  # (values are interpolated deliberately below, not left literal)
  cron_line="${minute} ${hour} * * * TRANSCRIPT_ARCHIVE_DIR=\"${archive_dir}\" TRANSCRIPT_ARCHIVE_MACHINE_ID=\"${machine_id}\" /usr/bin/env python3 \"${backup_py}\"${compress_suffix} >> \"${cron_out}\" 2>&1 # transcript-archive"

  existing=$(crontab -l 2>/dev/null || true)
  filtered=$(printf '%s\n' "$existing" | grep -v '# transcript-archive$' || true)
  new_crontab=$(printf '%s\n%s\n' "$filtered" "$cron_line" | sed '/^$/d')
  printf '%s\n' "$new_crontab" | crontab -

  echo "install.sh: crontab entry installed (tag '# transcript-archive')" >&2
  echo "install.sh: scheduled daily at ${hour}:${minute}; cron output -> ${cron_out}" >&2
  echo "install.sh: ${cron_line}" >&2
}

main() {
  local archive_dir="" machine_id="" time_spec="$DEFAULT_TIME" compress=0

  if [[ $# -eq 0 ]]; then
    usage >&2
    exit 1
  fi

  while [[ $# -gt 0 ]]; do
    case "$1" in
      -h|--help)
        usage
        exit 0
        ;;
      --machine-id)
        [[ $# -ge 2 ]] || die "--machine-id requires a value"
        machine_id=$2
        shift 2
        ;;
      --time)
        [[ $# -ge 2 ]] || die "--time requires a value (HH:MM)"
        time_spec=$2
        shift 2
        ;;
      --compress)
        compress=1
        shift
        ;;
      --)
        shift
        ;;
      -*)
        die "unknown option: $1"
        ;;
      *)
        if [[ -n "$archive_dir" ]]; then
          die "unexpected extra argument: $1"
        fi
        archive_dir=$1
        shift
        ;;
    esac
  done

  [[ -n "$archive_dir" ]] || { usage >&2; die "ARCHIVE_DIR is required"; }

  [[ "$time_spec" =~ ^([0-9]{1,2}):([0-9]{2})$ ]] || die "--time must be HH:MM, got: $time_spec"
  local hour=${BASH_REMATCH[1]} minute=${BASH_REMATCH[2]}
  hour=$((10#$hour))
  minute=$((10#$minute))
  ((hour >= 0 && hour <= 23)) || die "--time hour out of range: $hour"
  ((minute >= 0 && minute <= 59)) || die "--time minute out of range: $minute"

  if [[ -z "$machine_id" ]]; then
    machine_id=$(default_machine_id)
    [[ -n "$machine_id" ]] || die "could not derive a machine id from the hostname; pass --machine-id explicitly"
  else
    # Sanitize an explicit --machine-id the same way backup.py sanitizes
    # whatever it receives via TRANSCRIPT_ARCHIVE_MACHINE_ID, so the log
    # dir / plist EnvironmentVariables value install.sh sets up always
    # agrees with the directory backup.py actually writes to.
    machine_id=$(sanitize_machine_id "$machine_id")
    [[ -n "$machine_id" ]] || die "--machine-id sanitized to empty; pass a value with at least one [a-z0-9-] character"
  fi

  command -v python3 >/dev/null 2>&1 || die "python3 not found on PATH -- install Python 3.8+ and re-run"

  local script_dir backup_py template
  script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
  backup_py="${script_dir}/backup.py"
  template="${script_dir}/com.example.transcript-archive.plist"
  [[ -f "$backup_py" ]] || die "backup.py not found next to install.sh at ${backup_py}"

  # Normalize/expand ARCHIVE_DIR (may not exist yet -- backup.py creates it).
  mkdir -p "$archive_dir"
  archive_dir=$(cd "$archive_dir" && pwd)

  verify_identity_or_die "$archive_dir" "$machine_id" "$backup_py"

  local uname_s
  uname_s=$(uname -s)
  case "$uname_s" in
    Darwin)
      [[ -f "$template" ]] || die "plist template not found at ${template}"
      install_macos "$archive_dir" "$machine_id" "$hour" "$minute" "$backup_py" "$template" "$compress"
      ;;
    Linux)
      install_linux "$archive_dir" "$machine_id" "$hour" "$minute" "$backup_py" "$compress"
      ;;
    *)
      die "unsupported OS: ${uname_s} (only macOS and Linux are supported)"
      ;;
  esac

  echo "install.sh: running first dump now..." >&2
  set +e
  if [[ "$compress" == "1" ]]; then
    env TRANSCRIPT_ARCHIVE_DIR="$archive_dir" TRANSCRIPT_ARCHIVE_MACHINE_ID="$machine_id" \
      python3 "$backup_py" --compress
  else
    env TRANSCRIPT_ARCHIVE_DIR="$archive_dir" TRANSCRIPT_ARCHIVE_MACHINE_ID="$machine_id" \
      python3 "$backup_py"
  fi
  local rc=$?
  set -e
  exit "$rc"
}

# Allow this file to be sourced (e.g. to call render_plist directly for
# testing) without running main.
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  main "$@"
fi
