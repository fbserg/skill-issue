from __future__ import annotations

import copy
import json
import os
import unittest
from unittest.mock import patch

import undo

SESSION = {"agent": "codex", "kind": "id", "value": "test-session"}
PANE = {
    "pane_id": "w1:p1",
    "terminal_id": "term1",
    "workspace_id": "w1",
    "cwd": "/tmp",
    "agent": "codex",
    "agent_session": SESSION,
}
WORKSPACES = [{"workspace_id": "w1", "label": "project"}]


class UndoTest(unittest.TestCase):
    def setUp(self) -> None:
        self.state = {"live": {}, "closed": []}

    def capture(self, panes: list[dict], closed: bool = False) -> None:
        undo.reconcile(self.state, panes, WORKSPACES, record_closed=closed)

    def test_capture_then_close_retains_identity_and_project(self) -> None:
        self.capture([PANE])
        self.capture([], True)
        self.assertEqual(self.state["closed"][0]["session"], SESSION)
        self.assertEqual(self.state["closed"][0]["workspace_label"], "project")
        self.assertEqual(self.state["live"], {})

    def test_duplicate_close_events_do_not_duplicate_history(self) -> None:
        self.capture([PANE])
        self.capture([], True)
        self.capture([], True)
        self.assertEqual(len(self.state["closed"]), 1)

    def test_shell_after_agent_exit_retains_last_session_until_pane_closes(
        self,
    ) -> None:
        self.capture([PANE])
        self.capture(
            [{k: v for k, v in PANE.items() if k not in ("agent", "agent_session")}]
        )
        self.capture([], True)
        self.assertEqual(self.state["closed"][0]["session"], SESSION)

    def test_startup_does_not_mark_stale_panes_as_closed(self) -> None:
        self.capture([PANE])
        self.capture([])
        self.assertEqual(self.state, {"live": {}, "closed": []})

    def test_new_session_replaces_previous_session(self) -> None:
        self.capture([PANE])
        pane = copy.deepcopy(PANE)
        pane["agent_session"]["value"] = "new-session"
        self.capture([pane])
        self.capture([], True)
        self.assertEqual(self.state["closed"][0]["session"]["value"], "new-session")

    def test_moved_pane_does_not_look_like_a_closure(self) -> None:
        self.capture([PANE])
        pane = dict(PANE, pane_id="w2:p2", workspace_id="w2")
        self.capture([pane], True)
        self.assertEqual(self.state["closed"], [])

    def test_unsupported_sessions_and_plain_shells_are_not_recorded(self) -> None:
        pane = dict(PANE, agent_session={"agent": "other", "kind": "id", "value": "x"})
        self.capture([pane, {"pane_id": "w1:p2", "terminal_id": "term2"}])
        self.assertEqual(self.state["live"], {})

    def test_history_is_bounded(self) -> None:
        for i in range(60):
            self.capture([dict(PANE, terminal_id=f"term{i}")])
            self.capture([], True)
        self.assertEqual(len(self.state["closed"]), 50)
        self.assertEqual(self.state["closed"][-1]["terminal_id"], "term59")

    def test_resume_argv_never_interprets_session_as_shell(self) -> None:
        self.assertEqual(
            undo.resume_argv(
                {"agent": "claude", "kind": "id", "value": "a; touch bad"}
            ),
            ["claude", "--resume", "a; touch bad"],
        )
        self.assertEqual(undo.resume_argv(SESSION), ["codex", "--no-daemon", "resume", "test-session"])

    def test_restore_reuses_project_and_pops_only_after_success(self) -> None:
        self.capture([PANE])
        self.capture([], True)
        with patch.object(
            undo,
            "rpc",
            return_value={
                "root_pane": dict(PANE, pane_id="w1:p2", terminal_id="term2")
            },
        ) as rpc:
            undo.restore(self.state, [], WORKSPACES)
        method, params = rpc.call_args.args
        self.assertEqual(method, "tab.create")
        self.assertEqual(params["workspace_id"], "w1")
        self.assertEqual(json.loads(params["env"]["HERDR_UNDO_SESSION"]), SESSION)
        self.assertEqual(self.state["closed"], [])

    def test_restored_session_can_be_closed_and_restored_again(self) -> None:
        self.capture([PANE])
        self.capture([], True)
        replacement = dict(PANE, pane_id="w1:p2", terminal_id="term2")
        with patch.object(undo, "rpc", return_value={"root_pane": replacement}):
            undo.restore(self.state, [], WORKSPACES)
        self.capture([{k: v for k, v in replacement.items() if k != "agent_session"}])
        self.capture([], True)
        self.assertEqual(self.state["closed"][0]["session"], SESSION)

    def test_missing_workspace_is_recreated(self) -> None:
        self.capture([PANE])
        self.capture([], True)
        with patch.object(undo, "rpc", return_value={"root_pane": PANE}) as rpc:
            undo.restore(self.state, [], [])
        self.assertEqual(rpc.call_args.args[0], "workspace.create")
        self.assertEqual(rpc.call_args.args[1]["label"], "project")

    def test_existing_session_is_focused_instead_of_duplicated(self) -> None:
        self.capture([PANE])
        self.capture([], True)
        with patch.object(undo, "rpc", return_value={}) as rpc:
            undo.restore(self.state, [dict(PANE, pane_id="w1:p9")], WORKSPACES)
        rpc.assert_called_once_with("pane.focus", {"pane_id": "w1:p9"})

    def test_failed_creation_preserves_history(self) -> None:
        self.capture([PANE])
        self.capture([], True)
        with (
            patch.object(undo, "rpc", side_effect=RuntimeError("server unavailable")),
            self.assertRaisesRegex(RuntimeError, "server unavailable"),
        ):
            undo.restore(self.state, [], WORKSPACES)
        self.assertEqual(len(self.state["closed"]), 1)

    def test_missing_directory_preserves_history(self) -> None:
        self.capture([dict(PANE, cwd="/does-not-exist-undo-test")])
        self.capture([], True)
        with self.assertRaises(FileNotFoundError):
            undo.restore(self.state, [], WORKSPACES)
        self.assertEqual(len(self.state["closed"]), 1)

    def test_launch_clears_one_shot_environment(self) -> None:
        with (
            patch.dict(os.environ, HERDR_UNDO_SESSION=json.dumps(SESSION)),
            patch.object(os, "execvpe") as execute,
        ):
            undo.launch()
            self.assertNotIn("HERDR_UNDO_SESSION", execute.call_args.args[2])
        self.assertEqual(execute.call_args.args[1][1:], ["--no-daemon", "resume", "test-session"])


if __name__ == "__main__":
    unittest.main()
