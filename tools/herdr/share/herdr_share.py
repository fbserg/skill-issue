#!/usr/bin/env python3
"""Publish one Herdr pane through a temporary browser terminal.

Two modes, one share at a time:
  view     read-only. Viewers see the pane, cannot type. Fixed login as/as.
  control  read-write. The browser types into the pane. Random password per share.
"""

from __future__ import annotations

import argparse
import base64
import fcntl
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import struct
import subprocess
import sys
import termios
import threading
import time
import tty
from typing import Any, Iterator
import urllib.request


DEFAULT_TTL_SECONDS = 3 * 60 * 60
MAX_TTL_SECONDS = 24 * 60 * 60
SHARE_USERNAME = "as"
SHARE_PASSWORD = "as"
MODE_SUMMARY = {
    "view": "VIEW ONLY. Viewers cannot type. This link expires automatically.",
    "control": "FULL CONTROL. Anyone with this link can type into the pane. This link expires automatically.",
}
TUNNEL_URL_PATTERN = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")
SIZE_POLL_SECONDS = 2.0
# Private OSC: the stream bridge tells the browser the owner's grid, the page scales to it.
SIZE_OSC = 7777
VIEWER_PAGE_PATCH = """
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>html,body{overscroll-behavior:none}</style>
<script>
(function () {
  var size = null;
  function fit() {
    var t = window.term;
    if (!t || !size) return;
    var cell = t._core._renderService.dimensions.css.cell;
    var font = t.options.fontSize;
    if (!cell.width || !font) return;
    var w = window.innerWidth, h = window.innerHeight;
    var next = Math.min(w / (size.cols * cell.width / font), h / (size.rows * cell.height / font));
    next = Math.max(4, Math.floor(next * 2) / 2);
    if (next !== font) t.options.fontSize = next;
    t.resize(size.cols, size.rows);
  }
  function install() {
    var t = window.term;
    if (!t) { setTimeout(install, 50); return; }
    t.parser.registerOscHandler(%(osc)d, function (data) {
      var parts = data.split(";");
      size = { cols: +parts[0], rows: +parts[1] };
      fit();
      return true;
    });
    // ttyd's own FitAddon still runs on window resize and font changes; drop its resizes.
    var resize = t.resize.bind(t);
    t.resize = function (cols, rows) {
      if (size && (cols !== size.cols || rows !== size.rows)) return;
      resize(cols, rows);
    };
    t.fit = fit;
    window.addEventListener("resize", fit);
  }
  install();
})();
</script>
""" % {"osc": SIZE_OSC}


def state_dir() -> Path:
    configured = os.environ.get("HERDR_SHARE_STATE_DIR")
    path = Path(configured) if configured else Path.home() / ".local/state/herdr-share"
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.chmod(0o700)
    return path


def state_path() -> Path:
    return state_dir() / "share.json"


class StateLock:
    def __enter__(self) -> None:
        self.file = (state_dir() / "share.lock").open("a+")
        fcntl.flock(self.file, fcntl.LOCK_EX)

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        fcntl.flock(self.file, fcntl.LOCK_UN)
        self.file.close()


def load_state() -> dict[str, Any] | None:
    path = state_path()
    if not path.exists():
        return None
    value = json.loads(path.read_text())
    if not isinstance(value, dict):
        raise ValueError(f"invalid share state: {path}")
    return value


def save_state(state: dict[str, Any]) -> None:
    path = state_path()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n")
    temporary.chmod(0o600)
    temporary.replace(path)


def remove_state() -> None:
    state_path().unlink(missing_ok=True)


def require_binary(name: str) -> str:
    path = shutil.which(name)
    if path:
        return path
    for directory in (
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path.home() / ".local/bin",
    ):
        candidate = directory / name
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return str(candidate)
    raise RuntimeError(f"required command is missing: {name}")


def herdr_binary() -> str:
    return os.environ.get("HERDR_BIN_PATH") or require_binary("herdr")


