# Herdr tools

Reusable Herdr plugins belong here, with one directory per tool. Keep skills
under the runtime's `skills/` tree. Host services and deployment records stay
in the host configuration repository.

## Available here

| Tool | Purpose | Status |
| --- | --- | --- |
| [Project placeholders](project-anchors/README.md) | Inert first tabs that return after closure or a Herdr server restart | Self-contained Linux plugin with unit and real-server tests |
| [Pane sharing skill](../../skills/shared/herdr-share/SKILL.md) | Request a temporary browser link with view or control access | Skill exists here; the implementation still lives in the host repository |

Project placeholders repair a close after it happens. A whole-workspace close
still stops workers. Full machine reboot recovery remains untested.

## Other existing tools worth extracting

These sources already exist in the host repository. This inventory describes
their code, not a new portability or deployment test.

| Tool | Use | Work before packaging |
| --- | --- | --- |
| [Agent state ages](https://github.com/fbserg/etc/tree/main/configs/herdr-state-age) | Show how long an agent has been blocked, working, or done in the sidebar | Remove the sibling-repository socket import and verify its refresher lifecycle |
| [Undo closed agent tabs](https://github.com/fbserg/etc/tree/main/configs/herdr-undo) | Reopen a recorded Claude or Codex conversation in its project | Remove the sibling-repository import and shell-startup dependency; currently declared macOS-only |
| [Pane sharing implementation](https://github.com/fbserg/etc/tree/main/configs/herdr-share) | Temporary browser access to a pane, with view and control modes | Package its CLI and document its ttyd/cloudflared dependencies; verify expiry and access modes |
| [Codex cache countdown](https://github.com/fbserg/etc/blob/main/scripts/herdr_codex_cache_countdown.py) | Show a cache countdown for the active Codex pane | Isolate its socket dependency and document the model-specific TTL assumptions |
| [Agent quota display](https://github.com/fbserg/etc/blob/main/scripts/herdr_agent_allowance.py) | Show remaining weekly allowance and usage pace for the active agent | Depends on the macOS CodexBar widget snapshot |

Start with state ages, then undo. Both support ordinary work without a browser
tunnel or a separate quota application. They already have focused tests, but
need standalone packaging and a fresh live check before extraction.

The older Space Keeper overlaps project placeholders. Do not ship both as
independent recovery mechanisms. Automatic-rename settings, Ovis/Collie launchers,
and machine autostart/update scripts remain host configuration.
