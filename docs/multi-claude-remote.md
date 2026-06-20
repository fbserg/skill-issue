# Running multiple Claude Code instances on one remote machine

**Goal:** N independent Claude Code sessions on a single remote box (e.g. a build
server you reach over SSH), each optionally on a *different* claude.ai account,
each launchable with a one-word command, surviving disconnects, with a session
**picker** — and with a hard guarantee that no instance clobbers another's auth.

This is the "attach a persistent remote Claude" pattern (SSH + tmux), scaled from
one fixed session to **many, multi-account, with a selector**.

> Audience: LLM agents and operators. Every command below uses placeholders —
> `REMOTE` (host), `KEY` (ssh key), `USER` (remote login), `NAME` (instance name,
> e.g. `alpha`), `WORKDIR` (where Claude starts, relative to `$HOME`).
> Substitute and go. `id_ed25519`, `~/.local/bin`, `/opt/homebrew/bin` are
> generic defaults, not part of any one setup.

---

## Mental model — four axes of isolation

Each instance is defined by four independent choices. Get these right and
instances cannot collide.

| Axis | Mechanism | Why |
|---|---|---|
| **Config/state** | `CLAUDE_CONFIG_DIR=~/.claude-NAME` | Own `.claude.json`, sessions, history, cache |
| **Credentials** | a `.credentials.json` **file** in that dir | A different account per instance (see the Keychain trap) |
| **tmux sessions** | a dedicated socket `tmux -L NAME` | A picker for one instance never sees/kills another's |
| **Shared assets** | symlinks to one source-of-truth dir | Skills/agents/settings/memory stay in lockstep, edited once |

The local one-word command is trivial: open a TTY over SSH and run a picker
script that lives **on the box**. All the logic is remote; the launcher is four
lines.

---

## The Keychain trap (macOS) — read this first

This is the part that bites. On **macOS**, Claude Code stores the claude.ai OAuth
token in the login **Keychain**, *not* in a file. Three consequences:

1. **The Keychain item is namespaced per config dir** as
   `Claude Code-credentials-<hash>`, where `<hash>` is the first 8 hex of
   `sha256(<absolute CLAUDE_CONFIG_DIR>)`. The **default** config dir
   (`~/.claude`) uses the unsuffixed `Claude Code-credentials`. So "grab the
   Claude token from the Keychain" is ambiguous — there can be several, one per
   profile, and the unsuffixed one is usually a *different* account than the
   profile you care about. **Always identify the right item by the hash.**

2. **One Keychain slot can hold one account per OS user.** To run a *second*
   account on the same machine + same OS user, that instance must use a
   **file**: a config dir that contains its own `.credentials.json` uses the file
   and leaves the Keychain untouched. (Proof you can see on any such box: the
   default `~/.claude` with a creds file and a second profile on the Keychain
   coexist as two different accounts.)

3. **Over SSH the remote login Keychain is usually locked**
   (`security ...` → "User interaction is not allowed"). Claude can then neither
   read nor write it non-interactively. For us that's a *safety feature*: a
   file-credentialed instance launched over SSH **physically cannot migrate into
   or overwrite the shared Keychain slot** another instance depends on.

> **Linux is simpler:** creds are always a file at
> `$CLAUDE_CONFIG_DIR/.credentials.json`. No Keychain, no hash. Skip the Keychain
> extraction step and just copy that file.

**Find the hash for a given config dir** (run on the machine that holds the
account you want to copy *from*):

```bash
printf '%s' "/absolute/path/to/.claude-SOURCE" | shasum -a 256 | cut -c1-8   # macOS
printf '%s' "/absolute/path/to/.claude-SOURCE" | sha256sum   | cut -c1-8   # Linux
# -> e.g. a1b2c3d4   ==>   Keychain service "Claude Code-credentials-a1b2c3d4"
```

List every Claude Keychain item so you can see what accounts exist:

```bash
security dump-keychain 2>/dev/null \
  | grep -E '"svce"<blob>="Claude Code-credentials' | sort -u
```

---

## Setup — step by step

Assume one already-working instance (or the box default) exists, and you want to
add instance `NAME` on a chosen account.

### 1. Create the profile dir and link shared assets

Pick a single source-of-truth dir, `~/.claude-SHARED`, for read-only assets. If
you don't have one yet, use your first instance's config dir as the shared
source, or create `~/.claude-SHARED` and populate it (skills/agents/settings/
memory/statusline). Symlinks mean "pull once, every instance sees it."

