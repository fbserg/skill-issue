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

The local one-word command is small: it picks a transport (mosh if present, else
`ssh -t`) and runs a picker script that lives **on the box**. All the logic is
remote. Transport and picker polish (live preview, detach-on-attach, auto-named
sessions) are orthogonal niceties layered on top — see Starters.

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

Two optional deps sharpen this:
- **`fzf`** — fuzzy picker *and* the live per-session preview; without it the
  picker falls back to a numbered `select` menu (no preview).
- **`mosh`** — opt-in resilient transport (`NAME_TRANSPORT=mosh`) for sleep / IP
  changes / flaky phone networks. ssh -t is the default because a blocked-UDP
  mosh hangs hard; only opt in where UDP 60000-61000 actually reaches the box.

Install fzf on the box and your laptop; mosh on both only if you opt in: `brew install fzf` (+ `mosh` when wanted).

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

Keep the launcher dumb and put the connection details in a sibling **`NAME.env`**
so editing host/port/key never means touching the script.

**Naming convention (follow it for every instance):** the env file is
`NAME.env`, and every variable in it is prefixed `<NAME-uppercased>_` —
`BMAC_HOST`, `CMAC_PICKER`, etc. One glance tells you which instance a variable
belongs to, and two instances' envs can never shadow each other. The fixed keys
are `<N>_HOST`, `<N>_PORT`, `<N>_USER`, `<N>_KEY`, `<N>_PICKER` (plus an optional
`<N>_MOSH_SERVER`). The prefix is simply the connection's own name, uppercased —
`bmac` → `BMAC_*`, `cmac` → `CMAC_*`. Nothing clever; just the name.

`NAME.env` (next to the launcher, and/or in `~/projects/NAME/`):

```bash
NAME_HOST="REMOTE"          # Tailscale IP / MagicDNS name
NAME_PORT="22"
NAME_USER="USER"
NAME_KEY="$HOME/.ssh/KEY"
NAME_PICKER="/Users/USER/.claude-profiles/NAME-pick.sh"
NAME_MOSH_SERVER="/opt/homebrew/bin/mosh-server"   # only used when mosh is present
```

`NAME` launcher — put it on your PATH (e.g. symlink into `~/.local/bin`):

```bash
#!/usr/bin/env bash
set -euo pipefail
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
for cfg in "$SELF_DIR/NAME.env" "$HOME/projects/NAME/NAME.env"; do
  [ -f "$cfg" ] && { . "$cfg"; break; }
done
: "${NAME_HOST:?NAME.env not found or NAME_HOST unset}"
: "${NAME_PORT:=22}" "${NAME_USER:=USER}" "${NAME_KEY:=$HOME/.ssh/KEY}"
: "${NAME_PICKER:=/Users/USER/.claude-profiles/NAME-pick.sh}"
: "${NAME_TRANSPORT:=ssh}"
: "${NAME_MOSH_SERVER:=/opt/homebrew/bin/mosh-server}"

# ssh by DEFAULT (robust everywhere, incl. over Tailscale). Opt into mosh with
# NAME_TRANSPORT=mosh — but ONLY where UDP 60000-61000 reaches the box, or mosh
# hangs. A broken mosh must never be the default, or it locks you out.
if [ "$NAME_TRANSPORT" = "mosh" ] && command -v mosh >/dev/null 2>&1; then
  exec mosh --server="$NAME_MOSH_SERVER" --ssh="ssh -p $NAME_PORT -i $NAME_KEY" \
    "${NAME_USER}@${NAME_HOST}" -- bash "$NAME_PICKER"
fi
exec ssh -t -p "$NAME_PORT" -i "$NAME_KEY" \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=4 \
  "${NAME_USER}@${NAME_HOST}" "exec bash ${NAME_PICKER}"
```

Both transports hand the remote picker an interactive TTY (mosh always; `ssh -t`
forces one), so fzf / select / read work either way.

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
- **mosh is opt-in, ssh is default.** mosh needs UDP 60000–61000 reachable to the
  box; if those are dropped (some Tailscale paths, UDP-blocking wifi) mosh hangs
  with "Nothing received from server on UDP port …". Because a present-but-blocked
  mosh would otherwise lock you out, the launcher uses ssh unless you set
  `NAME_TRANSPORT=mosh`. Verify UDP works before opting in.
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
# NAME tmux socket WITH a live preview of each pane; attach one (detaching any
# other client) or start a fresh, timestamped one. Isolated from every other
# instance (they use other sockets). bash-3.2-safe: no mapfile / no arrays.
set -u
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"

