# Share a Herdr pane

Publish one pane through a temporary browser terminal, with view or control access.
Requires macOS or Linux, Python 3.10+, Herdr 0.9.5+, `ttyd`, and `cloudflared`.
There are no Python package dependencies.

From the repository root:

```sh
herdr plugin link "$PWD/tools/herdr/share" --enabled
mkdir -p "$HOME/.local/bin"
ln -sfn "$PWD/tools/herdr/share/herdr_share.py" "$HOME/.local/bin/herdr-share"
```

Use an explicit pane ID, or invoke a workspace menu action. CLI calls from inside
a Herdr pane prefer the caller's pane rather than another client's current focus.

```sh
herdr-share view --pane PANE_ID
herdr-share control --pane PANE_ID
herdr-share status
herdr-share stop
```

| Mode | Browser access | Login | Viewer limit |
| --- | --- | --- | --- |
| View | Output only | `as` / `as` | 5 |
| Control | Can type into the pane | `as` / random password printed in the invite | 1 |

Version 0.3 assigns a random password to each new control share. Keep the whole
invite private. Read-only access keeps the original fixed login.
An existing invite is reused only after validating the same pane on the same
Herdr socket. Requests for a different pane or session replace the share.

Links expire after three hours by default. `--ttl SECONDS` accepts 60 seconds
through 24 hours. The expiry helper revokes only its own share generation, so an
old helper cannot revoke a replacement. There is one share per machine. Plugin
actions and the CLI use the same state directory, independent of plugin context.
Use `HERDR_SHARE_STATE_DIR` to select a different directory explicitly.

`ttyd` listens on loopback and a Cloudflare quick tunnel provides the temporary
URL. The tunnel uses HTTP/2. View mode uses an observe-only Herdr stream and does
not enable writable ttyd mode. Control uses Herdr's control stream. Both follow
the owner's terminal dimensions rather than resizing the owner's pane to fit
the browser. The invite is copied to the clipboard when `pbcopy` is available.

The tests cover modes, credentials, expiry ownership, private state permissions,
and real local Herdr observe/control traffic. They do not open a public tunnel or
retest Cloudflare availability. Existing host installations remain unchanged by
this publication.