```bash
ssh -i ~/.ssh/KEY USER@REMOTE '
  mkdir -p ~/.claude-NAME
  S=~/.claude-SHARED
  for f in skills agents settings.json CLAUDE.md statusline.sh; do
    ln -sfn "$S/$f" ~/.claude-NAME/"$f"
  done
'
```

Each instance keeps its **own** `.credentials.json`, `.claude.json`, and runtime
dirs (`sessions/`, `projects/`, `history.jsonl`, `cache/`).

> Trade-off: a symlinked `settings.json` is shared **read+write** — changing a
> setting inside one instance writes through to all that share the file. Want
> fully independent settings? `cp` it instead of `ln -s`.

### 2. Seed the credentials file (the chosen account)

**Never print the token.** Pipe Keychain → reshape → remote file in one shot.
Identify the source account's Keychain service via its config-dir hash (above).
The on-disk shape is `{"claudeAiOauth": { ... }}`.

```bash
# macOS source machine -> remote instance
security find-generic-password -s "Claude Code-credentials-<hash>" -w 2>/dev/null \
  | python3 -c 'import json,sys; o=json.load(sys.stdin)["claudeAiOauth"]; sys.stdout.write(json.dumps({"claudeAiOauth": o}))' \
  | ssh -i ~/.ssh/KEY USER@REMOTE 'umask 177; cat > ~/.claude-NAME/.credentials.json'
```

(Linux source: replace the `security ...` segment with
`cat ~/.claude-SOURCE/.credentials.json`.)

`umask 177` makes the file `600` on creation. If the source read fails (locked
Keychain, wrong hash), you'll get a broken/empty file — the **identity check** in
verification below catches it, so always run verification after seeding.

### 3. Pre-empt the first-run dialogs

A fresh config dir shows blocking interactive prompts (theme picker, folder-trust)
that kill a non-interactive launch. Seed `.claude.json` so the first launch drops
straight to a prompt. Use the remote home's real path — `/Users/USER` on macOS,
`/home/USER` on Linux:

```bash
ssh -i ~/.ssh/KEY USER@REMOTE 'cat > ~/.claude-NAME/.claude.json' <<'JSON'
{
  "hasCompletedOnboarding": true,
  "theme": "dark",
  "numStartups": 1,
  "projects": {
    "/Users/USER/WORKDIR": { "hasTrustDialogAccepted": true, "hasCompletedProjectOnboarding": true }
  }
}
JSON
```

> A further **"allow external CLAUDE.md imports?"** prompt can appear if your
> shared memory (`CLAUDE.md`) `@imports` a file outside `WORKDIR`. Either accept
> it once (it persists per config dir) or avoid external imports in shared memory.

### 4. Drop the two remote scripts and a dependency

`fzf` makes the picker nice; the script falls back to the `select` builtin
without it. Install once: `ssh ... 'brew install fzf'` (or your package manager).

See **Starters** below for `NAME-launch.sh` (sets `CLAUDE_CONFIG_DIR`, execs
claude) and `NAME-pick.sh` (the selector). Create the dir, deploy, mark
executable:

```bash
ssh -i ~/.ssh/KEY USER@REMOTE 'mkdir -p ~/.claude-profiles'
for f in NAME-launch.sh NAME-pick.sh; do
  cat "$f" | ssh -i ~/.ssh/KEY USER@REMOTE "cat > ~/.claude-profiles/$f && chmod +x ~/.claude-profiles/$f"
done
```

### 5. The local one-word command

Put this on your PATH as `NAME` (e.g. symlink into `~/.local/bin`):

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ssh -t -i ~/.ssh/KEY \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=4 \
  USER@REMOTE 'exec bash ~/.claude-profiles/NAME-pick.sh'
