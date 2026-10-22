---
name: herdr-share
description: Share the current Herdr pane through a temporary browser link. Use when the user says "herdr share", "share this session", "share my pane", or asks for view or edit access to the terminal.
---

# herdr-share

Run one of these. Print the output verbatim to the user.

```bash
herdr-share control   # watch + type, 1 viewer. Use for "edit access".
herdr-share view      # watch only, 5 viewers.
herdr-share status
herdr-share stop
```

Use the credentials printed by the installed command. Published control shares
have a random password; older host copies may use a fixed password. Links expire
after three hours by default. Source: `tools/herdr/share/herdr_share.py` in this
repository. The command output is authoritative for the active installation.
