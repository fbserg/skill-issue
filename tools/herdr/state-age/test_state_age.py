#!/usr/bin/env python3
"""Tests for the Herdr sidebar state-age plugin."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path

import state_age
from socket_fixture import HerdrTestServer

SCRIPT = Path(__file__).with_name("state_age.py")


class FormatAgeTests(unittest.TestCase):
    def test_sessions_have_separate_state_and_daemon_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(os.environ, {"HERDR_PLUGIN_STATE_DIR": temporary, "HERDR_SOCKET_PATH": "/test/first.sock"}):
                first_state = state_age.state_path()
                first_pid = state_age.daemon_pid_path()
            with mock.patch.dict(os.environ, {"HERDR_PLUGIN_STATE_DIR": temporary, "HERDR_SOCKET_PATH": "/test/second.sock"}):
                self.assertNotEqual(state_age.state_path(), first_state)
                self.assertNotEqual(state_age.daemon_pid_path(), first_pid)

    def test_formats_compact_sidebar_ages(self) -> None:
        cases = {
            0: "<1m",
            59: "<1m",
            60: "1m",
            3_599: "59m",
            3_600: "1h",
            3_660: "1h1m",
            90_000: "1d1h",
        }
        for elapsed_seconds, expected in cases.items():
            with self.subTest(elapsed_seconds=elapsed_seconds):
                self.assertEqual(state_age.format_age(elapsed_seconds), expected)


class DesiredTokensTests(unittest.TestCase):
    def test_blocked_and_done_ages_show_immediately(self) -> None:
        self.assertEqual(
            state_age.desired_tokens("blocked", 20),
            {"blocked_age": "<1m", "symbol_blocked": "◆"},
        )
        self.assertEqual(
            state_age.desired_tokens("done", 7 * 60),
            {"done_age": "7m", "symbol_done": "●"},
        )

    def test_working_age_stays_hidden_until_fifteen_minutes(self) -> None:
        self.assertEqual(
            state_age.desired_tokens("working", 899), {"symbol_working": "◐"}
        )
        self.assertEqual(
            state_age.desired_tokens("working", 900),
            {"working_age": "15m", "symbol_working": "◐"},
        )

    def test_idle_and_unknown_ages_stay_hidden(self) -> None:
        self.assertEqual(state_age.desired_tokens("idle", 3_600), {"symbol_idle": "○"})
        self.assertEqual(
            state_age.desired_tokens("unknown", 3_600), {"symbol_unknown": "·"}
        )


class ReconcileTests(unittest.TestCase):
    def test_preserves_timestamp_until_state_changes(self) -> None:
        previous = {
            "w1:p1": {"status": "working", "since_epoch": 1_000.0},
        }
        panes = [
            {"pane_id": "w1:p1", "agent": "codex", "agent_status": "working"},
        ]

        reconciled = state_age.reconcile_states(previous, panes, now_epoch=2_000.0)

        self.assertEqual(reconciled["w1:p1"]["since_epoch"], 1_000.0)

    def test_resets_timestamp_on_change_and_discards_missing_panes(self) -> None:
        previous = {
            "w1:p1": {"status": "working", "since_epoch": 1_000.0},
            "w1:p2": {"status": "done", "since_epoch": 1_500.0},
        }
        panes = [
            {"pane_id": "w1:p1", "agent": "codex", "agent_status": "blocked"},
            {"pane_id": "w1:p3", "agent": "claude", "agent_status": "working"},
            {"pane_id": "w1:p4", "agent_status": "unknown"},
        ]

        reconciled = state_age.reconcile_states(previous, panes, now_epoch=2_000.0)

        self.assertEqual(
            reconciled,
            {
                "w1:p1": {"status": "blocked", "since_epoch": 2_000.0},
                "w1:p3": {"status": "working", "since_epoch": 2_000.0},
            },
        )


class EventTests(unittest.TestCase):
    def test_reads_status_change_event_envelope(self) -> None:
        event = {
            "event": "pane.agent_status_changed",
            "data": {"pane_id": "w3:p2", "agent_status": "blocked"},
        }
        self.assertEqual(
            state_age.status_change_from_event(event),
            ("w3:p2", "blocked"),
        )

    def test_rejects_incomplete_event(self) -> None:
        self.assertIsNone(state_age.status_change_from_event({"data": {}}))


class FakeHerdrIntegrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.requests = []
        self.panes = []
        self.socket_path = self.root / "api.sock"

        def handle(request):
            if request["method"] == "pane.list":
                return {"panes": self.panes}
            self.requests.append(request["params"])
            return {}

        self.server = HerdrTestServer(self.socket_path, handle)

    def tearDown(self) -> None:
        self.server.close()
        self.temporary_directory.cleanup()

    def environment(
        self, panes: list[dict[str, object]], now_epoch: float
    ) -> dict[str, str]:
        self.panes = panes
        environment = os.environ.copy()
        environment.update(
            {
                "HERDR_BIN_PATH": "/usr/bin/false",
                "HERDR_SOCKET_PATH": str(self.socket_path),
                "HERDR_PLUGIN_STATE_DIR": str(self.root / "state"),
                "HERDR_STATE_AGE_NOW_EPOCH": str(now_epoch),
                "HERDR_STATE_AGE_NO_DAEMON": "1",
            }
        )
        return environment

    def run_plugin(self, mode: str, environment: dict[str, str]) -> None:
        subprocess.run(
            [sys.executable, str(SCRIPT), mode],
            check=True,
            env=environment,
            capture_output=True,
            text=True,
        )

    def test_refresh_preserves_transition_time_and_crosses_working_threshold(
        self,
    ) -> None:
        panes = [
            {"pane_id": "w1:p1", "agent": "claude", "agent_status": "blocked"},
            {"pane_id": "w1:p2", "agent": "codex", "agent_status": "working"},
        ]
        environment = self.environment(panes, now_epoch=1_000)
        self.run_plugin("once", environment)

        environment["HERDR_STATE_AGE_NOW_EPOCH"] = "2000"
        self.run_plugin("once", environment)

        reports = [request["tokens"] for request in self.requests]
        self.assertEqual(reports[0]["symbol_blocked"], "◆")
        self.assertIsNone(reports[0]["symbol_working"])
        self.assertEqual(reports[1]["symbol_working"], "◐")
        self.assertIsNone(reports[1]["symbol_blocked"])
        self.assertEqual(reports[0]["blocked_age"], "<1m")
        self.assertIsNone(reports[1]["working_age"])
        self.assertEqual(reports[2]["blocked_age"], "16m")
        self.assertEqual(reports[3]["working_age"], "16m")

        saved = json.loads(
            next((self.root / "state").glob("*/state.json")).read_text(encoding="utf-8")
        )
        self.assertEqual(saved["panes"]["w1:p1"]["since_epoch"], 1_000.0)
        self.assertEqual(saved["panes"]["w1:p2"]["since_epoch"], 1_000.0)

    def test_event_resets_age_and_reports_new_state_immediately(self) -> None:
        panes = [
            {"pane_id": "w1:p1", "agent": "codex", "agent_status": "working"},
        ]
        environment = self.environment(panes, now_epoch=1_000)
        self.run_plugin("once", environment)

        environment["HERDR_STATE_AGE_NOW_EPOCH"] = "2_000"
        environment["HERDR_PLUGIN_EVENT_JSON"] = json.dumps(
            {
                "event": "pane.agent_status_changed",
                "data": {"pane_id": "w1:p1", "agent_status": "blocked"},
            }
        )
        self.run_plugin("event", environment)

        self.assertEqual(self.requests[-1]["tokens"]["blocked_age"], "<1m")
        saved = json.loads(
            next((self.root / "state").glob("*/state.json")).read_text(encoding="utf-8")
        )
        self.assertEqual(
            saved["panes"]["w1:p1"], {"since_epoch": 2_000.0, "status": "blocked"}
        )


if __name__ == "__main__":
    unittest.main()
