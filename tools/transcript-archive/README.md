# transcript-archive

A daily one-way archiver for Claude Code and Codex JSONL transcripts. Both
CLIs auto-prune old transcripts on a rolling window; this keeps an incremental
off-machine copy. Zero runtime dependencies — stdlib Python only.

## Why

Agent transcripts are your real work history: the decisions, prompts, and
approaches that worked (or didn't). Losing them to CLI pruning is losing notes
from a whiteboard you didn't photograph. This script keeps them.

Two design choices keep the archive small and safe:

**Base64 stripping.** Transcripts embed pasted images and screenshots as raw
base64 strings. An unstripped archive of a few months of work can run into tens
of gigabytes. The script replaces any run of 200+ base64-alphabet characters
with the marker `__STRIPPED_BASE64__` before writing. This is a heuristic: in
practice it catches pasted images and screenshots, but a stray long hash, token,
or opaque blob ≥200 chars can be caught too. Everything except those long
base64-ish blobs is preserved.

**One-way.** The script never deletes a destination file after the CLI prunes
the source, re-copies a transcript as it grows, and refuses to overwrite a
larger archived copy with a smaller one (logs a `keep-larger` warning instead).
No sync, no reconciliation, no surprises.

## The key idea: it does NOT have to be a cloud drive

The script writes to one directory (`TRANSCRIPT_ARCHIVE_DIR`) and stops there.
Off-machine durability is entirely about *where you point that directory* — the
script itself never touches a cloud API.

| Storage back-end | How it works |
|---|---|
| Dropbox / iCloud Drive / Google Drive / OneDrive | Point the dir at a folder inside the sync client. The client uploads it; the script doesn't know or care. |
| Syncthing | Same idea — any Syncthing-managed folder. |
| Git repo | `cd $TRANSCRIPT_ARCHIVE_DIR && git add -A && git commit -m "daily" && git push` after each run (wrap in a shell script). |
| External SSD or NAS mount | Works as long as it's mounted when the job runs. |
| rsync / restic target | Run a second cron job after backup.py finishes. |

The script is identical for all of these. Storage is somebody else's job by
design.

## What it archives

- `~/.claude/projects/**/*.jsonl` — Claude Code transcripts, including subagent
  sessions, mirrored under `$TRANSCRIPT_ARCHIVE_DIR/claude/`
- `~/.codex/sessions/**/*.jsonl` — Codex session transcripts, mirrored under
  `$TRANSCRIPT_ARCHIVE_DIR/codex/sessions/`
- `~/.codex/history.jsonl` — Codex command history, copied to
  `$TRANSCRIPT_ARCHIVE_DIR/codex/history.jsonl`

Source directory structure is preserved in the archive.

## Setup

Requirements: `python3` (3.8+), stdlib only.

```bash
export TRANSCRIPT_ARCHIVE_DIR="$HOME/Dropbox/transcript-archive"
python3 backup.py
```

The last line of output is always a SUMMARY line:

```
2026-06-26T03:00:01Z  SUMMARY | added=47 updated=3 skipped=1204 kept_larger=0 errors=0 | archive_total=1254 files | archive_size=128M | free_disk=312.4GB
```

If it looks right, wire it up to run daily.

## Schedule it

### macOS — launchd

A template plist is included: `com.example.transcript-archive.plist`. It has
four `ALL-CAPS` placeholders to fill in: the script path, the archive dir, the
stdout log path, and the stderr log path. Rename the file to match the `Label`
value, then:

```bash
cp com.example.transcript-archive.plist ~/Library/LaunchAgents/
launchctl load ~/Library/LaunchAgents/com.example.transcript-archive.plist
```

**The env-var-in-plist gotcha:** launchd ignores your shell environment
entirely. `TRANSCRIPT_ARCHIVE_DIR` must be set in the plist's
`EnvironmentVariables` dict, not in `.zshrc`. The template does this correctly
— just fill in the path. Before loading, verify every placeholder is replaced:
`grep 'PATH/TO\|ARCHIVE' com.example.transcript-archive.plist` should return
nothing. A missed placeholder causes launchd to silently fail to start or not
open its log file.

### Linux — cron

```
0 3 * * * TRANSCRIPT_ARCHIVE_DIR="$HOME/Dropbox/transcript-archive" /usr/bin/python3 /path/to/backup.py >> /path/to/backup.log 2>&1
```

The script writes its own log to `backup.log` next to `backup.py`; the cron
redirect above captures anything that leaks to stdout/stderr before the log
file is opened.

### Exit code

`0` on clean run, `1` if any file errored OR if no transcript sources were found
at all (see below). A monitoring wrapper or cron-mailer can alert on non-zero
exits.

## Failure modes / what a green run guarantees

**No sources found → exit 1.** If none of the expected source directories or
files exist, the script exits non-zero and logs an error. This catches a broken
launchd environment (wrong `HOME`, missing dotfiles directory) that would
otherwise masquerade as a successful empty backup.

**Smaller source → `keep-larger` warning, no overwrite.** If the source file is
newer by mtime but smaller than the archived copy, the script logs a
`WARN keep-larger` line and leaves the archive copy intact. JSONL transcripts
only grow within a session, so a shrink means the source was truncated or
restored from an older state — keeping the bigger copy is the right call.

**SUMMARY is always the last logged line.** Errors and warnings are emitted
before it. If you're tailing the log or piping to a monitor, the final line is
always the outcome.

**Idempotent.** Skip logic is mtime-based: a file is re-copied only if the
source is newer than the destination. Safe to run multiple times a day.

## Notes

**Base64 heuristic.** The strip regex matches any run of 200+ base64-alphabet
characters. This catches embedded images and screenshots reliably in practice,
but it's a heuristic — not content-aware. A long opaque token or hash can be
caught too. For archiving purposes that's an acceptable trade-off.

**Cloud "files-on-demand" placeholders.** If your sync client uses thin
placeholders (OneDrive, iCloud with Optimize Storage), a few files may throw
`Operation not permitted` when the script tries to read them while they're
being downloaded. They are logged as errors and retried on the next run.
