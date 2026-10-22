# Agent quota display

Show the active Claude or Codex agent's weekly allowance and usage pace in Herdr.
Requires Python 3.10+ and a readable CodexBar widget snapshot. The default snapshot
is in CodexBar's macOS app-group directory. The reader never queries credentials
or calls a provider API.

From the repository root:

```sh
mkdir -p "$HOME/.local/bin"
ln -sfn "$PWD/tools/herdr/quota/herdr_agent_allowance.py" "$HOME/.local/bin/herdr-quota"
```

Add an entry to your existing `ui.tab_bar_right` list:

```toml
{ type = "command", command = "herdr-quota", interval_seconds = 15, timeout_seconds = 2 }
```

For an explicit snapshot or a standalone check:

```sh
herdr-quota --provider codex --snapshot /path/to/widget-snapshot.json
```

Without `--provider`, the reader queries Herdr for the active pane's agent.
It selects the weekly window by its duration, regardless of which snapshot field
holds it. An up arrow means usage is ahead of an even weekly budget, and a down
arrow means spare budget. Expired windows do not claim a refill. Stale data omits
pace and labels its age. Claude data has a longer freshness allowance to match
the inherited CodexBar polling assumptions.

The code targets the CodexBar 0.57 widget schema. Tests cover window selection,
pace, stale and expired data, socket lookup, and the real CLI with a supplied
snapshot. A live macOS CodexBar refresh is outside this release's Linux gate.
Existing host tab-bar settings remain unchanged.
