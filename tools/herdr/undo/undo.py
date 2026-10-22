"""Restore recently closed Claude/Codex panes through Herdr's public socket API."""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

from socket_rpc import rpc

# ceiling: 50 closed agent panes per socket; add a picker before increasing this.
HISTORY_LIMIT = 50


def resume_argv(session: dict[str, Any]) -> list[str]:
    if session.get("kind") != "id" or not session.get("value"):
        raise ValueError("Undo requires a recorded native conversation ID")
    agent = session["agent"]
    if agent == "codex":
        return ["codex", "--no-daemon", "resume", session["value"]]
    if agent == "claude":
        return ["claude", "--resume", session["value"]]
    raise ValueError(f"Undo does not support {agent}")


def reconcile(
    state: dict[str, Any],
    panes: list[dict[str, Any]],
    workspaces: list[dict[str, Any]],
    *,
    record_closed: bool,
) -> None:
    labels = {w["workspace_id"]: w["label"] for w in workspaces}
    live = {}
    for pane in panes:
        terminal = pane["terminal_id"]
        previous = state["live"].get(terminal)
        session = pane.get("agent_session")
        if not session and previous:
            session = previous["session"]
        if not session or session.get("agent") not in ("codex", "claude"):
            continue
        if session.get("kind") != "id" or not session.get("value"):
            continue
        cwd = pane.get("foreground_cwd") or pane.get("cwd")
        if not cwd:
            continue
        workspace = pane["workspace_id"]
        live[terminal] = {
            "terminal_id": terminal,
            "pane_id": pane["pane_id"],
            "workspace_id": workspace,
            "workspace_label": labels.get(
                workspace, (previous or {}).get("workspace_label", cwd)
            ),
            "cwd": cwd,
            "session": session,
        }
    if record_closed:
        present = {p["terminal_id"] for p in panes}
        state["closed"].extend(
            value for key, value in state["live"].items() if key not in present
        )
        state["closed"] = state["closed"][-HISTORY_LIMIT:]
    state["live"] = live


def restore(
    state: dict[str, Any], panes: list[dict[str, Any]], workspaces: list[dict[str, Any]]
) -> None:
    if not state["closed"]:
        rpc(
            "notification.show",
            {"title": "No closed agent tabs to reopen", "sound": "none"},
        )
        return
    saved = state["closed"][-1]
    session = saved["session"]
    resume_argv(session)
    existing = next(
        (
            p
            for p in panes
            if (p.get("agent_session") or {}).get("agent") == session["agent"]
            and (p.get("agent_session") or {}).get("value") == session["value"]
        ),
        None,
    )
    if existing:
        rpc("pane.focus", {"pane_id": existing["pane_id"]})
        state["closed"].pop()
        return
    if not Path(saved["cwd"]).is_dir():
        raise FileNotFoundError(f"Original directory no longer exists: {saved['cwd']}")
    workspace = next(
        (w for w in workspaces if w["workspace_id"] == saved["workspace_id"]), None
    )
    # Space Keeper recreates the last closed project space with a new ID.
    if workspace is None:
        workspace = next(
            (
                w
                for w in workspaces
                if w["label"] == saved["workspace_label"]
                and any(
                    p["workspace_id"] == w["workspace_id"]
                    and p.get("cwd") == saved["cwd"]
                    for p in panes
                )
            ),
            None,
        )
    params = {
        "cwd": saved["cwd"],
        "focus": True,
        "env": {"HERDR_UNDO_SESSION": json.dumps(session)},
    }
    if workspace:
        params["workspace_id"] = workspace["workspace_id"]
        created = rpc("tab.create", params)
    else:
        params["label"] = saved["workspace_label"]
        created = rpc("workspace.create", params)
    pane = created["root_pane"]
    state["live"][pane["terminal_id"]] = {
        **saved,
        "pane_id": pane["pane_id"],
        "terminal_id": pane["terminal_id"],
        "workspace_id": pane["workspace_id"],
    }
    state["closed"].pop()


def launch() -> None:
    session = json.loads(os.environ.pop("HERDR_UNDO_SESSION"))
    argv = resume_argv(session)
    environment = os.environ.copy()
    if argv[0] == "codex" and Path("/opt/homebrew/bin/codex").exists():
        argv[0] = "/opt/homebrew/bin/codex"
        environment["npm_config_prefix"] = "/opt/homebrew"
    os.execvpe(argv[0], argv, environment)


def main() -> None:
    mode = sys.argv[1]
    if mode == "launch":
        launch()
        return
    if mode not in ("sync", "event", "undo"):
        raise ValueError(f"Unknown mode: {mode}")
    directory = Path(os.environ["HERDR_PLUGIN_STATE_DIR"])
    directory.mkdir(parents=True, exist_ok=True)
    socket_key = hashlib.sha256(os.environ["HERDR_SOCKET_PATH"].encode()).hexdigest()[
        :16
    ]
    path = directory / f"{socket_key}.json"
    with (directory / f"{socket_key}.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = (
            json.loads(path.read_text())
            if path.exists()
            else {"live": {}, "closed": []}
        )
        panes = rpc("pane.list", {})["panes"]
        workspaces = rpc("workspace.list", {})["workspaces"]
        if mode == "undo":
            restore(state, panes, workspaces)
        else:
            reconcile(state, panes, workspaces, record_closed=mode == "event")
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2) + "\n")
        temporary.replace(path)


if __name__ == "__main__":
    main()
