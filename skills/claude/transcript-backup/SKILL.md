---
name: transcript-backup
description: Set up (or re-check) the daily transcript-archive backup for Claude Code + Codex JSONL transcripts on this machine. Use when the user invokes /transcript-backup <destination-dir>, asks to back up / archive their Claude or Codex transcripts, or reports a transcript-archive install/schedule problem.
---

Boundary: this skill installs and verifies the local backup job (`tools/transcript-archive/install.sh`) — it does not touch the archiving logic itself (`backup.py`) or debug JSONL image-policy questions beyond what the troubleshooting table below covers.

## Steps

1. **Locate the repo.** Find `tools/transcript-archive/install.sh` on this machine (check the current repo first, then any known local clones). If it isn't present anywhere, clone `skill-issue` and use the copy inside the clone.

2. **Run install.sh with the destination the user gave you:**

   ```bash
   ./tools/transcript-archive/install.sh <destination-dir>
   ```

   Pass through `--machine-id ID` or `--time HH:MM` only if the user specified them; otherwise let the script derive the machine id from the hostname and use its default time (03:17). This both registers the daily schedule (launchd on macOS, cron on Linux) and runs the **first dump immediately in the foreground** — that first run is the initial full archive, not just a schedule registration.

   Relay the `SUMMARY | ...` line from the output verbatim — it's the receipt: added/updated/skipped/kept_larger/errors counts plus archive size and free disk space on the destination volume.

3. **Verify the install actually stuck:**
   - Re-run `install.sh` with the same arguments. The second run's SUMMARY should show `skipped` accounting for nearly everything and `added` near zero — proof the incremental mtime-skip logic is working, not re-copying the world every time.
   - macOS: confirm the job is registered — `launchctl print gui/$UID/com.skill-issue.transcript-archive` should succeed (not "could not find service").
   - Linux: confirm the crontab entry exists — `crontab -l | grep transcript-archive`.

4. **Troubleshoot:**
   - **launchd job runs but archives nothing / wrong HOME:** launchd does not inherit your shell environment or `$HOME` assumptions the way a terminal does — `install.sh` bakes `TRANSCRIPT_ARCHIVE_DIR` and `TRANSCRIPT_ARCHIVE_MACHINE_ID` directly into the plist's `EnvironmentVariables` for exactly this reason. If something still looks wrong, check the rendered plist at `~/Library/LaunchAgents/com.skill-issue.transcript-archive.plist`, not your shell profile.
   - **Sporadic read errors on cloud-synced source or destination folders** (iCloud Drive / OneDrive "files on demand" placeholders): transient — a file materializes on next access. `backup.py` logs the error and moves on; it gets picked up on the next scheduled run. Don't treat one bad run as broken.
   - **Exit code 2** — configuration error (`TRANSCRIPT_ARCHIVE_DIR` unset/unreachable, or a machine id that sanitizes to empty). Fix the environment/args, don't retry as-is.
   - **Exit code 1** — file errors during copy, or zero source directories found on this machine (nothing under `~/.claude/projects`, `~/.claude/tasks`, `~/.codex/sessions`, `~/.codex/history.jsonl`). Confirm the CLIs in question are actually installed and have produced transcripts here.
   - **Re-running `install.sh` is always safe** — it's idempotent: same destination/time re-registers the same job without duplicating it; a new destination or `--time` replaces the previous schedule for this machine.
