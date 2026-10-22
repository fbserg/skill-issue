from __future__ import annotations

import base64
import io
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import herdr_share


class HerdrShareTests(unittest.TestCase):
    def test_same_mode_share_for_a_different_pane_is_replaced(self) -> None:
        existing = {"mode": "control", "pane_id": "old-pane", "socket_path": "/same.sock", "url": "old-url", "username": "as", "password": "old-password"}
        for requested in ("explicit-new-pane", None):
            with self.subTest(requested=requested), tempfile.TemporaryDirectory() as temporary:
                with mock.patch.dict(os.environ, {"HERDR_SHARE_STATE_DIR": temporary, "HERDR_SOCKET_PATH": "/same.sock"}, clear=True), mock.patch.object(herdr_share, "load_state", return_value=existing), mock.patch.object(herdr_share, "share_is_live", return_value=True), mock.patch.object(herdr_share, "resolve_pane", return_value="new-pane") as resolve, mock.patch.object(herdr_share, "stop_state") as stop, mock.patch.object(herdr_share, "require_binary", side_effect=RuntimeError("replacement reached")):
                    with self.assertRaisesRegex(RuntimeError, "replacement reached"):
                        herdr_share.start_share("control", requested, 600)
                    resolve.assert_called_once_with(requested)
                    stop.assert_called_once_with(existing)

    def test_same_mode_same_pane_reuses_invite_after_validation(self) -> None:
        existing = {"mode": "view", "pane_id": "same-pane", "socket_path": "/same.sock", "url": "old-url", "username": "as", "password": "as"}
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(os.environ, {"HERDR_SHARE_STATE_DIR": temporary, "HERDR_SOCKET_PATH": "/same.sock"}, clear=True), mock.patch.object(herdr_share, "load_state", return_value=existing), mock.patch.object(herdr_share, "share_is_live", return_value=True), mock.patch.object(herdr_share, "resolve_pane", return_value="same-pane") as resolve, mock.patch.object(herdr_share, "copy_invite"), mock.patch.object(sys, "stdout"), mock.patch.object(herdr_share, "require_binary") as binary:
                herdr_share.start_share("view", "same-pane", 600)
                resolve.assert_called_once_with("same-pane")
                binary.assert_not_called()

    def test_same_pane_id_in_another_session_is_not_reused(self) -> None:
        existing = {"mode": "control", "pane_id": "w1:p1", "socket_path": "/old.sock", "url": "old-url", "username": "as", "password": "old-password"}
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(os.environ, {"HERDR_SHARE_STATE_DIR": temporary, "HERDR_SOCKET_PATH": "/new.sock"}, clear=True), mock.patch.object(herdr_share, "load_state", return_value=existing), mock.patch.object(herdr_share, "share_is_live", return_value=True), mock.patch.object(herdr_share, "resolve_pane", return_value="w1:p1"), mock.patch.object(herdr_share, "stop_state") as stop, mock.patch.object(herdr_share, "require_binary", side_effect=RuntimeError("replacement reached")):
                with self.assertRaisesRegex(RuntimeError, "replacement reached"):
                    herdr_share.start_share("control", "w1:p1", 600)
                stop.assert_called_once_with(existing)

    def test_cli_without_socket_context_uses_server_status(self) -> None:
        existing = {"mode": "view", "pane_id": "same-pane", "socket_path": "/status.sock", "url": "old-url", "username": "as", "password": "as"}
        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(os.environ, {"HERDR_SHARE_STATE_DIR": temporary}, clear=True), mock.patch.object(herdr_share, "load_state", return_value=existing), mock.patch.object(herdr_share, "share_is_live", return_value=True), mock.patch.object(herdr_share, "resolve_pane", return_value="same-pane"), mock.patch.object(herdr_share, "run_herdr", return_value={"socket": "/status.sock"}) as run, mock.patch.object(herdr_share, "copy_invite"), mock.patch.object(sys, "stdout"):
                herdr_share.start_share("view", "same-pane", 600)
                run.assert_called_once_with("status", "server", "--json")

    def test_cli_and_plugin_action_share_one_state_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            environment = {
                "HERDR_PLUGIN_STATE_DIR": "/tmp/wrong-plugin-specific-state",
                "HERDR_SHARE_STATE_DIR": temporary,
            }
            with mock.patch.dict(os.environ, environment, clear=True):
                self.assertEqual(herdr_share.state_dir(), Path(temporary))

    def test_context_pane_wins_without_querying_global_focus(self) -> None:
        with mock.patch.dict(os.environ, {"HERDR_PANE_ID": "w2:p3"}, clear=True):
            with mock.patch.object(herdr_share, "run_herdr") as run_herdr:
                self.assertEqual(herdr_share.resolve_pane(None), "w2:p3")
        run_herdr.assert_called_once_with("pane", "get", "w2:p3")

    def test_context_json_supplies_pane(self) -> None:
        context = json.dumps({"context": {"focused_pane_id": "w4:p9"}})
        with mock.patch.dict(
            os.environ, {"HERDR_PLUGIN_CONTEXT_JSON": context}, clear=True
        ):
            self.assertEqual(herdr_share.pane_from_context(), "w4:p9")

    def test_homebrew_binary_resolves_when_plugin_path_is_minimal(self) -> None:
        with mock.patch.object(herdr_share.shutil, "which", return_value=None):
            with mock.patch.object(Path, "is_file", return_value=True):
                with mock.patch.object(herdr_share.os, "access", return_value=True):
                    self.assertEqual(
                        herdr_share.require_binary("ttyd"), "/opt/homebrew/bin/ttyd"
                    )

    def test_rendered_invite_contains_only_needed_share_details(self) -> None:
        invite = herdr_share.render_invite(
            {
                "url": "https://quiet-dog.trycloudflare.com",
                "username": herdr_share.SHARE_USERNAME,
                "password": herdr_share.SHARE_PASSWORD,
                "mode": "view",
            }
        )
        self.assertEqual(
            invite,
            "https://quiet-dog.trycloudflare.com\n"
            "Username: as\n"
            "Password: as\n"
            "VIEW ONLY. Viewers cannot type. This link expires automatically.",
        )

    def test_control_invite_warns_that_the_browser_can_type(self) -> None:
        invite = herdr_share.render_invite(
            {"url": "u", "username": "as", "password": "p", "mode": "control"}
        )
        self.assertIn("FULL CONTROL", invite)
        self.assertIn("can type into the pane", invite)

    def test_view_ttyd_is_read_only_and_control_ttyd_is_writable(self) -> None:
        commands: dict[str, list[str]] = {}
        for mode in ("view", "control"):
            commands[mode] = self._ttyd_command_for(mode)
        self.assertNotIn("-W", commands["view"])
        self.assertIn("observe", commands["view"])
        self.assertIn("as", commands["view"][commands["view"].index("-c") + 1])
        self.assertIn("-W", commands["control"])
        self.assertIn("bridge", commands["control"])
        self.assertEqual("1", commands["control"][commands["control"].index("-m") + 1])
        credential = commands["control"][commands["control"].index("-c") + 1]
        self.assertTrue(credential.startswith("as:"))
        self.assertNotEqual(credential, "as:as")

    def _ttyd_command_for(self, mode: str) -> list[str]:
        """Drive start_share until ttyd is launched, then abort. Returns ttyd argv."""
        captured: list[list[str]] = []

        def popen(command: list[str], **_: object) -> mock.Mock:
            captured.append(command)
            raise RuntimeError("stop after ttyd launch")

        with tempfile.TemporaryDirectory() as temporary:
            with mock.patch.dict(
                os.environ, {"HERDR_SHARE_STATE_DIR": temporary, "HERDR_SOCKET_PATH": "/test.sock"}, clear=True
            ):
                with mock.patch.object(herdr_share, "resolve_pane", return_value="w1:p1"):
                    with mock.patch.object(
                        herdr_share, "require_binary", side_effect=lambda name: name
                    ):
                        with mock.patch.object(herdr_share, "viewer_page_path", return_value=Path(temporary) / "viewer.html"), mock.patch.object(subprocess, "Popen", side_effect=popen):
                            with self.assertRaises(RuntimeError):
                                herdr_share.start_share(mode, None, 600)
        self.assertEqual(len(captured), 1)
        return captured[0]

    def test_bridge_forwards_keystrokes_as_terminal_input_then_releases(self) -> None:
        process = mock.Mock()
        process.stdin = io.BytesIO()
        read_fd, write_fd = os.pipe()
        os.write(write_fd, b"ls\r")
        os.close(write_fd)
        holder = herdr_share.StreamHolder()
        holder.process = process
        herdr_share.forward_keystrokes(holder, read_fd)
        os.close(read_fd)
        lines = [json.loads(line) for line in process.stdin.getvalue().splitlines()]
        self.assertEqual(
            lines,
            [
                {"type": "terminal.input", "bytes": base64.b64encode(b"ls\r").decode()},
                {"type": "terminal.release"},
            ],
        )
        process.terminate.assert_called_once_with()
        self.assertTrue(holder.viewer_closed.is_set())

    def test_control_password_changes_for_each_share(self) -> None:
        first = self._ttyd_command_for("control")
        second = self._ttyd_command_for("control")
        self.assertNotEqual(first[first.index("-c") + 1], second[second.index("-c") + 1])

    def test_view_mode_keeps_fixed_credentials(self) -> None:
        self.assertEqual(herdr_share.SHARE_USERNAME, "as")
        self.assertEqual(herdr_share.SHARE_PASSWORD, "as")

    def test_state_file_is_private(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with mock.patch.object(herdr_share, "state_dir", return_value=root):
                herdr_share.save_state({"pane_id": "w1:p1"})
            mode = stat.S_IMODE((root / "share.json").stat().st_mode)
        self.assertEqual(mode, 0o600)

    def test_observer_decodes_only_terminal_frames(self) -> None:
        terminal_bytes = b"\x1b[2J hi"
        frames = (
            b"\n".join(
                (
                    json.dumps({"type": "other", "bytes": "aWdub3Jl"}).encode(),
                    json.dumps(
                        {
                            "type": "terminal.frame",
                            "bytes": base64.b64encode(terminal_bytes).decode(),
                        }
                    ).encode(),
                )
            )
            + b"\n"
        )
        process = mock.Mock()
        process.stdout = io.BytesIO(frames)
        process.wait.return_value = 0
        output = io.BytesIO()
        stdout = mock.Mock()
        stdout.buffer = output
        with mock.patch.object(sys, "stdout", stdout):
            self.assertFalse(herdr_share.pump_frames(process))
        self.assertEqual(output.getvalue(), terminal_bytes)
        process.terminate.assert_called_once_with()

    def test_view_mode_uses_an_observe_stream(self) -> None:
        with mock.patch.object(herdr_share, "stream_pane") as stream:
            herdr_share.observe_pane("w1:p1")
        stream.assert_called_once_with("observe", "w1:p1")

    def test_tunnel_url_parser_reads_cloudflared_log(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            log_path = Path(temporary) / "cloudflared.log"
            log_path.write_text("INF https://three-words.trycloudflare.com ready\n")
            process = mock.Mock()
            process.poll.return_value = None
            self.assertEqual(
                herdr_share.wait_for_tunnel_url(log_path, process),
                "https://three-words.trycloudflare.com",
            )

    def test_expiry_revokes_only_its_own_generation(self) -> None:
        with mock.patch.object(herdr_share.time, "sleep") as sleep:
            with mock.patch.object(herdr_share, "stop_share") as stop_share:
                herdr_share.expire_share("generation-1", 600)
        sleep.assert_called_once_with(600)
        stop_share.assert_called_once_with(expected_generation="generation-1")


if __name__ == "__main__":
    unittest.main()
