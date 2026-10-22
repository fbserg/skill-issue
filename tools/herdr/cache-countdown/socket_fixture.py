"""Socket fixtures and regression coverage for CLI-independent Herdr reads."""

import json
import socketserver
import threading


class HerdrTestServer:
    def __init__(self, path, handler):
        class RequestHandler(socketserver.StreamRequestHandler):
            def handle(self):
                request = json.loads(self.rfile.readline())
                result = handler(request)
                self.wfile.write(
                    (
                        json.dumps({"id": request["id"], "result": result}) + "\n"
                    ).encode()
                )

        self.server = socketserver.UnixStreamServer(str(path), RequestHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()


