"""Real close and restart tests in a private Herdr home, never the user's server."""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest

import anchors


class LiveAnchorsTest(unittest.TestCase):
    def test_input_close_restart_and_release(self) -> None:
        binary = shutil.which("herdr")
        self.assertIsNotNone(binary, "Herdr 0.9.5 is required for the live gate")
        with tempfile.TemporaryDirectory(prefix="ha-") as temporary:
            root = Path(temporary)
            home = root / "home"
            config = home / ".config/herdr"
            config.mkdir(parents=True)
            (config / "config.toml").write_text('onboarding = false\n[terminal]\ndefault_shell = "/bin/dash"\n[update]\nversion_check = false\nmanifest_check = false\n[session]\nresume_agents_on_restore = false\n')
            project = home / "projects/probe"
            project.mkdir(parents=True)
            environment = {
                "PATH": os.environ["PATH"], "HOME": str(home), "SHELL": "/bin/dash", "TERM": "xterm-256color",
                "XDG_CONFIG_HOME": str(home / ".config"), "XDG_STATE_HOME": str(home / ".local/state"),
                "HERDR_CONFIG_PATH": str(config / "config.toml"), "HERDR_SOCKET_PATH": str(config / "herdr.sock"),
            }
            def cli(*args: str) -> str:
                return subprocess.check_output([binary, *args], env=environment, text=True, stderr=subprocess.PIPE, timeout=15)
            def rpc(method: str, params: dict) -> dict:
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
                    connection.settimeout(10)
                    connection.connect(environment["HERDR_SOCKET_PATH"])
                    connection.sendall((json.dumps({"id": "test", "method": method, "params": params}) + "\n").encode())
                    with connection.makefile() as stream:
                        response = json.loads(stream.readline())
                if "error" in response:
                    raise AssertionError(response["error"])
                return response["result"]
            def wait(check, description: str):
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline:
                    value = check()
                    if value:
                        return value
                    time.sleep(0.1)
                self.fail("Timed out: " + description)
            def live_anchor(cwd: str | None = None):
                panes = rpc("pane.list", {})["panes"]
                for pane in panes:
                    if cwd and pane.get("cwd") != cwd:
                        continue
                    processes = rpc("pane.process_info", {"pane_id": pane["pane_id"]})["process_info"].get("foreground_processes", [])
                    if any(str(anchors.SCRIPT) in p.get("argv", []) and "hold" in p.get("argv", []) for p in processes):
                        return pane
                return None
            def start():
                log = (root / "server.log").open("a")
                server = subprocess.Popen([binary, "server"], env=environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
                log.close()
                wait(lambda: Path(environment["HERDR_SOCKET_PATH"]).exists() and server.poll() is None, "server socket")
                return server
            cli("plugin", "link", str(anchors.SCRIPT.parent), "--enabled")
            server = start()
            try:
                created = rpc("workspace.create", {"cwd": str(project), "label": "probe", "focus": False})
                wid = created["workspace"]["workspace_id"]
                wait(lambda: rpc("pane.read", {"pane_id": created["root_pane"]["pane_id"], "source": "recent", "lines": 10})["read"]["text"].strip().endswith("$"), "initial shell prompt")
                rpc("plugin.action.invoke", {"action_id": "serg.project-anchors.protect", "context": {"workspace_id": wid}})
                anchor = wait(live_anchor, "initial placeholder")
                tabs = rpc("tab.list", {})["tabs"]
                self.assertEqual(tabs[0]["label"], anchors.LABEL)
                self.assertEqual(len(tabs), 1, json.dumps({"prompt": rpc("pane.read", {"pane_id": created["root_pane"]["pane_id"], "source": "recent", "lines": 10}), "process": rpc("pane.process_info", {"pane_id": created["root_pane"]["pane_id"]}), "panes": rpc("pane.list", {})}))
                sentinel = project / "must-not-exist"
                cli("pane", "run", anchor["pane_id"], "touch " + str(sentinel))
                cli("pane", "run", anchor["pane_id"], "exit")
                for key in ("ctrl+c", "ctrl+d", "ctrl+z", "ctrl+backslash"):
                    cli("pane", "send-keys", anchor["pane_id"], key)
                self.assertIsNotNone(live_anchor())
                self.assertFalse(sentinel.exists())

                worker = rpc("tab.create", {"workspace_id": wid, "cwd": str(project), "label": "work", "focus": False})["root_pane"]
                worker_terminal = worker["terminal_id"]
                rpc("tab.close", {"tab_id": anchor["tab_id"]})
                anchor = wait(live_anchor, "tab-close recovery")
                self.assertEqual(rpc("pane.get", {"pane_id": worker["pane_id"]})["pane"]["terminal_id"], worker_terminal)
                self.assertEqual(rpc("tab.list", {})["tabs"][0]["tab_id"], anchor["tab_id"])
                rpc("pane.close", {"pane_id": anchor["pane_id"]})
                anchor = wait(live_anchor, "pane-close recovery")
                process = rpc("pane.process_info", {"pane_id": anchor["pane_id"]})["process_info"]["foreground_processes"][0]
                os.kill(process["pid"], signal.SIGKILL)
                old_pane_id = anchor["pane_id"]
                anchor = wait(lambda: (p if (p := live_anchor()) and p["pane_id"] != old_pane_id else None), "process-kill recovery")
                cli("server", "stop")
                server.wait(timeout=10)
                server = start()
                anchor = wait(live_anchor, "restart restores inert process")
                self.assertEqual(rpc("tab.list", {})["tabs"][0]["label"], anchors.LABEL)
                cli("pane", "run", anchor["pane_id"], "touch " + str(sentinel))
                self.assertFalse(sentinel.exists())
                rpc("workspace.close", {"workspace_id": anchor["workspace_id"]})
                anchor = wait(live_anchor, "workspace-close recovery")
                self.assertNotEqual(anchor["workspace_id"], wid)
                self.assertEqual(len(rpc("pane.list", {})["panes"]), 1)
                rpc("plugin.action.invoke", {"action_id": "serg.project-anchors.release", "context": {"workspace_id": anchor["workspace_id"]}})
                # Await the action receipt rather than race an asynchronous release.
                wait(lambda: any('"projects": {}' in p.read_text() for p in home.rglob("projects.json")), "release saved")
                rpc("workspace.close", {"workspace_id": anchor["workspace_id"]})
                logs = cli("plugin", "log", "list", "--plugin", "serg.project-anchors", "--limit", "100")
                self.assertNotIn("failed", logs.lower(), logs)
                self.assertEqual(rpc("workspace.list", {})["workspaces"], [])
                created = rpc("workspace.create", {"cwd": str(project), "label": "auto-project", "focus": False})
                rpc("plugin.action.invoke", {"action_id": "serg.project-anchors.enroll", "context": {"workspace_id": created["workspace"]["workspace_id"]}})
                wait(live_anchor, "automatic enrollment")
                another = home / "projects/another"
                another.mkdir()
                new_workspace = rpc("workspace.create", {"cwd": str(another), "label": "another", "focus": False})["workspace"]
                wait(lambda: any(p["workspace_id"] == new_workspace["workspace_id"] and p.get("label") == anchors.LABEL for p in rpc("tab.list", {})["tabs"]), "new project enrolled by event")
                for _ in range(3):
                    anchor = live_anchor()
                    rpc("pane.close", {"pane_id": anchor["pane_id"]})
                    old_pane_id = anchor["pane_id"]
                    wait(lambda: (p if (p := live_anchor(anchor["cwd"])) and p["pane_id"] != old_pane_id else None), "repeat-close recovery")
            finally:
                if server.poll() is None:
                    cli("server", "stop")
                server.wait(timeout=10)


if __name__ == "__main__":
    unittest.main()
