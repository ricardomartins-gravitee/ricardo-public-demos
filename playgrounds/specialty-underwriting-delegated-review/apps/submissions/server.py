"""Private submission service. No host port: only the compose network can reach it.

The MCP methods are the upstream behind the gateway. Reset and observation are
not tools, and the gateway answers 404 for every path other than the MCP root.
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import protocol
import store

PORT = int(os.environ.get("HTTP_PORT", "8000"))
CONTROL = os.environ.get("CONTROL_TOKEN", "")
SESSIONS = set()


def log(step):
    print(step, flush=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "specialty-submissions"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self._json(200, {"status": "ok"})
            return
        if self.path.split("?", 1)[0] == "/demo/observation":
            if not self._control():
                return
            self._json(200, store.observation())
            return
        self._json(404, {"message": "Not Found"})

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        if path == "/demo/reset":
            if not self._control():
                return
            if self._json_body() is None:
                return
            store.reset()
            log("reset")
            self._json(200, store.observation())
            return
        if path != "/":
            self._json(404, {"message": "Not Found"})
            return
        message = self._json_body()
        if message is None:
            return
        self._mcp(message)

    def _control(self):
        if not CONTROL or self.headers.get("X-Demo-Control") != CONTROL:
            self._json(403, {"message": "Forbidden"})
            return False
        return True

    def _json_body(self):
        kind = self.headers.get("Content-Type", "")
        if "application/json" not in kind:
            self._json(415, {"message": "Unsupported Media Type"})
            return None
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length) if length else b""
        try:
            body = json.loads(raw.decode() or "null")
        except (UnicodeError, json.JSONDecodeError):
            self._json(400, {"message": "Bad Request"})
            return None
        if not isinstance(body, dict):
            self._json(400, {"message": "Bad Request"})
            return None
        return body

    def _mcp(self, message):
        method = message.get("method")
        message_id = message.get("id")
        if isinstance(method, str) and method.startswith("notifications/"):
            self.send_response(202)
            self.end_headers()
            return
        session = self.headers.get("Mcp-Session-Id")
        try:
            result, created = self._dispatch(method, message.get("params") or {}, session)
        except protocol.ProtocolError as error:
            self._json(200, protocol.failure(message_id, error.code, error.message))
            return
        extra = {"Mcp-Session-Id": created} if created else None
        self._json(200, protocol.success(message_id, result), extra)

    def _dispatch(self, method, params, session):
        if method == "initialize":
            created = protocol.new_session()
            SESSIONS.add(created)
            log("initialize")
            return protocol.initialize(params), created
        if session not in SESSIONS:
            raise protocol.ProtocolError(-32000, "MCP session is missing")
        if method == "tools/list":
            log("tools/list")
            return protocol.list_tools(), None
        if method == "tools/call":
            return self._call(params), None
        raise protocol.ProtocolError(-32601, "Method not found")

    def _call(self, params):
        name = params.get("name")
        arguments = params.get("arguments") or {}
        submission_id = arguments.get("submission_id")
        if not isinstance(submission_id, str) or not submission_id:
            raise protocol.ProtocolError(-32602, "submission_id is required")
        if name == "get_submission_context":
            found = store.read_context(submission_id)
            log("read")
        elif name == "mark_ready_for_quote":
            found = store.mark_ready(submission_id)
            log("mark-ready")
        else:
            raise protocol.ProtocolError(-32602, "Unknown tool")
        if found is None:
            raise protocol.ProtocolError(-32004, "No such submission")
        return protocol.tool_result(found)

    def _json(self, status, body, extra=None):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        for key, value in (extra or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(raw)


def main():
    if not CONTROL:
        raise SystemExit("CONTROL_TOKEN is required")
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
