# Agent state ages

Show elapsed blocked, working, and done times in Herdr's agent sidebar.
Blocked and done ages appear immediately. Working age appears after 15 minutes.
The plugin also reports a distinct symbol for each state.

Requires macOS or Linux, Python 3.10+, and Herdr 0.8.2+. No third-party Python
dependencies are required. Install from the repository root:

```sh
herdr plugin link "$PWD/tools/herdr/state-age" --enabled
herdr plugin action invoke serg.state-age.refresh
```

Or install the directory with Herdr's GitHub installer:

```sh
herdr plugin install fbserg/skill-issue/tools/herdr/state-age --yes
```

Add the tokens to your own sidebar layout, then reload Herdr's config:

```toml
[ui.sidebar.agents]
rows = [["state_icon", "workspace", "$blocked_age", "$working_age", "$done_age"], ["agent"]]
```

State-change events update metadata immediately. A single refresher per session
updates ages every 30 seconds. Metadata expires after 90 seconds if refresh stops.
State and PID files are scoped by socket path under the plugin state directory.
The refresher exits after repeated expected refresh failures, rather than running
forever against a dead server.

Version 0.2 uses separate storage per session. If an older host copy is active,
stop its refresher before changing its source link. Do not run both versions.
This publication does not migrate existing host installations or their timestamps.

Tests cover transitions, elapsed time, session isolation, socket traffic, actual
Herdr metadata, and stopping an owned refresher. Run the category suite from the
repository root with `project-test --suite herdr-tools`.
