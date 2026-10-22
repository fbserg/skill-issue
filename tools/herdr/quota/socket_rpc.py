"""Herdr public JSON socket requests, independent of the installed CLI version."""

from __future__ import annotations

import json
import os
import socket
from typing import Any


def rpc(method: str, params: dict[str, Any], timeout: float = 10) -> dict[str, Any]:
    # Public requests avoid coupling this plugin to the CLI's private protocol version.
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(timeout)
        connection.connect(os.environ["HERDR_SOCKET_PATH"])
        request = {"id": "project-anchors", "method": method, "params": params}
        connection.sendall((json.dumps(request) + "\n").encode())
        with connection.makefile("r") as response_stream:
            response = json.loads(response_stream.readline())
    if "error" in response:
        raise RuntimeError(f"{method}: {response['error']}")
    return response["result"]
