from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import anchors


class AnchorsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.environment = patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/test/default.sock", "HERDR_PLUGIN_STATE_DIR": self.temporary.name})
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.workspace = {"workspace_id": "w1", "label": "example"}
        self.tab = {"workspace_id": "w1", "tab_id": "w1:t1"}
        self.pane = {"workspace_id": "w1", "tab_id": "w1:t1", "pane_id": "w1:p1", "cwd": self.temporary.name}

    def state(self) -> dict:
        with anchors.locked_state() as (_, state):
            return state

    def write(self, state: dict) -> None:
        with anchors.locked_state() as (path, _):
            anchors.save(path, state)

    def rpc(self, method: str, params: dict) -> dict:
        return {
            "workspace.list": {"workspaces": [self.workspace]},
            "pane.list": {"panes": [self.pane]},
            "tab.list": {"tabs": [self.tab]},
        }.get(method, {})

    def test_unenrolled_sessions_do_nothing(self) -> None:
        with patch.object(anchors, "rpc") as rpc:
            anchors.reconcile("sync")
        rpc.assert_not_called()

    def test_sessions_with_same_workspace_ids_have_separate_state(self) -> None:
        self.write({"projects": {"w1": {"cwd": "/a"}}, "auto": False, "released": []})
        with patch.dict(os.environ, {"HERDR_SOCKET_PATH": "/test/other.sock"}):
            self.assertEqual(self.state()["projects"], {})
        self.assertIn("w1", self.state()["projects"])

    def test_protect_adopts_only_empty_shell(self) -> None:
        with patch.object(anchors, "rpc", side_effect=self.rpc) as rpc, patch.object(anchors, "empty_shell", return_value=True), patch.object(anchors, "launch") as launch:
            anchors.reconcile("protect", "w1")
        launch.assert_called_once_with("w1:p1")
        self.assertEqual(self.state()["projects"]["w1"]["pane_id"], "w1:p1")
        self.assertTrue(any(c.args == ("tab.move", {"tab_id": "w1:t1", "insert_index": 0}) for c in rpc.call_args_list))

    def test_busy_first_tab_gets_a_separate_anchor(self) -> None:
        new_pane = dict(self.pane, pane_id="w1:p2", tab_id="w1:t2")
        def rpc(method: str, params: dict) -> dict:
            return {"root_pane": new_pane} if method == "tab.create" else self.rpc(method, params)
        with patch.object(anchors, "rpc", side_effect=rpc), patch.object(anchors, "empty_shell", return_value=False), patch.object(anchors, "launch") as launch:
            anchors.reconcile("protect", "w1")
        launch.assert_called_once_with("w1:p2")

    def test_live_anchor_is_not_relaunched(self) -> None:
        self.write({"projects": {"w1": {"cwd": self.temporary.name, "label": "old", "pane_id": "w1:p1"}}, "auto": False, "released": []})
        with patch.object(anchors, "rpc", side_effect=self.rpc), patch.object(anchors, "foreground", return_value=(True, False)), patch.object(anchors, "launch") as launch:
            anchors.reconcile("sync")
        launch.assert_not_called()
        self.assertEqual(self.state()["projects"]["w1"]["label"], "example")

    def test_restored_shell_is_replaced_with_inert_process(self) -> None:
        self.write({"projects": {"w1": {"cwd": self.temporary.name, "label": "example", "pane_id": "w1:p1"}}, "auto": False, "released": []})
        with patch.object(anchors, "rpc", side_effect=self.rpc), patch.object(anchors, "foreground", return_value=(False, True)), patch.object(anchors, "launch") as launch:
            anchors.reconcile("sync")
        launch.assert_called_once_with("w1:p1")

    def test_release_survives_auto_enrollment(self) -> None:
        self.pane["cwd"] = str(Path.home() / "projects/example")
        self.write({"projects": {"w1": {}}, "auto": True, "released": []})
        with patch.object(anchors, "rpc", side_effect=self.rpc), patch.object(anchors, "launch") as launch:
            anchors.reconcile("release", "w1")
            anchors.reconcile("sync")
        launch.assert_not_called()
        self.assertEqual(self.state()["projects"], {})

    def test_missing_directory_does_not_create_a_wrong_project(self) -> None:
        self.write({"projects": {"gone": {"cwd": "/nonexistent-herdr-anchor-project", "label": "gone"}}, "auto": False, "released": []})
        with patch.object(anchors, "rpc", side_effect=self.rpc) as rpc:
            with self.assertRaises(FileNotFoundError):
                anchors.reconcile("sync")
        self.assertFalse(any(c.args[0] == "workspace.create" for c in rpc.call_args_list))

    def test_empty_shell_rejects_command_history_and_agents(self) -> None:
        with patch.object(anchors, "foreground", return_value=(False, True)), patch.object(anchors, "rpc", return_value={"read": {"text": "user$ important\nuser$ "}}):
            self.assertFalse(anchors.empty_shell(self.pane))
        self.assertFalse(anchors.empty_shell(dict(self.pane, agent="codex")))


if __name__ == "__main__":
    unittest.main()
