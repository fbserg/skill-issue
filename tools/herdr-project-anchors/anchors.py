#!/usr/bin/env python3
"""Durable, input-free project placeholders. Closures are repaired, not vetoed."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import termios
import tty
from typing import Any, Iterator

from socket_rpc import rpc

LABEL = "🔒 plz no close"
SCRIPT = Path(__file__).resolve()
SHELLS = {"bash", "zsh", "sh", "dash", "fish"}


@contextmanager
def locked_state() -> Iterator[tuple[Path, dict[str, Any]]]:
    # Plugin storage is global. Workspace IDs are scoped to a session socket.
    session = hashlib.sha256(os.environ["HERDR_SOCKET_PATH"].encode()).hexdigest()[:20]
    directory = Path(os.environ["HERDR_PLUGIN_STATE_DIR"]) / session
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "projects.json"
    with (directory / "projects.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        state = json.loads(path.read_text()) if path.exists() else {"projects": {}, "auto": False, "released": []}
        yield path, state


def save(path: Path, state: dict[str, Any]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def foreground(pane_id: str) -> tuple[bool, bool]:
    info = rpc("pane.process_info", {"pane_id": pane_id})["process_info"]
    processes = info.get("foreground_processes", [])
    placeholder = any(str(SCRIPT) in p.get("argv", []) and "hold" in p.get("argv", []) for p in processes)
    shell = len(processes) == 1 and processes[0]["pid"] == info["shell_pid"] and processes[0]["name"].lstrip("-") in SHELLS
    return placeholder, shell


def empty_shell(pane: dict[str, Any]) -> bool:
    if pane.get("agent") or not foreground(pane["pane_id"])[1]:
        return False
    output = rpc("pane.read", {"pane_id": pane["pane_id"], "source": "recent", "lines": 10})
    # Adopt only a single untouched prompt, never a shell with command history.
    text = output["read"]["text"].strip()
    return len(text.splitlines()) == 1 and text.endswith(("$", "%", "#", ">"))


def launch(pane_id: str) -> None:
    command = shlex.join(["exec", sys.executable, str(SCRIPT), "hold"])
    subprocess.run(
        [os.environ.get("HERDR_BIN_PATH", "herdr"), "pane", "run", pane_id, command],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, check=True,
    )


def reconcile(mode: str, target: str | None = None) -> None:
    with locked_state() as (path, state):
        if mode == "sync" and not state["projects"] and not state["auto"]:
            return
        workspaces = rpc("workspace.list", {})["workspaces"]
        panes = rpc("pane.list", {})["panes"]
        tabs = rpc("tab.list", {})["tabs"]
        by_id = {w["workspace_id"]: w for w in workspaces}
        if mode == "release":
            state["projects"].pop(target, None)
            if target not in state["released"]:
                state["released"].append(target)
            save(path, state)
            return
        if mode == "enroll":
            state["auto"] = True
        for workspace in workspaces:
            wid = workspace["workspace_id"]
            candidates = [p for p in panes if p["workspace_id"] == wid]
            if not candidates or workspace.get("worktree"):
                continue
            cwd = candidates[0].get("cwd")
            project = cwd and Path(cwd).resolve().is_relative_to((Path.home() / "projects").resolve())
            wanted = (mode == "protect" and wid == target) or (state["auto"] and project and wid not in state["released"])
            if wanted and wid not in state["projects"]:
                state["projects"][wid] = {"cwd": cwd, "label": workspace["label"]}
        if mode == "protect":
            if target not in by_id:
                raise ValueError(f"Unknown workspace: {target}")
            if target in state["released"]:
                state["released"].remove(target)
        save(path, state)

        for wid, project in list(state["projects"].items()):
            if wid not in by_id:
                if not Path(project["cwd"]).is_dir():
                    raise FileNotFoundError(project["cwd"])
                created = rpc("workspace.create", {"cwd": project["cwd"], "label": project["label"], "focus": False})
                del state["projects"][wid]
                wid = created["workspace"]["workspace_id"]
                project.pop("pane_id", None)
                state["projects"][wid] = project
                panes.append(created["root_pane"])
                tabs.append(created["tab"])
                save(path, state)
            else:
                project["label"] = by_id[wid]["label"]

            owned = next((p for p in panes if p["pane_id"] == project.get("pane_id") and p["workspace_id"] == wid), None)
            if owned:
                placeholder, shell = foreground(owned["pane_id"])
                if shell:
                    launch(owned["pane_id"])
                elif not placeholder:
                    # A restored pane may have been repurposed before the hook ran.
                    # Preserve its process and give the project a new placeholder.
                    owned = None
            if not owned:
                workspace_tabs = [t for t in tabs if t["workspace_id"] == wid]
                first = workspace_tabs[0]
                candidates = [p for p in panes if p["tab_id"] == first["tab_id"]]
                if len(candidates) == 1 and empty_shell(candidates[0]):
                    owned = candidates[0]
                else:
                    created = rpc("tab.create", {"workspace_id": wid, "cwd": project["cwd"], "label": LABEL, "focus": False})
                    owned = created["root_pane"]
                project["pane_id"] = owned["pane_id"]
                save(path, state)
                launch(owned["pane_id"])
            rpc("tab.rename", {"tab_id": owned["tab_id"], "label": LABEL})
            rpc("tab.move", {"tab_id": owned["tab_id"], "insert_index": 0})
            save(path, state)


def hold() -> None:
    for sig in (signal.SIGINT, signal.SIGQUIT, signal.SIGTSTP, signal.SIGHUP):
        signal.signal(sig, signal.SIG_IGN)
    previous = termios.tcgetattr(0)
    try:
        tty.setraw(0)
        os.write(1, b"\x1b[2J\x1b[Hplz no close\r\n\r\nThis tab keeps your project here.\r\nOpen another tab for work. Input here is ignored.\r\nIf closed, this placeholder comes back.\r\nClosing the whole project still stops its workers.\r\n")
        while os.read(0, 4096):
            pass
    finally:
        termios.tcsetattr(0, termios.TCSANOW, previous)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=["hold", "sync", "enroll", "protect", "release"])
    parser.add_argument("--workspace")
    args = parser.parse_args()
    if args.mode == "hold":
        hold()
    else:
        target = args.workspace or os.environ.get("HERDR_WORKSPACE_ID")
        if args.mode in {"protect", "release"} and not target:
            parser.error("A workspace context is required")
        reconcile(args.mode, target)


if __name__ == "__main__":
    main()
