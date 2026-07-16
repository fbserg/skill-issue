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

Machine ID defaults to `<os-username>-<short-hostname>`, lowercased, with any
character outside `[a-z0-9-]` replaced by `-`. A bare hostname (the pre-M1
default) is the most collision-prone value on a team: default MacBook names,
DHCP-assigned names, and corporate imaging all hand out identical or
near-identical hostnames, and two machines resolving the same machine-id
interleave writes into one namespace (see [Identity
handshake](#identity-handshake) below for how a collision now gets caught
instead of silently corrupting history). Override with
`TRANSCRIPT_ARCHIVE_MACHINE_ID` (or `install.sh --machine-id`) if you run
several archive-writing checkouts on one host, or if the derived id sanitizes
down to nothing (in which case the script refuses to guess and exits 2).
`install.sh`'s bash default and `backup.py`'s Python default derive the id
the same way, from the same two inputs, so a manual `python3 backup.py` run
(no `install.sh` involved) lands on the identical id `install.sh` would have
registered.

## Identity handshake

Machine-namespacing alone isn't enough to stop two machines from colliding:
if they resolve to the *same* machine-id (an accidental duplicate hostname,
someone copy-pasting a `--machine-id`, a rebuilt laptop reusing an old name),
they interleave writes into one `<machine-id>/` directory with no
coordination. Proven failure modes: a smaller/older interleaved write gets
logged as `kept_larger` (silently dropped), a bigger one gets logged as
`updated` (silently clobbering the other machine's history). A second,
unrelated failure mode looks similar from the outside: `TRANSCRIPT_ARCHIVE_DIR`
points at a NAS mount or sync-client folder that isn't actually
mounted/synced *right now* — the OS happily creates a fresh empty directory
tree at that path, and the archiver "successfully" builds a brand-new shadow
archive on local disk while the real, already-populated archive sits
untouched on the (unmounted) other end. Exit 0 either way, nothing to
distinguish a good run from a corrupting or a misdirected one just by
looking at the exit code.

The fix is a small identity handshake, checked before any archive write
happens (before even `backup.log` gets created or rotated):

- The first successful run for a given `(TRANSCRIPT_ARCHIVE_DIR, machine-id)`
  pair generates a random nonce and writes it to **both**:
  - `<machine_root>/.transcript-archive-identity` — JSON with `machine_id`,
    `hostname`, `os_user`, the `nonce`, and a `created` timestamp, living
    *inside* the shared archive.
  - `<local state dir>/<sha256 of the absolute archive dir>.json` — JSON with
    the same `nonce`, living on *this machine only*. State dir is
    `$XDG_STATE_HOME/transcript-archive/` if `XDG_STATE_HOME` is set, else
    `~/.local/state/transcript-archive/`.
- Every later run compares the two nonces:
  - **Both present, matching** → proceed normally, no further writes to
    either identity file.
  - **Both present, mismatched** → `exit 2`, loud stderr explanation, **zero
    writes** (this run doesn't even create `backup.log`). This is the
    machine-id-collision signature: a genuinely different physical machine
    reached this same `machine_root` and got its own nonce recorded at some
    point, and the two no longer agree.
  - **Local nonce recorded, but the archive has no identity file at all** →
    `exit 2`, zero writes, unless `--adopt-archive` is passed. This is the
    unmounted-NAS / wrong-destination signature: this machine has archived
    here before (it has a local record), but the archive side now looks
    brand new — the real destination probably isn't mounted right now.
  - **Archive has an identity file, but this machine has no local record** →
    `exit 2`, zero writes, unless `--adopt-archive` is passed. This is the
    other half of the collision signature: some *other* machine already
    established this `machine_root`'s identity, and this machine has never
    recorded agreeing with it.
  - **Neither side has anything recorded** → adopt silently, write both. This
    is either a genuine first run, or a pre-hardening archive that already
    has real content but predates the identity file — either way there's
    nothing to contradict, so there's nothing to refuse.
- `--dry-run` runs every check above but never writes the identity files
  either, matching its "log what would happen, write nothing" contract
  everywhere else in this tool.
- `--adopt-archive` is the deliberate override for the two one-sided cases
  above, when you've confirmed (not guessed) it's a lost-local-state or
  rebuilt/moved-archive situation rather than an actual collision: it makes
  the missing side agree with the side that already exists, instead of
  generating a new nonce.

See [Identity handshake failure modes](#identity-handshake-failure-modes)
below for exactly what each refusal means and how to resolve it.

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

## Analyzing the archive

This tool's stated purpose is keeping your prompt/transcript history around
to actually look at later — here's how.

**One traversal catches both plain and compressed files.** `--compress`
means any given archive may have a mix of `.jsonl` and `.jsonl.gz` files
(files migrate format one at a time, on their next write — see
[Compression](#compression-optional)), so analysis code needs to walk both:

```python
from pathlib import Path

for path in Path(archive_root).rglob("*.jsonl*"):
    if path.suffix not in (".jsonl", ".gz"):
        continue  # rglob("*.jsonl*") also catches e.g. "foo.jsonl.bak" -- be precise
    ...
```

Don't dispatch on suffix with a single `.endswith(".jsonl")` check and a
separate `.endswith(".gz")` branch elsewhere in your code — a `.jsonl.gz`
file has **two** extensions, and code that only ever checks the last one
(`.gz`) needs the *other* check too to know it's transcript JSONL at all
underneath, not some other gzipped file that happened to land in the
archive.

**Uniform open, one line:**

```python
import gzip

def open_transcript(path):
    return gzip.open(path, "rt", encoding="utf-8") if path.name.endswith(".gz") else open(path, "rt", encoding="utf-8")

with open_transcript(path) as f:
    for line in f:
        ...  # each line is one JSON object, exactly as documented above
```

**Identifying genuine human prompts vs. machinery.** Not every `role: user`
line was typed by a person — most of them, in an agentic transcript, weren't:

- **Claude Code:** a real human prompt has `promptSource == "typed"` or
  `origin.kind == "human"` (the same markers the image policy uses to decide
  what's sacred — see the table below). Exclude:
  - `isMeta: true` records (agent-internal bookkeeping lines, not user turns)
  - records carrying `agentId` / `sidechain: true` (subagent traffic, not the
    primary conversation)
  - `tool_result`-only content blocks (the CLI's own tool output being fed
    back in, formatted to look like a "user" turn to the model, not a human
    saying anything)
- **Codex:** `history.jsonl` has a sharper caveat than the sessions files —
  it's a flatter format, and **templated tool text can appear as a `user`
  line** (Codex sometimes re-injects tool/command output as a user-role
  history entry). A `role: user` line in `history.jsonl` is not proof a
  human typed it; cross-reference against the corresponding session JSONL
  (which carries the richer `payload.type` markers) if you need to be sure.

**The tombstone is deliberately not valid base64 — never blind-decode
`source.data`.** A tombstoned image field looks like:

```
__IMAGE_TOMBSTONE(media_type=image/png,bytes=48291,sha256=a1b2c3d4e5f6)__
```

That string will fail (loudly, with an exception) if you feed it to
`base64.b64decode()` — on purpose. It's not corrupted base64 that needs a
lenient decoder; it's a marker that the original bytes were deliberately
discarded (see [Image policy](#image-policy-the-heart-of-v2) below for which
images and why). Analysis code that walks `source.data` fields expecting
valid base64 must check for the `__IMAGE_TOMBSTONE(` prefix first and treat
it as "bytes not available" rather than attempting to decode it — a naive
"try to decode everything, catch the exception" approach works too, but a
prefix check is cheaper and makes the intent explicit in the code.

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
- `--compress` — gzip every archived file (see [Compression](#compression-optional) below).
- `--adopt-archive` — rebless a one-sided identity mismatch as legitimate
  instead of refusing to run (see [Identity handshake](#identity-handshake)).
  Only use this after confirming it's a lost-local-state or rebuilt-archive
  situation, not an actual machine-id collision.

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

## Compression (optional)

`--compress` gzips (stdlib `gzip`, level 6) every file written to the
archive; the destination path gains a `.gz` suffix. Measured on a real
17,298-file archive (Claude + Codex transcripts, `~/.claude/tasks`, Codex
`history.jsonl`): 7.0G uncompressed → 1.9G compressed, **~3.7x**. Actual
ratio depends on how much of the corpus is already-high-entropy content
(base64 thinking signatures, tombstoned-but-still-present hashes) versus
plain JSON/prose, which compresses much better on its own.

**Lossless, and a drop-in for analysis.** The bytes inside the `.gz` are
exactly what uncompressed mode would have written — same stripped/
tombstoned transcripts, same raw copies. Reading them back is one line:
`gzip.open(path, "rt")` instead of `open(path)` in Python, or `zcat`/`zgrep`
instead of `cat`/`grep` on the command line — the corpus is easier to ship
around and scan through, not harder, once your tools go through the gzip
layer. The cost: you can't `grep`/open a `.gz` file directly in an editor or
naive `grep` without decompressing first (`zgrep` fixes command-line grep;
editors mostly won't).

**Format migration is automatic and one-way per file.** Turning `--compress`
on or off for an archive that already has copies in the *other* format
doesn't leave you with duplicates: on the next run, the existing plain (or
`.gz`) copy is used for the mtime-skip and keep-larger decisions as if it
were the target format, and once the new-format copy is written
successfully, the old-format copy for that file is deleted. This is the one
sanctioned deletion in an otherwise one-way, never-delete archiver — see
`process_file()` in `backup.py` for exactly where it happens. Turning
compression off later reverses it (`.gz` copies get replaced by plain ones
and removed) the same way, one file at a time as each is next touched. If
that cleanup unlink ever fails (permissions, an interrupted process), the
run still counts as a success — the new-format copy was written correctly —
but logs a distinct `WARN: stale ... left behind` line, and every
subsequent run retries the cleanup unconditionally (independent of
mtime-skip) until the stale duplicate is finally gone.

**Corrupted `.gz` never wedges the guard.** The keep-larger comparison reads
a `.gz`'s uncompressed size from its gzip ISIZE footer, but only after
validating the file is actually a readable gzip stream (magic bytes plus a
full decompress pass). A truncated or corrupted `.gz` — left by a
non-atomic write interrupted mid-run (crash, `kill -9`, disk-full, a
sync-client conflict copy) — fails that validation, so the guard treats its
size as unknown and lets the correct new content overwrite it, instead of
trusting garbage trailing bytes and refusing to ever re-archive that file
without `--force`.

**Enabling on an existing install:** re-run `install.sh` with `--compress`
(it re-registers the schedule with the flag baked in, and runs an
incremental dump immediately — only files newer than their archived copy get
migrated). To convert the whole existing backlog to `.gz` in one pass rather
than waiting for each file's next natural update, run the archiver once with
both flags: `--compress --force` — `--force` bypasses the mtime-skip so every
already-archived file gets picked up and compressed on that run.

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
- `2` — config error: `TRANSCRIPT_ARCHIVE_DIR` unset, the machine ID
  sanitizes down to empty and no `TRANSCRIPT_ARCHIVE_MACHINE_ID` override was
  given, or the [identity handshake](#identity-handshake) refused to run
  (mismatched or one-sided identity nonce). In every identity-refusal case,
  zero writes were made this run — see [Identity handshake failure
  modes](#identity-handshake-failure-modes).

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

**Writes are atomic — no half-written file ever replaces a good one.** Every
write to the archive (transcripts, identity files) goes to a temp file in
the same directory first, gets `fsync`'d, then lands via `os.replace()`.
Disk-full, a crash, or `kill -9` mid-write leaves either the old content
untouched or nothing at all — never a truncated file stamped with a fresh
mtime that the mtime-skip logic would then treat as "already archived,
correct" forever. (This is exactly the failure mode a non-atomic
`write_bytes()` used to have: a truncated destination with `mtime >= src`
was permanently invisible to every later run short of `--force`.)

**A torn read self-heals only if the source keeps growing.** If a transcript
file is read mid-write by the source CLI (a torn trailing line), the
archived copy inherits that torn line. On the *next* run, if the source has
grown further (new mtime, and — since [M2](#m2) — genuinely more content),
the whole file gets re-copied and the torn line is naturally replaced by a
complete one. If the source CLI never touches that file again (session
ended, no further writes), the torn line stays torn in the archive forever
— nothing after it can trigger a re-copy. Recover with `--force` if you
notice one.

**mtime-skip has a content fallback for raw-copied files only.** <a
name="m2"></a>A restored/replaced source with an mtime that's still `>=` the
archived copy's (so the skip logic would normally trust it) but genuinely
different content used to be skipped forever. For `kind == 'raw'` sources
(`~/.claude/tasks`, `~/.codex/history.jsonl` — copied byte-for-byte, so
dest size always equals src size when they actually match), a size mismatch
on the skip path now forces a re-copy even when the mtime says "unchanged".
**This does not extend to the `strip-claude`/`strip-codex` kinds** (the
`.jsonl` transcripts) — their processed size differs from the source by
design (tombstoning shrinks it), so a size comparison there can't
distinguish "genuinely different content" from "same content, same
tombstones, as always". If you suspect a transcript file was restored from
an older snapshot with a newer-or-equal mtime and stale archived content,
`--force` is the fix; there's no honest way to auto-detect it for this
kind without maintaining a persistent manifest of decoded content hashes,
which this tool deliberately does not do.

**Long paths can silently fail sync clients even after a green run.** <a
name="m3"></a>A full destination path composes as: `TRANSCRIPT_ARCHIVE_DIR`
(commonly 40–60 chars for a path inside a cloud-sync folder) + `/<machine-id>`
(a handful to ~30 chars) + `/claude/projects/` (17 chars) + the
source-derived project directory name (Claude Code encodes the project's
absolute working-directory path into this name, `/` replaced with `-` —
routinely 80–150+ chars for a few levels of nested repo/monorepo paths) +
`/<session-uuid>.jsonl` (~45 chars). Measured on real archives, this
composition realistically lands at **407+ characters**. OneDrive (and some
other sync clients) silently refuses to sync anything past roughly 400
characters — the *local* run still reports success (`backup.py` only writes
to a local filesystem path; it has no idea whether or how a sync client will
handle that path afterward), so the failure surfaces later, quietly, as a
file that's on your machine but never made it off-machine. `backup.py` logs
`WARN long-path (may exceed sync-client limits): <path>` per offender when a
destination path hits 400+ characters (no new SUMMARY field — the format is
frozen — so watch the log, not the summary line, for this one). Mitigation:
point `TRANSCRIPT_ARCHIVE_DIR` at as shallow a path as your sync client
allows (e.g. directly under the sync root, not three folders deep), and keep
`--machine-id` short — those are the two components you control; the
project-path and session-uuid components are not.

**cron has no sleep/wake catch-up.** Unlike launchd (which fires a missed
`StartCalendarInterval` job shortly after wake if the Mac was asleep at the
scheduled time), plain cron on a Linux laptop simply skips a run the machine
was asleep for — there's no catch-up mechanism built in. If your archive
machine is a laptop that sleeps overnight, either install
[anacron](https://en.wikipedia.org/wiki/Anacron) (`anacron` re-runs missed
periodic jobs on next boot/wake) or, on distros with systemd, use a
[systemd user timer](https://www.freedesktop.org/software/systemd/man/systemd.timer.html)
with `Persistent=true` instead of a crontab entry — that setting is
exactly the "catch up on the next opportunity" behavior cron lacks.
`install.sh` still installs a plain crontab entry on Linux (see [Linux —
cron](#linux--cron)); swapping it for a systemd timer is a manual step this
tool doesn't automate.

### Identity handshake failure modes

See [Identity handshake](#identity-handshake) above for the full mechanism.
What each refusal actually means, and how to resolve it:

| Refusal | What it means | Resolve by |
|---|---|---|
| Both nonces present, mismatched | Some other machine has already run against this exact `machine_root` with a different local identity than yours — the machine-id-collision signature. | Give one of the two machines a distinct `--machine-id` / `TRANSCRIPT_ARCHIVE_MACHINE_ID`, then re-run. Do **not** `--adopt-archive` this case — it's not a one-sided mismatch, it's an active collision, and reblessing one side doesn't fix that two machines still want the same name. |
| Local nonce present, archive has no identity file | This machine has a record of archiving here before, but the archive side looks brand new. Almost always an unmounted NAS/external disk, or a sync client that hasn't finished attaching the folder yet. | Check the mount/sync status of `TRANSCRIPT_ARCHIVE_DIR` first. If it's genuinely mounted and this really is a rebuilt/moved archive on purpose, `--adopt-archive` to rebless it. |
| Archive has an identity file, this machine has no local nonce | Either a genuine machine-id collision (another machine already established this `machine_root`), or this machine's local state (`~/.local/state/transcript-archive/` or `$XDG_STATE_HOME/transcript-archive/`) was cleared/lost. | If you're confident this is your own archive and your local state was simply lost, `--adopt-archive`. Otherwise treat it as a collision — pick a distinct `--machine-id`. |
| Neither side has a record | Not actually a refusal — this silently adopts (writes both files) and the run proceeds. Listed here only so it isn't mistaken for one of the above when you're reading the log. | Nothing to do. |

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
