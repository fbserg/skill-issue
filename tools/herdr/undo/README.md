# Undo closed agent tabs

Reopen the most recently closed Claude or Codex conversation in its original
project. An already-open conversation is focused instead of duplicated. Missing
directories and failed tab creation leave the saved history intact.

The plugin is declared macOS-only. Requires Python 3.10+, Herdr 0.8.2+, and the
relevant native agent CLI on PATH. It records up to 50 closed panes per socket.
It resumes a conversation through the agent CLI; it does not restore a process.

From the repository root:

```sh
herdr plugin link "$PWD/tools/herdr/undo" --enabled
mkdir -p "$HOME/.local/bin"
ln -sfn "$PWD/tools/herdr/undo/undo.py" "$HOME/.local/bin/herdr-undo"
```

Add this hook near the start of `.zshrc`, before ordinary interactive setup:

```zsh
if [[ -o interactive && -n "${HERDR_UNDO_SESSION:-}" ]]; then
    exec python3 "$HOME/.local/bin/herdr-undo" launch
fi
```

The hook consumes the one-shot resume context and replaces the shell with the
native agent. Without that hook, an undo-created tab only opens a shell.

Optional Herdr shortcut:

```toml
[[keys.command]]
key = "prefix+u"
type = "plugin_action"
command = "serg.undo.undo"
description = "reopen closed agent tab"
```

Invoke `serg.undo.sync` once after first installation to record current sessions.
The startup hook and pane lifecycle events keep the record current afterward.
Session references must be native conversation IDs reported to Herdr. Ordinary
shells and unsupported agents are not recorded.

The shared Linux gate covers history, move/close handling, failure retention, and
actual exec into test agent CLIs with the one-shot context removed. This release
does not claim a new macOS end-to-end agent resume test or change existing hosts.
