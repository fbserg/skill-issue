#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from socket_fixture import HerdrTestServer

SCRIPT = Path(__file__).with_name("herdr_codex_cache_countdown.py")
SESSION_ID = "01a02518-e1ad-7100-8954-e5fcb58bc875"


class HerdrCodexCacheCountdownTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.codex_home = self.root / "codex"
        self.codex_home.mkdir()
        self.rollout_path = self.codex_home / "rollout.jsonl"

    def create_thread(self, model: str = "gpt-5.6-sol") -> None:
        with sqlite3.connect(self.codex_home / "state_5.sqlite") as database:
            database.execute(
                "CREATE TABLE threads (id TEXT PRIMARY KEY, rollout_path TEXT, model TEXT)"
            )
            database.execute(
                "INSERT INTO threads (id, rollout_path, model) VALUES (?, ?, ?)",
                (SESSION_ID, str(self.rollout_path), model),
            )

    def write_rollout(self, *events: dict[str, object]) -> None:
        self.rollout_path.write_text(
            "".join(json.dumps(event) + "\n" for event in events),
            encoding="utf-8",
        )

    def run_countdown(
        self, agent: str = "codex", now_epoch: int = 1_800
    ) -> subprocess.CompletedProcess[str]:
        path = self.root / "api.sock"
        response = {
            "panes": [
                {
                    "pane_id": "w1:p1",
                    "agent": agent,
                    "agent_session": {"value": SESSION_ID},
                }
            ]
        }
        server = HerdrTestServer(path, lambda request: response)
        self.addCleanup(server.close)
        environment = {
            **os.environ,
            "CODEX_HOME": str(self.codex_home),
            "HERDR_ACTIVE_PANE_ID": "w1:p1",
            "HERDR_BIN_PATH": "/usr/bin/false",
            "HERDR_SOCKET_PATH": str(path),
            "CODEX_CACHE_COUNTDOWN_NOW_EPOCH": str(now_epoch),
        }
        return subprocess.run(
            [str(SCRIPT)],
            capture_output=True,
            check=False,
            env=environment,
            text=True,
        )

    def test_counts_down_from_latest_token_event(self) -> None:
        self.create_thread()
        self.write_rollout(
            {
                "timestamp": "1970-01-01T00:00:00Z",
                "type": "event_msg",
                "payload": {"type": "token_count"},
            },
            {
                "timestamp": "1970-01-01T00:15:00Z",
                "type": "event_msg",
                "payload": {"type": "token_count"},
            },
            {
                "timestamp": "1970-01-01T00:15:01Z",
                "type": "event_msg",
                "payload": {"type": "item_completed"},
            },
        )

        result = self.run_countdown(now_epoch=1_000)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "cache 28:20\n")

    def test_marks_an_expired_cache_as_cold(self) -> None:
        self.create_thread()
        self.write_rollout(
            {
                "timestamp": "1970-01-01T00:00:00Z",
                "type": "event_msg",
                "payload": {"type": "token_count"},
            },
        )

        result = self.run_countdown(now_epoch=1_801)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "cache cold\n")

    def test_hides_the_entry_for_non_codex_panes(self) -> None:
        result = self.run_countdown(agent="claude")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")

    def test_hides_the_entry_for_models_without_an_exact_ttl(self) -> None:
        self.create_thread(model="gpt-5.5")
        self.write_rollout(
            {
                "timestamp": "1970-01-01T00:15:00Z",
                "type": "event_msg",
                "payload": {"type": "token_count"},
            },
        )

        result = self.run_countdown(now_epoch=1_000)

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "")


if __name__ == "__main__":
    unittest.main()
