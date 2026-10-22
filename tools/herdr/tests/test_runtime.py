"""Exercise packaged scripts against an owned Herdr server, without public links."""

import json
import os
from pathlib import Path
import pty
import select
import shlex
import shutil
import signal
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone

ROOT = Path(__file__).resolve().parents[1]


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="ht-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        home = self.root / "home"
        config = home / ".config/herdr"
        config.mkdir(parents=True)
        (config / "config.toml").write_text('onboarding = false\n[terminal]\ndefault_shell = "/bin/dash"\n[update]\nversion_check = false\nmanifest_check = false\n')
        binary = shutil.which("herdr")
        self.assertIsNotNone(binary)
        self.binary = binary
        self.environment = {
            "PATH": os.environ["PATH"], "HOME": str(home), "TERM": "xterm-256color", "SHELL": "/bin/dash",
            "XDG_CONFIG_HOME": str(home / ".config"), "XDG_STATE_HOME": str(home / ".local/state"),
            "HERDR_CONFIG_PATH": str(config / "config.toml"), "HERDR_SOCKET_PATH": str(config / "herdr.sock"),
            "HERDR_BIN_PATH": binary, "HERDR_PLUGIN_STATE_DIR": str(self.root / "plugin-state"),
        }
        with (self.root / "server.log").open("w") as log:
            self.server = subprocess.Popen([binary, "server"], env=self.environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        self.addCleanup(self.stop_server)
        self.wait(lambda: Path(self.environment["HERDR_SOCKET_PATH"]).exists(), "server socket")
        self.pane = self.rpc("workspace.create", {"cwd": str(self.root), "label": "test", "focus": False})["root_pane"]

    def stop_server(self) -> None:
        if self.server.poll() is None:
            subprocess.run([self.binary, "server", "stop"], env=self.environment, capture_output=True, check=True, timeout=10)
        self.server.wait(timeout=10)

    def wait(self, check, description: str):
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            value = check()
            if value:
                return value
            time.sleep(0.05)
        self.fail("Timed out: " + description)

    def rpc(self, method: str, params: dict) -> dict:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(5)
            connection.connect(self.environment["HERDR_SOCKET_PATH"])
            connection.sendall((json.dumps({"id": "test", "method": method, "params": params}) + "\n").encode())
            with connection.makefile() as stream:
                response = json.loads(stream.readline())
        self.assertNotIn("error", response)
        return response["result"]

    def script(self, name: str, *args: str, extra: dict | None = None) -> str:
        return subprocess.check_output([sys.executable, str(ROOT / name), *args], env={**self.environment, **(extra or {})}, stderr=subprocess.PIPE, text=True, timeout=10)

    def stop_group(self, process: subprocess.Popen) -> None:
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        process.stdout.close()
        process.stderr.close()

    def output_until(self, process: subprocess.Popen, marker: bytes) -> bytes:
        output = b""
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if select.select([process.stdout], [], [], 0.1)[0]:
                data = os.read(process.stdout.fileno(), 65536)
                if not data:
                    self.fail(f"Stream exited before {marker!r}: {output!r}")
                output += data
                if marker in output:
                    return output
        self.fail(f"No {marker!r} in stream: {output!r}")

    def test_state_age_metadata_and_owned_daemon_stop(self) -> None:
        pane_id = self.pane["pane_id"]
        self.rpc("pane.report_agent", {"pane_id": pane_id, "source": "test:ages", "agent": "codex", "state": "blocked"})
        self.script("state-age/state_age.py", "once")
        pane = self.rpc("pane.get", {"pane_id": pane_id})["pane"]
        self.assertEqual(pane["tokens"]["blocked_age"], "<1m")
        state = next((self.root / "plugin-state").glob("*/state.json"))
        with (self.root / "daemon.log").open("w") as log:
            daemon = subprocess.Popen([sys.executable, str(ROOT / "state-age/state_age.py"), "daemon"], env=self.environment, stdin=subprocess.DEVNULL, stdout=log, stderr=log)
        def cleanup():
            if daemon.poll() is None:
                daemon.terminate()
            daemon.wait(timeout=5)
        self.addCleanup(cleanup)
        (state.parent / "daemon.pid").write_text(str(daemon.pid))
        self.script("state-age/state_age.py", "stop")
        self.assertEqual(daemon.wait(timeout=5), -signal.SIGTERM)
        self.assertFalse((state.parent / "daemon.pid").exists())

    def test_share_observe_transport(self) -> None:
        marker = "share-observe-proof"
        subprocess.run([self.binary, "pane", "run", self.pane["pane_id"], f"printf '{marker}\\n'"], env=self.environment, check=True, capture_output=True)
        process = subprocess.Popen([sys.executable, str(ROOT / "share/herdr_share.py"), "observe", self.pane["pane_id"]], env=self.environment, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        self.addCleanup(self.stop_group, process)
        self.assertIn(marker.encode(), self.output_until(process, marker.encode()))

    def test_share_control_transport(self) -> None:
        master, slave = pty.openpty()
        self.addCleanup(os.close, master)
        process = subprocess.Popen([sys.executable, str(ROOT / "share/herdr_share.py"), "bridge", self.pane["pane_id"]], env=self.environment, stdin=slave, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True)
        os.close(slave)
        self.addCleanup(self.stop_group, process)
        self.output_until(process, b"$")
        proof = self.root / "typed-proof"
        os.write(master, f"printf bridge-ok > {shlex.quote(str(proof))}\r".encode())
        self.wait(proof.exists, "typed command")
        self.assertEqual(proof.read_text(), "bridge-ok")

    def test_undo_launch_executes_native_resume_and_clears_context(self) -> None:
        binaries = self.root / "bin"
        binaries.mkdir()
        proof = self.root / "resume.json"
        stub = '#!/usr/bin/env python3\nimport json,os,sys\nfrom pathlib import Path\nPath(os.environ["RESUME_PROOF"]).write_text(json.dumps({"argv":sys.argv[1:],"session_env":os.environ.get("HERDR_UNDO_SESSION")}))\n'
        for name in ("codex", "claude"):
            executable = binaries / name
            executable.write_text(stub)
            executable.chmod(0o755)
            session = {"agent": name, "kind": "id", "value": "owned-test-session"}
            self.script("undo/undo.py", "launch", extra={"PATH": str(binaries) + os.pathsep + self.environment["PATH"], "HERDR_UNDO_SESSION": json.dumps(session), "RESUME_PROOF": str(proof)})
            value = json.loads(proof.read_text())
            self.assertIsNone(value["session_env"])
            self.assertEqual(value["argv"], ["--no-daemon", "resume", "owned-test-session"] if name == "codex" else ["--resume", "owned-test-session"])

    def test_quota_cli_reads_a_snapshot(self) -> None:
        now = datetime.now(timezone.utc)
        snapshot = self.root / "widget.json"
        snapshot.write_text(json.dumps({"entries": [{"provider": "codex", "updatedAt": now.isoformat(), "secondary": {"windowMinutes": 10080, "usedPercent": 25, "resetsAt": (now + timedelta(days=3.5)).isoformat()}}]}))
        output = self.script("quota/herdr_agent_allowance.py", "--provider", "codex", "--snapshot", str(snapshot))
        self.assertIn("Codex 7d 75% left", output)


if __name__ == "__main__":
    unittest.main()
