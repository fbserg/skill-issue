# transcript-archive

A one-way, incremental, multi-machine archiver for Claude Code and Codex JSONL
transcripts. Both CLIs auto-prune old transcripts on a rolling window; this
keeps an off-machine copy that only grows. Zero runtime dependencies — stdlib
Python only.

## Why

Agent transcripts are your real work history: the decisions, prompts, and
approaches that worked (or didn't). Losing them to CLI pruning is losing notes
from a whiteboard you didn't photograph. This script keeps them — for one
machine or a whole team, without machines clobbering each other's history.

## Quickstart

The primary setup path is `install.sh`, or the `/transcript-backup` skill if
you're driving this from a running Claude Code session:

```bash
./install.sh "$HOME/Dropbox/transcript-archive"
```

This resolves `python3`, renders and installs the schedule (launchd on macOS,
cron on Linux), and runs the **first dump in the foreground** so you see the
SUMMARY line and a non-zero exit fails loudly instead of silently at 3am.
Re-run it any time to change the destination or schedule — it's idempotent.

From inside a Claude Code session, `/transcript-backup <destination-dir>` does
the same thing and verifies the install afterward (second run shows
`skipped>0`, checks the launchd/cron entry exists).

Manual setup (no install.sh) is documented under [Schedule it](#schedule-it)
below as a fallback for anyone who wants to see every moving part.

## Team / multi-machine story

Point every machine's `TRANSCRIPT_ARCHIVE_DIR` at the **same shared
destination** — a synced folder, a NAS mount, a git repo — and each machine
writes under its own `<machine-id>/` namespace. No collisions, no merge
conflicts, no machine's `history.jsonl` overwriting another's. One shared
archive, N machines, each cleanly separated:

```
$TRANSCRIPT_ARCHIVE_DIR/
  laptop-1/
    claude/projects/...
    claude/tasks/...
    codex/sessions/...
    codex/history.jsonl
    backup.log
  workstation-2/
    claude/...
    codex/...
    backup.log
```

Machine ID defaults to `platform.node()` (hostname, first label before the
first `.`), lowercased, with any character outside `[a-z0-9-]` replaced by
`-`. Override it with `TRANSCRIPT_ARCHIVE_MACHINE_ID` if you run several
archive-writing checkouts on one host, or if your hostname sanitizes down to
nothing (in which case the script refuses to guess and exits 2).

**Old-layout detection.** If `$TRANSCRIPT_ARCHIVE_DIR/claude` or `.../codex`
exists directly at the archive root (the pre-machine-namespacing v1 layout),
the script logs one `WARN` with the exact fix and continues — it never
auto-moves your files:

```
mkdir -p <machine-id> && mv claude codex <machine-id>/
```

## What it archives

| Source | Processing | Destination |
|---|---|---|
| `~/.claude/projects/**/*.jsonl` | JSON-aware image strip (Claude policy) | `<machine-id>/claude/projects/` |
| `~/.claude/tasks/**` (all files) | raw copy | `<machine-id>/claude/tasks/` |
| `~/.codex/sessions/**/*.jsonl` | JSON-aware image strip (Codex policy) | `<machine-id>/codex/sessions/` |
| `~/.codex/history.jsonl` | raw copy | `<machine-id>/codex/history.jsonl` |

`~/.claude/tasks` is archived because Claude Code's cleanup sweep now purges
it too (upstream issue #51779) — it used to be safe to skip, it isn't
anymore. `shell-snapshots/` and `backups/` are deliberately excluded: they're
machine state (shell env captures, CLI self-backups), not conversation
history, and archiving them buys nothing but disk.

Source directory structure is preserved under each destination.

## Image policy (the heart of v2)

v1 stripped anything that looked like 200+ base64 characters with a regex.
That was a lie of convenience: it also mangled thinking-block signatures (up
to 86K chars), JWTs, embedded PDFs, and SVG paths — anything long and
base64-*ish*, not just images. Archived lines could come out as **invalid
JSON**. v2 deletes the regex entirely and replaces it with a JSON-aware walk
that only ever touches known image fields, so tombstoning happens in place
and the line stays parseable.

Tombstone format (replaces the base64 string value, JSON structure
untouched):

```
__IMAGE_TOMBSTONE(media_type=<mt>,bytes=<approx_decoded_len>,sha256=<hex12>)__
```

`bytes` is `len(base64_string) * 3 // 4` (the decoded size); `sha256` is the
first 12 hex chars of the SHA-256 of the base64 string itself — enough to
tell two tombstoned images apart without keeping the bytes.

| What | Disposition | Why |
|---|---|---|
| Human-pasted images (`imagePasteIds` / `origin.kind=='human'`, Codex user-message `input_image`) | **KEPT** | Sacred — a screenshot you deliberately pasted into the conversation is content, not exhaust. |
| Documents (PDF/docx/csv attachments) | **KEPT always** | User attachments, not agent noise, and rarely huge. |
| Agent tool-result screenshots (`tool_result` content blocks, MCP browser captures, `Read`-of-image) | **TOMBSTONED** | Machine-generated, regenerable, and the overwhelming majority of image bytes. |
| Agent-forwarded images (`isMeta:true` + `agentId`, no human markers) | **TOMBSTONED** | Subagent-to-parent forwarding of the same bytes, not new content. |
| Codex agent `view_image` output (`custom_tool_call_output`, `input_image` with a `data:` URL) | **TOMBSTONED** | Same category as Claude tool screenshots. |
| Ambiguous / no markers either way | **KEPT** | Bias to preservation — an unrecognized shape is not a confident enough signal to destroy bytes. |

Measured on a real archive: in a top-20 transcript sample, ~893 agent
screenshots totaled ≈137MB — and Claude Code stores each one **twice** in the
JSONL (once in the `tool_result` block, once again in the top-level
`toolUseResult` field, byte-identical), so that's ≈274MB of duplicate bytes
in 20 files. Human pastes in the same sample: effectively zero. Tombstoning
both copies of the agent screenshots is where the size win lives; nothing a
human typed or pasted is touched.

`thinking` blocks, `signature` fields, and Codex `encrypted_content` (base64url
reasoning blobs) are never inspected or modified, full stop — not "usually
skipped by the regex," structurally out of scope for the walk.

`--force` bypasses the mtime-skip and keep-larger guards (see below) and
exists specifically to **re-run the archiver over a v1-corrupted archive**
while the original sources are still within CLI retention, repairing the
tombstone corruption and invalid-JSON lines the old regex left behind.

## The key idea: it does NOT have to be a cloud drive

The script writes to one directory (`TRANSCRIPT_ARCHIVE_DIR`) and stops
there. Off-machine durability, team sharing, and version history are entirely
about *where you point that directory* — the script itself never touches a
cloud API.

| Storage back-end | How it works |
|---|---|
| Dropbox / iCloud Drive / Google Drive / OneDrive | Point the dir at a folder inside the sync client. The client uploads it; the script doesn't know or care. |
| Syncthing | Same idea — any Syncthing-managed folder, works for a team the same way as solo. |
| Git repo | `cd $TRANSCRIPT_ARCHIVE_DIR && git add -A && git commit -m "daily" && git push` after each run (wrap in a shell script). |
| External SSD or NAS mount | Works as long as it's mounted when the job runs. |
| rsync / restic target | Run a second cron job after `backup.py` finishes. |

The script is identical for all of these. Storage is somebody else's job by
design.

### Why one mirror folder, not per-day snapshot folders

A per-day-folder layout (`2026-07-16/claude/...`) would duplicate every
still-growing transcript on every run and break incrementality outright —
the mtime-skip and keep-larger logic depend on there being exactly one
destination path per source file. Point-in-time recovery is the sync
client's job (Dropbox/iCloud version history) or git's job (commit history),
not this script's — both already do it better than a folder-per-day scheme
would.

## Setup

Requirements: `python3` (3.8+), stdlib only. See [Quickstart](#quickstart)
for `install.sh` — this section is the manual path underneath it.

```bash
export TRANSCRIPT_ARCHIVE_DIR="$HOME/Dropbox/transcript-archive"
python3 backup.py
```

Optional: `export TRANSCRIPT_ARCHIVE_MACHINE_ID="laptop-1"` to override the
hostname-derived default (see [Team / multi-machine story](#team--multi-machine-story)).

Flags:

- `--dry-run` — log what would be added/updated, write nothing, same exit
  codes.
- `--force` — bypass the mtime-skip and keep-larger guards (repair mode, see
  [Image policy](#image-policy-the-heart-of-v2)).

The last line of output is always a SUMMARY line:

```
2026-07-16T03:17:04Z  SUMMARY | machine=laptop-1 added=47 updated=3 skipped=1204 kept_larger=0 errors=0 | archive_total=1254 files | archive_size=128M | free_disk=312.4GB
```

`free_disk` is measured on the volume backing `TRANSCRIPT_ARCHIVE_DIR`
(`statvfs` on the archive dir itself), not on `/` — so it reflects the space
that actually matters when the destination is a mounted NAS or a different
disk than the OS volume.

### First run

The first run is a **full dump**, as far back as your CLI retention still
allows. Claude Code's default `cleanupPeriodDays` is 30 — anything older is
already gone before this script ever sees it. If you've set
`cleanupPeriodDays: 0` hoping for "keep forever," don't: that setting is
broken upstream (issue #23710) and behaves unpredictably rather than
disabling cleanup. Codex currently keeps session history forever with no
pruning, so a first Codex dump can be large — that's expected, not a bug.

## Schedule it

`install.sh` handles both of these for you (see [Quickstart](#quickstart)).
Manual instructions follow for anyone who wants to wire it up by hand.

### macOS — launchd

A template plist is included: `com.example.transcript-archive.plist`. It has
`@@PLACEHOLDER@@`-style tokens for the Python interpreter, `backup.py` path,
archive dir, machine ID, schedule hour/minute, and stdout/stderr log paths —
`install.sh` renders these; by hand, fill them in and:

```bash
cp com.example.transcript-archive.plist ~/Library/LaunchAgents/com.skill-issue.transcript-archive.plist
launchctl bootstrap gui/$UID ~/Library/LaunchAgents/com.skill-issue.transcript-archive.plist
```

**The env-var-in-plist gotcha:** launchd ignores your shell environment
entirely. `TRANSCRIPT_ARCHIVE_DIR` (and `TRANSCRIPT_ARCHIVE_MACHINE_ID`, if
set) must be set in the plist's `EnvironmentVariables` dict, not in
`.zshrc`. The template does this correctly — just fill in the placeholders.
Before loading, validate the rendered file: `plutil -lint
com.skill-issue.transcript-archive.plist` should say `OK`. It actually
parses the XML and catches a missed or malformed substitution, which a
text `grep '@@'` can't reliably do. A missed placeholder causes launchd to
silently fail to start or not open its log file.
`RunAtLoad` is false — the schedule handles it; `install.sh` runs the first
dump itself, in the foreground, separately.

### Linux — cron

```
17 3 * * * TRANSCRIPT_ARCHIVE_DIR="$HOME/Dropbox/transcript-archive" TRANSCRIPT_ARCHIVE_MACHINE_ID="laptop-1" /usr/bin/env python3 /path/to/backup.py >> "$HOME/Dropbox/transcript-archive/laptop-1/cron.out" 2>&1
```

`install.sh` writes an idempotent version of this tagged `# transcript-archive`
(re-running it replaces the tagged line rather than appending a second one).

### Windows

Not supported. No scheduler integration, no path handling for it — this is a
macOS/Linux tool.

### Exit codes

- `0` — clean run.
- `1` — any file error, OR zero sources found at all (see below).
- `2` — config error: `TRANSCRIPT_ARCHIVE_DIR` unset, or the machine ID
  sanitizes down to empty and no `TRANSCRIPT_ARCHIVE_MACHINE_ID` override was
  given.

A monitoring wrapper or cron-mailer can alert on non-zero exits; a config
error (2) and a run error (1) are worth distinguishing in an alert message.

## Failure modes / what a green run guarantees

**No sources found → exit 1.** If none of the expected source directories or
files exist, the script exits non-zero and logs an error. This catches a
broken launchd/cron environment (wrong `HOME`, missing dotfiles directory)
that would otherwise masquerade as a successful empty backup.

**Smaller source → `keep-larger` warning, no overwrite.** If the source file
is newer by mtime but smaller than the archived copy, the script logs a
`WARN keep-larger` line and leaves the archive copy intact (counted in
`kept_larger` in the SUMMARY). JSONL transcripts only grow within a session,
so a shrink means the source was truncated or restored from an older state —
keeping the bigger copy is the right call. `--force` overrides this.

**SUMMARY is always the last logged line.** Errors and warnings are emitted
before it. If you're tailing the log or piping to a monitor, the final line
is always the outcome.

**Idempotent.** Skip logic is mtime-based: a file is re-copied only if the
source is newer than the destination (dest mtime is set to match src mtime
after a write). Safe to run multiple times a day; a second run in a row
should show `added=0 updated=0` and `skipped` equal to the file count.

**Cloud "files-on-demand" placeholders.** If your sync client uses thin
placeholders (OneDrive, iCloud with Optimize Storage), a few files may throw
a read error while they're being downloaded. They're logged as errors and
retried on the next run — a transient error here does not corrupt the
archive.

**Log lives in the archive.** `$TRANSCRIPT_ARCHIVE_DIR/<machine-id>/backup.log`,
appended each run, also echoed to stdout. Rotates to `backup.log.1` (single
generation, no `.2`) once it exceeds 5MB. If the log file can't be opened
(permissions, missing parent), the script notes it to stderr and continues —
a broken log destination doesn't stop the backup.

**Codex compacted-session exception.** Codex lines with `payload.type ==
'compacted'` or a `replacement_history` field are copied verbatim, untouched
by the image walk — these carry the state `codex resume` needs to resume a
compacted session, and mangling them would silently break resumability.

## Notes

`~/.claude/tasks` is copied raw (no image walk) — task files aren't
transcript JSONL and don't carry the same base64 image shapes.
