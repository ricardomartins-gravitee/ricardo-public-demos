"""Deterministic agent runner. It exchanges tokens and calls the gateway. It does not infer."""

import base64
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import exchange
import mcp

PORT = int(os.environ.get("HTTP_PORT", "8000"))
TOKEN_URL = os.environ.get("TOKEN_URL", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
ACTOR = os.environ.get("EXPECTED_ACTOR", "cyber-review-agent")
RESOURCE = os.environ.get("RESOURCE_URL", "")
AUDIENCES = [item.strip() for item in os.environ.get("ALLOWED_AUDIENCES", "").split(",") if item.strip()]
GATEWAY = os.environ.get("GATEWAY_MCP_URL", "")
TOOLS = {"read": "get_submission_context", "mark-ready": "mark_ready_for_quote"}


def log(step):
    print(step, flush=True)


def _token_request(form):
    raw = urlencode(form).encode()
    request = Request(TOKEN_URL, data=raw, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")
    # The client authenticates itself. The secret is not written to the log.
    token = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    request.add_header("Authorization", f"Basic {token}")
    try:
        with urlopen(request, timeout=15) as response:
            status, body = response.status, json.loads(response.read().decode() or "{}")
    except HTTPError as error:
        try:
            body = json.loads(error.read().decode() or "{}")
        except json.JSONDecodeError:
            body = {}
        status = error.code
    except (URLError, json.JSONDecodeError):
        return 0, {}
    return status, body if isinstance(body, dict) else {}


def actor_token():
    status, body = _token_request({"grant_type": "client_credentials", "scope": exchange.READ_SCOPE})
    if status != 200 or not body.get("access_token"):
        raise exchange.Closed("actor credential was refused")
    return body["access_token"]


def delegated_token(subject_token, actor):
    status, body = _token_request(exchange.form(subject_token, actor, RESOURCE))
    if status != 200 or not body.get("access_token"):
        reason = body.get("error") if isinstance(body.get("error"), str) else "token exchange was refused"
        raise exchange.Closed(reason)
    return body["access_token"]


def perform(action, subject_token, expected_sub, submission_id):
    tool = TOOLS.get(action)
    if tool is None:
        raise exchange.Closed("unknown action")
    if not submission_id:
        raise exchange.Closed("submission is missing")
    if not subject_token:
        raise exchange.Closed("subject token is missing")
    # The subject token is exchanged and then dropped. It is never sent to the gateway.
    access = delegated_token(subject_token, actor_token())
    summary = exchange.assess(access, expected_sub, ACTOR, AUDIENCES)
    result = mcp.call_tool(GATEWAY, access, tool, submission_id)
    error = result.body.get("error") if isinstance(result.body, dict) else None
    return {
        "ok": result.status == 200 and not error,
        "failed_closed": False,
        "called_gateway": True,
        "http_status": result.status,
        "mcp": result.body,
        "correlation_id": result.correlation_id,
        "identity": summary,
    }


class Handler(BaseHTTPRequestHandler):
    server_version = "specialty-agent"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self._json(200, {"status": "ok"})
            return
        self._json(404, {"message": "Not Found"})

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/act":
            self._json(404, {"message": "Not Found"})
            return
        if "application/json" not in self.headers.get("Content-Type", ""):
            self._json(415, {"message": "Unsupported Media Type"})
            return
        length = int(self.headers.get("Content-Length", "0") or "0")
        try:
            body = json.loads(self.rfile.read(length).decode() or "{}")
        except (UnicodeError, json.JSONDecodeError):
            self._json(400, {"message": "Bad Request"})
            return
        if not isinstance(body, dict):
            self._json(400, {"message": "Bad Request"})
            return
        try:
            outcome = perform(body.get("action"), body.get("subject_token"), body.get("expected_sub"), body.get("submission_id"))
            log(body.get("action") or "act")
            self._json(200, outcome)
        except exchange.Closed as closed:
            log("closed")
            self._json(200, {"ok": False, "failed_closed": True, "called_gateway": False, "reason": closed.reason})

    def _json(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def main():
    missing = [name for name, value in (
        ("TOKEN_URL", TOKEN_URL), ("CLIENT_ID", CLIENT_ID), ("CLIENT_SECRET", CLIENT_SECRET),
        ("GATEWAY_MCP_URL", GATEWAY), ("ALLOWED_AUDIENCES", ",".join(AUDIENCES))) if not value]
    if missing:
        raise SystemExit("missing " + ", ".join(missing))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
