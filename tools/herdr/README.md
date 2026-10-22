# Herdr tools

Reusable Herdr plugins belong here, with one directory per tool. Keep skills
under the runtime's `skills/` tree. Host services and deployment records stay
in the host configuration repository.

## Available here

| Tool | Purpose | Status |
| --- | --- | --- |
| [Project placeholders](project-anchors/README.md) | Inert first tabs that return after closure or a Herdr server restart | Self-contained Linux plugin with unit and real-server tests |
| [Agent state ages](state-age/README.md) | Sidebar ages and state symbols | macOS/Linux plugin; per-session refresher state |
| [Undo closed agent tabs](undo/README.md) | Resume recorded Claude/Codex conversations | macOS plugin; requires the documented shell-startup hook |
| [Pane sharing](share/README.md) | Temporary browser view or control access | macOS/Linux plugin and CLI; requires ttyd and cloudflared |
| [Codex cache countdown](cache-countdown/README.md) | Estimated cache window for the active Codex pane | Local Codex SQLite/rollout reader with a model-specific TTL assumption |
| [Agent quota display](quota/README.md) | Weekly allowance and usage pace | CodexBar snapshot reader; macOS snapshot by default |

Project placeholders repair a close after it happens. A whole-workspace close
still stops workers. Full machine reboot recovery remains untested.

## Installation and verification

Each directory contains its own instructions, dependencies, and focused tests.
Plugin packages are self-contained and can be installed by directory through
Herdr. Display readers are CLI commands configured in the tab bar. The
[pane-sharing skill](../../skills/shared/herdr-share/SKILL.md) remains in the
shared skills tree and calls the installed CLI.

Run all package tests with `project-test --suite herdr-tools` from the repository
root. The suite uses private temporary Herdr homes. It exercises local observe
and control streams without public links, metadata updates, an owned refresher,
native-resume argument handoff with test CLIs, and display-reader fixtures.

The first publication leaves existing host installations on their current etc
copies. It does not enable new features or migrate active daemons, shares, native
agent sessions, or host state. Source changes in this repository do not change
those pinned installations. A later host migration must explicitly change their
source links and preserve their state ownership.

State-age 0.2 stores data per socket. Sharing 0.3 generates random passwords for
new control shares. These changes apply to the published packages, not to the
unchanged host copies. The gate does not claim a new public Cloudflare-tunnel test,
a real macOS CodexBar refresh, or a native macOS agent-resume session.

The older Space Keeper overlaps project placeholders. Do not ship both as
independent recovery mechanisms. Automatic-rename settings, Ovis/Collie launchers,
and machine autostart/update scripts remain host configuration.

## Publication check, October 22, 2026

All 78 tests passed on sublet, including the private real-server checks.
The tested snapshot is `4068c2e73a0023b87759244dfd4ab162f481b507`, tree
`5d5db9a119e79db36b44cbd4127550b9b99eb189`. The executor receipt is run
`20261022T204744-d516424da86f` under the caller's `.cache/project-tests/runs`.
The independent review's wrong-pane invite-reuse finding was fixed and covered
by separate pane and session regressions before publication.