```

`ssh -t` forces a TTY so the remote picker (fzf / select / read) is interactive.

---

## Verification protocol — run this every time you touch creds

"Should work" is not verification. Four checks, all non-destructive:

1. **Tripwire — prove you did NOT write a shared Keychain slot.** Record the
   shared item's modification time before and after; it must not change.
   (`find-generic-password` prints the `mdat` attribute without `-g`; do **not**
   add `-g` here — with `2>&1` it would dump the secret into your logs.)
   ```bash
   ssh ... 'security find-generic-password -s "Claude Code-credentials" 2>&1 | grep mdat'
   ```
2. **Auth proof — the creds actually authenticate.** A one-shot print call
   returns the model's reply only if auth succeeds (and does NOT trip the
   interactive dialogs):
   ```bash
   ssh ... 'CLAUDE_CONFIG_DIR=$HOME/.claude-NAME claude -p "Reply with exactly: OK"'
   ```
3. **Identity check — the RIGHT account.** After a run, Claude records the
   resolved account in `.claude.json`. Confirm it's who you intended (grabbing the
   wrong Keychain item is *the* classic bug; a broken cred write shows up here as
   a missing `oauthAccount` or a login prompt):
   ```bash
   ssh ... 'python3 -c "import json;print(json.load(open(\"$HOME/.claude-NAME/.claude.json\")).get(\"oauthAccount\",{}).get(\"emailAddress\"))"'
   ```
4. **Neighbours intact.** List the other instances' tmux sockets and the default
   one; everything that was running still is.
   ```bash
   ssh ... 'tmux ls; tmux -L OTHER ls'
   ```

---

## Caveats

- **Same account on two instances** → shared rate-limit pool, and OAuth
  refresh-token rotation can occasionally force a one-time re-login on one side.
  Use *different* accounts for true parallelism.
- **In-memory creds.** A running instance caches its token at launch. After you
  change its `.credentials.json`, restart that session to pick it up.
- **Symlinked settings are shared writes** (see step 1).
- **bash 3.2.** macOS ships ancient bash. Keep remote scripts 3.2-safe — no
  `mapfile`, no arrays — so they run under the system shell. (The picker's
  unquoted `$sessions` is deliberate word-splitting; tmux session names with
  spaces would break it, so don't use spaces in session names.)

---

## Starters

### `NAME-launch.sh` (on the box, in `~/.claude-profiles/`)

```bash
#!/usr/bin/env bash
# Launch Claude under the NAME profile. File-based creds so it never touches
# the shared Keychain another instance relies on.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
export CLAUDE_CONFIG_DIR="$HOME/.claude-NAME"
mkdir -p "$HOME/WORKDIR"
cd "$HOME/WORKDIR" || exit 1
exec claude "$@"
```

### `NAME-pick.sh` (on the box, in `~/.claude-profiles/`) — the session selector

```bash
#!/usr/bin/env bash
# Session selector for the NAME instance. Lists Claude sessions on the dedicated
# NAME tmux socket; attach one or start a new one. Isolated from every other
# instance (they use other sockets). bash-3.2-safe: no mapfile / no arrays.
set -u
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"

TM="tmux -L NAME"
LAUNCHER="$HOME/.claude-profiles/NAME-launch.sh"
DEFAULT="NAME"
NEW="+ new session"

sessions="$($TM list-sessions -F '#S' 2>/dev/null | grep -v '^$' || true)"

if command -v fzf >/dev/null 2>&1; then
  choice="$(printf '%s\n' "$NEW" $sessions | fzf \
    --prompt='NAME > ' --height=45% --reverse --no-sort \
    --header='enter = attach  ·  pick + new session to start one')"
else
  echo; echo "NAME sessions (pick + new session to start one):"
  PS3="pick a number: "
  select choice in "$NEW" $sessions; do [ -n "${choice:-}" ] && break; done
fi

[ -z "${choice:-}" ] && exit 0          # cancelled

if [ "$choice" = "$NEW" ]; then
  printf 'new session name [%s]: ' "$DEFAULT"; read -r name
  [ -z "$name" ] && name="$DEFAULT"
  exec $TM new-session -A -s "$name" bash -lc "exec $LAUNCHER"   # -A: attach if it exists
else
  exec $TM attach-session -t "$choice"
fi
```

### Local `NAME` command (on your machine, on PATH)

```bash
#!/usr/bin/env bash
set -euo pipefail
exec ssh -t -i ~/.ssh/KEY \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=4 \
  USER@REMOTE 'exec bash ~/.claude-profiles/NAME-pick.sh'
```

---

## Why this shape (vs. a framework)

Off-the-shelf multi-agent orchestrators exist, but they solve "spawn N worktree
agents with diff review," not "attach/create named sessions across accounts on a
remote box over SSH." For that, a dedicated tmux socket + a file-credentialed
profile + a ~30-line picker is the smallest thing that works, with zero new
moving parts to reason about. Add another instance by repeating the four-axis
recipe with a new `NAME`.
```
