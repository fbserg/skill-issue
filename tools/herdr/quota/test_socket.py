import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from socket_fixture import HerdrTestServer


class DisplaySocketTests(unittest.TestCase):
    def test_allowance_ignores_incompatible_cli(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "api.sock"
            server = HerdrTestServer(
                path, lambda request: {"panes": [{"pane_id": "p1", "agent": "claude"}]}
            )
            self.addCleanup(server.close)
            env = dict(
                os.environ,
                HERDR_ACTIVE_PANE_ID="p1",
                HERDR_BIN_PATH="/usr/bin/false",
                HERDR_SOCKET_PATH=str(path),
            )
            result = subprocess.run(
                [
                    "python3",
                    str(Path(__file__).with_name("herdr_agent_allowance.py")),
                    "--snapshot",
                    directory + "/missing.json",
                ],
                check=False,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Claude quota unavailable", result.stdout)
