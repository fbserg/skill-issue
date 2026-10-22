# Codex cache countdown

Print a cache countdown for Herdr's active Codex pane. Requires Python 3.10+ and
local access to that Codex account's SQLite thread index and rollout files.
There are no third-party Python dependencies.

From the repository root:

```sh
mkdir -p "$HOME/.local/bin"
ln -sfn "$PWD/tools/herdr/cache-countdown/herdr_codex_cache_countdown.py" "$HOME/.local/bin/herdr-cache-countdown"
```

Add an entry to your existing `ui.tab_bar_right` list:

```toml
{ type = "command", command = "herdr-cache-countdown", interval_seconds = 5, timeout_seconds = 2 }
```

Herdr supplies `HERDR_ACTIVE_PANE_ID` and `HERDR_SOCKET_PATH`. The reader uses
`CODEX_HOME` when set and otherwise the account's `.codex` directory. It opens
`state_5.sqlite` read-only, locates the native session rollout, and scans backward
for the last token-count timestamp.

The countdown is an estimate based on a model-name rule and a 30-minute TTL.
It is not server-provided cache-expiry evidence. The inherited rule accepts
numeric GPT versions from 5.6 onward, hides older or unrecognized model names,
and reports `cache cold` after the estimated window. Provider policy or a Codex
schema change requires a reader update. Other active agents produce no output.

Tests exercise the script through a socket fixture and real SQLite/JSONL files.
This publication does not change a host's tab bar or provider policy assumptions.