TM="tmux -L NAME"
LAUNCHER="$HOME/.claude-profiles/NAME-launch.sh"
DEFAULT="NAME"
NEW="＋ new session"

sessions="$($TM list-sessions -F '#S' 2>/dev/null | grep -v '^$' || true)"

if command -v fzf >/dev/null 2>&1; then
  # Live preview of each session's pane ($TM is fully expanded into the string,
  # so the preview subshell needs no env). The NEW row has no pane → placeholder.
  PREVIEW="$TM capture-pane -ep -t {} 2>/dev/null || echo '(starts a fresh session)'"
  choice="$(printf '%s\n' "$NEW" $sessions | fzf \
    --prompt='NAME ▸ ' --height=90% --reverse --no-sort \
    --preview "$PREVIEW" --preview-window='right,62%,wrap,border-left' \
    --header='enter = attach  ·  pick ＋ new session to start one')"
else
  echo; echo "NAME sessions (pick ＋ new session to start one):"
  PS3="pick a number: "
  select choice in "$NEW" $sessions; do [ -n "${choice:-}" ] && break; done
fi

[ -z "${choice:-}" ] && exit 0          # cancelled

if [ "$choice" = "$NEW" ]; then
  default="$DEFAULT-$(date +%m%d-%H%M)"   # timestamped so repeats don't collide
  printf 'new session name [%s]: ' "$default"; read -r name
  [ -z "$name" ] && name="$default"
  # -A: attach if it exists, else create.  -D: detach any other client on attach.
  exec $TM new-session -A -D -s "$name" bash -lc "exec $LAUNCHER"
else
  exec $TM attach-session -d -t "$choice"   # -d: detach any other client
fi
```

### `status` overview (optional) — what's running, without attaching

One read-only command that lists every instance's sessions and which account
each profile is authed as, without attaching to anything. Edit the `show` lines
to name your instances (`label · tmux-flags · config-dir`; empty flags = the
default socket).

```bash
#!/usr/bin/env bash
set -euo pipefail
source "$HOME/projects/ANY/ANY.env"        # any instance's env — same box & key
ssh -p "$ANY_PORT" -i "$ANY_KEY" "${ANY_USER}@${ANY_HOST}" 'bash -s' <<"REMOTE"
export PATH="$HOME/.local/bin:/opt/homebrew/bin:$PATH"
acct(){ python3 - "$1" <<'PY'
import json,os,sys
p=os.path.expanduser("~/%s/.claude.json"%sys.argv[1])
try: print(json.load(open(p)).get("oauthAccount",{}).get("emailAddress","?"))
except Exception: print("?")
PY
}
show(){ printf '\n\033[1m── %s\033[0m  (%s)\n' "$1" "$(acct "$3")"
  tmux $2 list-sessions \
    -F '   #S  [#{?session_attached,attached,detached}]  #{session_windows}w' \
    2>/dev/null || echo '   (none)'; }
show alpha ""        .claude-alpha     # default-socket instance
show beta  "-L beta" .claude-beta      # dedicated-socket instance
REMOTE
```

### Local `NAME` command + `NAME.env` (on your machine, on PATH)

See **step 5** for the full pair: a thin launcher that sources `NAME.env` and
execs `ssh -t … NAME-pick.sh`, plus the `NAME.env` file whose keys are all
prefixed `<NAME-uppercased>_` (`NAME_HOST`, `NAME_PORT`, `NAME_USER`, `NAME_KEY`,
`NAME_PICKER`, `NAME_TRANSPORT`, `NAME_MOSH_SERVER`). The prefix is just the
connection name, uppercased. `NAME_TRANSPORT` is `ssh` (default) or `mosh`.

---

## Why this shape (vs. a framework)

Off-the-shelf multi-agent orchestrators exist, but they solve "spawn N worktree
agents with diff review," not "attach/create named sessions across accounts on a
remote box over SSH." For that, a dedicated tmux socket + a file-credentialed
profile + a ~30-line picker is the smallest thing that works, with zero new
moving parts to reason about. Add another instance by repeating the four-axis
recipe with a new `NAME`.
```
