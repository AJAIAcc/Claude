#!/usr/bin/env python3
"""A stand-in for an OpenAI-compatible endpoint, for the end-to-end test.

CoreTest covers the parsers directly. This exists to exercise the part that
only a socket can: the real HttpURLConnection request, its headers, the
chunked SSE response arriving in pieces, and the error paths. It also records
what it was sent, so the test can assert on the request the app actually built.

Usage: fake_server.py <portfile>   (binds an ephemeral port, writes it there)
"""
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

LAST = {}
LOCK = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):
        pass  # quiet

    # ---------------------------------------------------------------- helpers

    def _json(self, code, payload):
        body = json.dumps(payload).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sse_open(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Transfer-Encoding", "chunked")
        self.end_headers()

    def _chunk(self, text):
        """One HTTP chunk, so the client really does read the stream in pieces."""
        data = text.encode()
        self.wfile.write(b"%x\r\n" % len(data) + data + b"\r\n")
        self.wfile.flush()

    def _end_chunks(self):
        self.wfile.write(b"0\r\n\r\n")
        self.wfile.flush()

    def _event(self, obj):
        self._chunk("data: " + json.dumps(obj) + "\n\n")

    @staticmethod
    def _delta(text=None, reasoning=None, finish=None):
        d = {}
        if text is not None:
            d["content"] = text
        if reasoning is not None:
            d["reasoning_content"] = reasoning
        return {"choices": [{"index": 0, "delta": d, "finish_reason": finish}]}

    # -------------------------------------------------------------------- GET

    def do_GET(self):
        if self.path == "/last":
            with LOCK:
                self._json(200, LAST)
            return
        if self.path.endswith("/models"):
            self._json(200, {"object": "list", "data": [
                {"id": "Hermes-4-405B"},
                {"id": "some-other-model"},
                {"id": "Hermes-4-70B"},
            ]})
            return
        self._json(404, {"error": {"message": "no such path"}})

    # ------------------------------------------------------------------- POST

    def do_POST(self):
        # The cancellation test hangs up mid-stream on purpose, so a broken
        # pipe here is the expected outcome, not a fault worth a traceback.
        try:
            self._post()
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _post(self):
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n).decode("utf-8")
        try:
            req = json.loads(raw)
        except ValueError:
            self._json(400, {"error": {"message": "body was not JSON"}})
            return

        with LOCK:
            LAST.clear()
            LAST.update({
                "authorization": self.headers.get("Authorization") or "",
                "accept": self.headers.get("Accept") or "",
                "accept_encoding": self.headers.get("Accept-Encoding") or "",
                "content_type": self.headers.get("Content-Type") or "",
                "user_agent": self.headers.get("User-Agent") or "",
                "body": req,
            })

        if not self.path.endswith("/chat/completions"):
            self._json(404, {"error": {"message": "no such path"}})
            return

        model = req.get("model", "")

        if model == "err401":
            self._json(401, {"error": {"message": "invalid api key"}})
            return
        if model == "err500html":
            body = b"<html><body>Bad Gateway</body></html>"
            self.send_response(502)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if model == "midstream":
            # A 200 that fails part way through, which is the nasty case.
            self._sse_open()
            self._event(self._delta(text="starting"))
            self._chunk('data: {"error": {"message": "ran out of context"}}\n\n')
            self._end_chunks()
            return
        if model == "silent":
            self._sse_open()
            self._end_chunks()
            return

        if not req.get("stream"):
            self._json(200, {"choices": [{"index": 0, "message": {
                "role": "assistant",
                "content": "<think>quietly</think>A whole answer.",
            }, "finish_reason": "stop"}]})
            return

        # The happy path: a reasoning trace whose tags straddle chunk
        # boundaries, then the answer, one fragment at a time.
        self._sse_open()
        self._event(self._delta(text=""))
        for piece in ["<thi", "nk>I should", " be brief.</thi", "nk>", "Hello",
                      " from ", "Hermes", "."]:
            self._event(self._delta(text=piece))
            time.sleep(0.005)
        self._event(self._delta(finish="stop"))
        self._chunk("data: [DONE]\n\n")
        self._end_chunks()


def main():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    port = httpd.server_address[1]
    with open(sys.argv[1], "w") as f:
        f.write(str(port))
    httpd.serve_forever()


if __name__ == "__main__":
    main()
