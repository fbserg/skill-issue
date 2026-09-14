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

Login is always `as` / `as`. Links expire after one hour. Source: `~/projects/etc/configs/herdr-share/herdr_share.py`.
