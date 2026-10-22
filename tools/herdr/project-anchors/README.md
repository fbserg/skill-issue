# Herdr project placeholders

Keep an inert first tab named `🔒 plz no close` in each enrolled project.
The placeholder discards input and returns after a tab close, pane close,
process exit, or workspace close. A startup hook restores the inert process
after a Herdr server restart. No polling service or timer is required.

Requires Linux, Python 3.10 or newer, and Herdr 0.9.5 or newer. The plugin is
self-contained and uses only Python's standard library.

## Install

From a checkout of this repository:

```sh
herdr plugin link "$PWD/tools/herdr/project-anchors" --enabled
```

Or install the tool directory through Herdr:

```sh
herdr plugin install fbserg/skill-issue/tools/herdr/project-anchors --yes
```

Link or install the plugin once. This alone does not enroll any workspace.
Installed plugins are available to all local sessions, but protection state
is separate for each server socket.

In the workspace menu, choose **Keep this project open**. This works for any
project directory. To enroll all current non-worktree workspaces below the
home directory's `projects` folder, invoke:

```sh
herdr plugin action invoke serg.project-anchors.enroll
```

Enrollment also enables automatic protection for future project workspaces
under that folder on the same server. Other sessions remain inactive.

Each untouched, single-prompt first shell becomes the placeholder. If the first
tab contains an agent, command, or history, the plugin adds a separate placeholder
and moves it to the front. Open another tab for work.

Choose **Stop keeping this project open** to release a workspace. The placeholder
stays inert until closed. A released workspace does not reopen automatically.
Disable the plugin to stop all recovery on that installation.

## What survives

| Action | Result |
| --- | --- |
| Type a command, `exit`, or common exit keys | Input is discarded |
| Close the placeholder tab or pane | A new placeholder appears |
| Kill the placeholder process | A new placeholder appears |
| Close an ordinary work tab | That work tab stays closed |
| Close the entire workspace | Workers stop; only the project placeholder returns |
| Restart the Herdr server | Saved project placeholders return as inert processes |
| Reboot the machine | Requires Herdr autostart; a full reboot has not been tested |

This repairs a close after it happens. It cannot veto Herdr's close operation or
preserve running workers across a server stop. The asynchronous startup hook may
briefly expose a restored shell before it replaces that shell with the placeholder.
Native agent resume is a separate Herdr setting. The plugin does not change it.

State lives in Herdr's plugin state directory, under a hash of the server socket
path. If a project directory disappears, reconciliation fails rather than opening
a shell in an unrelated directory. Restore the directory or release that project.
Do not run another workspace-recreation plugin on the same server.

## Verify

The shared executor suite is:

```sh
project-test --suite herdr-anchors
```

The underlying test command is:

```sh
python3 -m unittest discover -s tools/herdr/project-anchors -p 'test_*.py' -v
```

The suite includes a real Herdr server in a private temporary home. It tests
ignored input, repeated closes, process death, server restart, whole-workspace
recovery, release, future-project enrollment, session-state isolation, and
preservation of a separate work terminal. It stops only its own test server.

Inspect failures with `herdr plugin log list --plugin serg.project-anchors`.
Do not restart a live server merely to validate installation.