def run_herdr(*args: str) -> dict[str, Any]:
    result = subprocess.run(
        [herdr_binary(), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise TypeError("Herdr returned a non-object response")
    return value


def nested_objects(value: Any) -> Iterator[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from nested_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from nested_objects(child)


def pane_from_context() -> str | None:
    for name in ("HERDR_ACTIVE_PANE_ID", "HERDR_PANE_ID"):
        value = os.environ.get(name)
        if value:
            return value

    raw_context = os.environ.get("HERDR_PLUGIN_CONTEXT_JSON")
    if not raw_context:
        return None
    for item in nested_objects(json.loads(raw_context)):
        for key in ("pane_id", "focused_pane_id"):
            pane_id = item.get(key)
            if isinstance(pane_id, str) and pane_id:
                return pane_id
    return None


def resolve_pane(requested: str | None) -> str:
    pane_id = requested or pane_from_context()
    if not pane_id:
        response = run_herdr("pane", "current")
        pane_id = response["result"]["pane"]["pane_id"]
    run_herdr("pane", "get", pane_id)
    return pane_id


def process_command(pid: int) -> str | None:
    if pid <= 0:
        return None
    result = subprocess.run(
        ["ps", "-p", str(pid), "-o", "command="],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def process_matches(pid: int, expected: str) -> bool:
    command = process_command(pid)
    return command is not None and expected in command


def share_is_live(state: dict[str, Any]) -> bool:
    return process_matches(int(state["ttyd_pid"]), "ttyd") and process_matches(
        int(state["tunnel_pid"]), "cloudflared"
    )


def terminate_process_group(pid: int, expected: str) -> None:
    if pid == os.getpid() or not process_matches(pid, expected):
        return
    process_group = os.getpgid(pid)
    os.killpg(process_group, signal.SIGTERM)
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        if not process_matches(pid, expected):
            return
        time.sleep(0.05)
    if process_matches(pid, expected):
        os.killpg(process_group, signal.SIGKILL)


def stop_state(state: dict[str, Any]) -> None:
    terminate_process_group(int(state.get("expire_pid") or 0), "herdr_share.py")
    terminate_process_group(int(state.get("tunnel_pid") or 0), "cloudflared")
    terminate_process_group(int(state.get("ttyd_pid") or 0), "ttyd")
    remove_state()


def wait_for_port(port: int, process: subprocess.Popen[bytes]) -> None:
    deadline = time.monotonic() + 8
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError("ttyd exited before it opened the viewer port")
        with socket.socket() as probe:
            probe.settimeout(0.2)
            if probe.connect_ex(("127.0.0.1", port)) == 0:
                return
        time.sleep(0.1)
    raise RuntimeError(f"ttyd did not open 127.0.0.1:{port}")


def wait_for_tunnel_url(log_path: Path, process: subprocess.Popen[bytes]) -> str:
    deadline = time.monotonic() + 25
    while time.monotonic() < deadline:
        if log_path.exists():
            match = TUNNEL_URL_PATTERN.search(log_path.read_text(errors="replace"))
            if match:
                return match.group(0)
        if process.poll() is not None:
            raise RuntimeError(
                f"cloudflared exited before it issued a URL; see {log_path}"
            )
        time.sleep(0.2)
    raise RuntimeError(f"cloudflared did not issue a URL; see {log_path}")


def viewer_page_path(ttyd: str) -> Path:
    """ttyd's bundled index.html plus the fit-to-owner-grid patch, cached per ttyd version."""
    version = subprocess.run([ttyd, "--version"], capture_output=True, text=True, check=True)
    tag = re.sub(r"[^A-Za-z0-9.]+", "-", version.stdout.strip())
    page = state_dir() / f"viewer-{tag}.html"
    if page.exists():
        return page
    port = available_port()
    with subprocess.Popen(
        [ttyd, "-i", "127.0.0.1", "-p", str(port), "true"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    ) as probe:
        try:
            wait_for_port(port, probe)
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as response:
                stock = response.read().decode()
        finally:
            probe.terminate()
    if stock.count("</body>") != 1:
        raise RuntimeError("ttyd index.html has no single </body>; cannot patch the viewer page")
    page.write_text(stock.replace("</body>", VIEWER_PAGE_PATCH + "</body>"))
    return page


def available_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return int(listener.getsockname()[1])


def notify(title: str, body: str) -> None:
    subprocess.run(
        [
            herdr_binary(),
            "notification",
            "show",
            title,
            "--body",
            body,
            "--sound",
            "none",
        ],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def copy_invite(invite: str) -> bool:
    pbcopy = shutil.which("pbcopy")
    if not pbcopy:
        return False
    subprocess.run([pbcopy], input=invite, check=True, text=True)
    return True


def render_invite(state: dict[str, Any]) -> str:
    return "\n".join(
        (
            str(state["url"]),
            f"Username: {state['username']}",
            f"Password: {state['password']}",
            MODE_SUMMARY[str(state["mode"])],
        )
    )


def start_share(mode: str, pane: str | None, ttl_seconds: int) -> None:
    if ttl_seconds < 60 or ttl_seconds > MAX_TTL_SECONDS:
        raise ValueError(f"TTL must be between 60 and {MAX_TTL_SECONDS} seconds")

    with StateLock():
        pane_id = resolve_pane(pane)
        socket_path = os.environ.get("HERDR_SOCKET_PATH")
        if not socket_path:
            socket_path = run_herdr("status", "server", "--json")["socket"]
        socket_path = str(Path(socket_path).resolve())
        existing = load_state()
        if existing and share_is_live(existing) and existing["mode"] == mode and existing["pane_id"] == pane_id and existing.get("socket_path") == socket_path:
            invite = render_invite(existing)
            copy_invite(invite)
            print(invite)
            print(f"Already active ({mode}) for pane {existing['pane_id']}.")
            return
        if existing:
            stop_state(existing)

        ttyd = require_binary("ttyd")
        cloudflared = require_binary("cloudflared")
        port = available_port()
        username = SHARE_USERNAME
        password = SHARE_PASSWORD if mode == "view" else secrets.token_urlsafe(16)
        generation = secrets.token_hex(16)
        logs_dir = state_dir() / "logs"
        logs_dir.mkdir(mode=0o700, exist_ok=True)
        ttyd_log = logs_dir / "ttyd.log"
        tunnel_log = logs_dir / "cloudflared.log"
        script_path = Path(__file__).resolve()
        viewer_page = viewer_page_path(ttyd)

        ttyd_command = [
            ttyd,
            "-i",
            "127.0.0.1",
            "-p",
            str(port),
            "-c",
            f"{username}:{password}",
            "-O",
            "-I",
            str(viewer_page),
            "-t",
            "disableResizeOverlay=true",
            "-m",
            "5" if mode == "view" else "1",
            *(["-W"] if mode == "control" else []),
            sys.executable,
            str(script_path),
            "observe" if mode == "view" else "bridge",
            pane_id,
        ]
        cloudflared_command = [
            cloudflared,
            "tunnel",
            "--no-autoupdate",
            # QUIC (udp 7844) is blocked on some networks; the tunnel then registers and dies.
            "--protocol",
            "http2",
            "--url",
            f"http://127.0.0.1:{port}",
        ]

        ttyd_process: subprocess.Popen[bytes] | None = None
        tunnel_process: subprocess.Popen[bytes] | None = None
        try:
            with ttyd_log.open("wb") as ttyd_output:
                ttyd_process = subprocess.Popen(
                    ttyd_command,
                    stdin=subprocess.DEVNULL,
                    stdout=ttyd_output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            wait_for_port(port, ttyd_process)

            with tunnel_log.open("wb") as tunnel_output:
                tunnel_process = subprocess.Popen(
                    cloudflared_command,
                    stdin=subprocess.DEVNULL,
                    stdout=tunnel_output,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            url = wait_for_tunnel_url(tunnel_log, tunnel_process)
            expires_at = int(time.time()) + ttl_seconds
            state: dict[str, Any] = {
                "expires_at": expires_at,
                "generation": generation,
                "mode": mode,
                "pane_id": pane_id,
                "socket_path": socket_path,
                "password": password,
                "port": port,
                "started_at": int(time.time()),
                "ttyd_pid": ttyd_process.pid,
                "tunnel_pid": tunnel_process.pid,
                "url": url,
                "username": username,
            }
            save_state(state)
            expire_process = subprocess.Popen(
                [
                    sys.executable,
                    str(script_path),
                    "_expire",
                    generation,
                    str(ttl_seconds),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
            state["expire_pid"] = expire_process.pid
            save_state(state)
        except BaseException:
            if tunnel_process is not None:
                terminate_process_group(tunnel_process.pid, "cloudflared")
            if ttyd_process is not None:
                terminate_process_group(ttyd_process.pid, "ttyd")
            remove_state()
            raise

        invite = render_invite(state)
        copied = copy_invite(invite)
        print(invite)
        print(f"Mode: {mode}")
        print(f"Pane: {pane_id}")
        print(
            f"Expires: {time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(expires_at))}"
        )
        print("Copied to clipboard." if copied else "Clipboard unavailable.")
        notify(
            f"Pane shared: {mode.upper()}",
            "Invite copied to clipboard" if copied else url,
        )


def stop_share(expected_generation: str | None = None) -> None:
    with StateLock():
        state = load_state()
        if not state:
            if expected_generation is None:
                print("No Herdr pane share is active.")
            return
        if (
            expected_generation is not None
            and state.get("generation") != expected_generation
        ):
            return
        stop_state(state)
    if expected_generation is None:
        print(f"Stopped {state['mode']} share for pane {state['pane_id']}.")
        notify("Pane share stopped", str(state["pane_id"]))


def show_status() -> None:
    with StateLock():
        state = load_state()
        if not state:
            print("No Herdr pane share is active.")
            return
        if not share_is_live(state):
            print(
                f"Stale share state for pane {state['pane_id']}; run `herdr-share stop`."
            )
            return
        print(render_invite(state))
        print(f"Mode: {state['mode']}")
        print(f"Pane: {state['pane_id']}")
        print(
            f"Expires: {time.strftime('%Y-%m-%d %H:%M:%S %Z', time.localtime(state['expires_at']))}"
        )


def owner_size(pane_id: str) -> tuple[int, int]:
    """(cols, rows) of the pane's real pty, read from the shell's controlling tty."""
    info = run_herdr("pane", "process-info", "--pane", pane_id)["result"]["process_info"]
    shell_pid = int(info["shell_pid"])
    tty_name = subprocess.run(
        ["ps", "-o", "tty=", "-p", str(shell_pid)], capture_output=True, text=True, check=True
    ).stdout.strip()
    if not tty_name or tty_name == "?":
        raise RuntimeError(f"pane {pane_id} shell {shell_pid} has no controlling tty")
    fd = os.open(f"/dev/{tty_name}", os.O_RDONLY | os.O_NOCTTY)
    try:
        rows, cols = struct.unpack("HHHH", fcntl.ioctl(fd, termios.TIOCGWINSZ, b"\0" * 8))[:2]
    finally:
        os.close(fd)
    if not cols or not rows:
        raise RuntimeError(f"pane {pane_id} tty {tty_name} reports a zero-size window")
    return cols, rows


def pane_rect(pane_id: str) -> dict[str, Any]:
    """The pane's layout rect. Changes even while a control session pins the pty size."""
    layout = run_herdr("pane", "layout", "--pane", pane_id)["result"]["layout"]
    for pane in layout["panes"]:
        if pane["pane_id"] == pane_id:
            return dict(pane["rect"])
    raise RuntimeError(f"pane {pane_id} is not in its own layout")


def open_stream(
    kind: str, pane_id: str, size: tuple[int, int], stdin: Any
) -> subprocess.Popen[bytes]:
    # --cols/--rows always equal the owner's real pty size. In control mode Herdr resizes
    # the pty to whatever is passed (default 120x40), which clips the owner's local view.
    cols, rows = size
    process = subprocess.Popen(
        [herdr_binary(), "terminal", "session", kind, pane_id, "--cols", str(cols), "--rows", str(rows)],
        stdin=stdin,
        stdout=subprocess.PIPE,
    )
    if process.stdout is None:
        raise RuntimeError(f"failed to open Herdr {kind} stream")
    return process


def announce_size(size: tuple[int, int]) -> None:
    cols, rows = size
    sys.stdout.buffer.write(f"\x1b]{SIZE_OSC};{cols};{rows}\x07".encode())
    sys.stdout.buffer.flush()


def pump_frames(process: subprocess.Popen[bytes]) -> bool:
    """Write Herdr terminal frames to our stdout. True when the viewer side closed."""
    assert process.stdout is not None
    try:
        for line in process.stdout:
            frame = json.loads(line)
            if frame.get("type") != "terminal.frame":
                continue
            encoded = frame.get("bytes")
            if not isinstance(encoded, str):
                raise TypeError("Herdr terminal frame has no base64 bytes")
            sys.stdout.buffer.write(base64.b64decode(encoded, validate=True))
            sys.stdout.buffer.flush()
    except BrokenPipeError:
        return True
    finally:
        process.terminate()
        process.wait(timeout=3)
    return False


def send_control(process: subprocess.Popen[bytes], command: dict[str, Any]) -> None:
    assert process.stdin is not None
    try:
        process.stdin.write(json.dumps(command).encode() + b"\n")
        process.stdin.flush()
    except (BrokenPipeError, ValueError):
        pass


class StreamHolder:
    """The live Herdr stream process; swapped when the owner's size changes."""

    def __init__(self) -> None:
        self.process: subprocess.Popen[bytes] | None = None
        self.viewer_closed = threading.Event()


def forward_keystrokes(holder: StreamHolder, fd: int) -> None:
    """Read raw bytes from our terminal (ttyd's pty) into Herdr control input."""
    while True:
        try:
            data = os.read(fd, 4096)
        except OSError:
            data = b""
        process = holder.process
        if not data:
            holder.viewer_closed.set()
            if process is not None:
                send_control(process, {"type": "terminal.release"})
                process.terminate()
            return
        if process is not None:
            send_control(
                process,
                {"type": "terminal.input", "bytes": base64.b64encode(data).decode()},
            )


def watch_owner_size(
    holder: StreamHolder, pane_id: str, size: tuple[int, int], stop: threading.Event
) -> None:
    """Close the stream when the owner's pane changes size, so it reopens at the new size.

    A live control session pins the pty at --cols/--rows and Herdr applies the owner's
    resize only after release, so the layout rect is the change signal, not the pty.
    """
    rect = pane_rect(pane_id)
    while not stop.wait(SIZE_POLL_SECONDS):
        if pane_rect(pane_id) != rect or owner_size(pane_id) != size:
            process = holder.process
            if process is not None:
                if process.stdin is not None:
                    send_control(process, {"type": "terminal.release"})
                process.terminate()
            return


def settled_owner_size(pane_id: str, previous: tuple[int, int] | None) -> tuple[int, int]:
    """Owner size once Herdr has applied the pending resize after a stream release."""
    deadline = time.monotonic() + 2
    while True:
        size = owner_size(pane_id)
        if previous is None or size != previous or time.monotonic() > deadline:
            return size
        time.sleep(0.1)


def stream_pane(kind: str, pane_id: str) -> None:
    """Frames out at the owner's size until the viewer closes; keystrokes in for control."""
    holder = StreamHolder()
    stdin: Any = subprocess.PIPE if kind == "control" else subprocess.DEVNULL
    if kind == "control":
        fd = sys.stdin.fileno()
        threading.Thread(target=forward_keystrokes, args=(holder, fd), daemon=True).start()
    size: tuple[int, int] | None = None
    while not holder.viewer_closed.is_set():
        size = settled_owner_size(pane_id, size)
        announce_size(size)
        holder.process = open_stream(kind, pane_id, size, stdin)
        stop = threading.Event()
        threading.Thread(
            target=watch_owner_size, args=(holder, pane_id, size, stop), daemon=True
        ).start()
        viewer_gone = pump_frames(holder.process)
        stop.set()
        if viewer_gone:
            return


def observe_pane(pane_id: str) -> None:
    """ttyd entry for view mode: frames out, no input."""
    stream_pane("observe", pane_id)


def control_pane(pane_id: str) -> None:
    """ttyd entry for control mode: frames out, keystrokes in, size follows the owner."""
    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    tty.setraw(fd)
    try:
        stream_pane("control", pane_id)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)


def expire_share(generation: str, ttl_seconds: int) -> None:
    time.sleep(ttl_seconds)
    stop_share(expected_generation=generation)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(
        dest="command", required=True, metavar="{view,control,stop,status}"
    )
    for mode, help_text in (
        ("view", "share one pane READ-ONLY (viewers cannot type)"),
        ("control", "share one pane READ-WRITE (the browser can type into it)"),
    ):
        start = subparsers.add_parser(mode, help=help_text)
        start.add_argument(
            "--pane", help="Herdr pane id; defaults to the action or focused pane"
        )
        start.add_argument(
            "--ttl",
            type=int,
            default=int(os.environ.get("HERDR_SHARE_TTL_SECONDS", DEFAULT_TTL_SECONDS)),
            help="expiry in seconds (default: 10800)",
        )
    subparsers.add_parser("stop", help="revoke the active share")
    subparsers.add_parser("status", help="show the active share and its mode")
    observe = subparsers.add_parser("observe")  # internal: ttyd entry for view
    observe.add_argument("pane")
    bridge = subparsers.add_parser("bridge")  # internal: ttyd entry for control
    bridge.add_argument("pane")
    expire = subparsers.add_parser("_expire")  # internal: TTL watchdog
    expire.add_argument("generation")
    expire.add_argument("ttl", type=int)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.command in MODE_SUMMARY:
        start_share(args.command, args.pane, args.ttl)
    elif args.command == "stop":
        stop_share()
    elif args.command == "status":
        show_status()
    elif args.command == "observe":
        observe_pane(args.pane)
    elif args.command == "bridge":
        control_pane(args.pane)
    elif args.command == "_expire":
        expire_share(args.generation, args.ttl)
    else:
        raise AssertionError(f"unhandled command: {args.command}")


if __name__ == "__main__":
    try:
        main()
    except (
        KeyError,
        OSError,
        RuntimeError,
        subprocess.SubprocessError,
        TypeError,
        ValueError,
    ) as error:
        print(f"herdr-share: {error}", file=sys.stderr)
        raise SystemExit(1) from error
