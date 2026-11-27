"""Review page. The browser talks only to this process.

Delegated actions go to the agent runner. The underwriter's own write goes to the
same gateway tool with the human token. Neither path calls the submission service's
tools directly.
"""

import base64
import hashlib
import json
import os
import secrets
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen

import identity
import mcp

PORT = int(os.environ.get("HTTP_PORT", "8000"))
ISSUER = os.environ.get("AM_PUBLIC_ISSUER", "").rstrip("/")
TOKEN_URL = os.environ.get("TOKEN_URL", "")
CLIENT_ID = os.environ.get("WEB_CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("WEB_CLIENT_SECRET", "")
REDIRECT = os.environ.get("REDIRECT_URL", "http://localhost:8170/callback")
AGENT = os.environ.get("AGENT_URL", "").rstrip("/")
GATEWAY = os.environ.get("GATEWAY_MCP_URL", "")
SUBMISSIONS = os.environ.get("SUBMISSIONS_URL", "").rstrip("/")
CONTROL = os.environ.get("CONTROL_TOKEN", "")
DECISIONS = os.environ.get("DECISIONS_URL", "http://localhost:8086/environments/DEFAULT/authz/decisions")
ALLOWED = {item.strip() for item in os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if item.strip()}
SCOPES = "openid profile email submission:read submission:mark-ready"
PAGE = Path(__file__).with_name("page.html").read_text(encoding="utf-8")
LAB = ("http://localhost:9000", "http://127.0.0.1:9000")

SESSIONS = {}
PENDING = {}


def log(step):
    print(step, flush=True)


def _host(header):
    text = header or ""
    if text.startswith("["):
        return text[1:].split("]", 1)[0]
    return text.split(":", 1)[0]


def _json_request(url, payload=None, headers=None, method=None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=data, headers=headers or {}, method=method)
    if payload is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urlopen(request, timeout=20) as response:
            raw = response.read()
            return response.status, json.loads(raw.decode() or "{}")
    except HTTPError as error:
        try:
            body = json.loads(error.read().decode() or "{}")
        except json.JSONDecodeError:
            body = {"message": "Unreadable response"}
        return error.code, body
    except (URLError, json.JSONDecodeError):
        return 0, {"message": "Unreachable"}


def _form_token(form):
    raw = urlencode(form).encode()
    request = Request(TOKEN_URL, data=raw, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    request.add_header("Accept", "application/json")
    basic = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    request.add_header("Authorization", f"Basic {basic}")
    try:
        with urlopen(request, timeout=15) as response:
            return response.status, json.loads(response.read().decode() or "{}")
    except HTTPError as error:
        try:
            body = json.loads(error.read().decode() or "{}")
        except json.JSONDecodeError:
            body = {}
        return error.code, body if isinstance(body, dict) else {}
    except (URLError, json.JSONDecodeError):
        return 0, {}


def authorize_url():
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).decode().rstrip("=")
    state = secrets.token_urlsafe(24)
    PENDING[state] = verifier
    query = urlencode({
        "response_type": "code",
        "client_id": CLIENT_ID,
        "redirect_uri": REDIRECT,
        "scope": SCOPES,
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    })
    return f"{ISSUER}/oauth/authorize?{query}"


def exchange_code(code, state):
    verifier = PENDING.pop(state, None)
    if not verifier or not code:
        raise identity.Closed("sign-in could not be completed")
    status, body = _form_token({
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT,
        "code_verifier": verifier,
    })
    token = body.get("access_token") if status == 200 else None
    if not token:
        raise identity.Closed("sign-in was refused")
    summary = identity.claims(token)
    session = secrets.token_urlsafe(32)
    SESSIONS[session] = {"token": token, "summary": summary}
    return session


def session_from(header):
    for part in (header or "").split(";"):
        name, _, value = part.strip().partition("=")
        if name == "sudr_session":
            return SESSIONS.get(value)
    return None


def outcome(status, body, correlation, summary, source):
    error = body.get("error") if isinstance(body, dict) else None
    observed = _json_request(SUBMISSIONS + "/demo/observation", headers={"X-Demo-Control": CONTROL}, method="GET")[1]
    return {
        "ok": status == 200 and not error,
        "source": source,
        "http_status": status,
        "mcp": body,
        "correlation_id": correlation,
        "decisions_url": DECISIONS,
        "identity": summary,
        "submission": observed,
    }


def through_agent(action, record):
    status, body = _json_request(AGENT + "/act", {
        "action": action,
        "subject_token": record["token"],
        "expected_sub": record["summary"]["sub"],
        "submission_id": "CYB-001",
    })
    if not isinstance(body, dict):
        body = {}
    if body.get("failed_closed"):
        return {"ok": False, "failed_closed": True, "called_gateway": False, "source": "agent", "reason": body.get("reason")}
    identity_summary = body.get("identity") or record["summary"]
    return outcome(body.get("http_status") or status, body.get("mcp") or {}, body.get("correlation_id"), identity_summary, "agent")


def as_human(record):
    result = mcp.call_tool(GATEWAY, record["token"], "mark_ready_for_quote", "CYB-001")
    return outcome(result.status, result.body, result.correlation_id, record["summary"], "human")


def reset_demo():
    _json_request(SUBMISSIONS + "/demo/reset", {}, headers={"X-Demo-Control": CONTROL})
    log("reset")


class Handler(BaseHTTPRequestHandler):
    server_version = "specialty-presenter"
    protocol_version = "HTTP/1.1"

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        if not self._host_ok():
            return
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._json(200, {"status": "ok"})
            return
        if path == "/api/ready":
            agent = _json_request(AGENT + "/health", method="GET")[0] == 200
            submissions = _json_request(SUBMISSIONS + "/health", method="GET")[0] == 200
            self._json(200 if agent and submissions else 503, {
                "status": "ok" if agent and submissions else "degraded",
                "agent": agent,
                "submissions": submissions,
            })
            return
        if path == "/api/session":
            record = session_from(self.headers.get("Cookie"))
            self._json(200, {"signed_in": bool(record), "identity": None if not record else record["summary"], "decisions_url": DECISIONS})
            return
        if path == "/api/desk":
            record = session_from(self.headers.get("Cookie"))
            status, observed = _json_request(SUBMISSIONS + "/demo/observation", headers={"X-Demo-Control": CONTROL}, method="GET")
            self._json(200, {
                "signed_in": bool(record),
                "identity": None if not record else record["summary"],
                "decisions_url": DECISIONS,
                "submission": observed if status == 200 and isinstance(observed, dict) else None,
            })
            return
        if path == "/callback":
            self._callback()
            return
        if path == "/":
            self._bytes(200, PAGE.encode(), "text/html; charset=utf-8")
            return
        self._json(404, {"message": "Not Found"})

    def do_POST(self):
        if not self._host_ok() or not self._origin_ok() or not self._json_post():
            return
        path = self.path.split("?", 1)[0]
        record = session_from(self.headers.get("Cookie"))
        try:
            if path == "/api/sign-in/start":
                self._json(200, {"authorize_url": authorize_url()})
                return
            if path == "/api/reset":
                reset_demo()
                self._clear_cookie()
                body = {"ok": True, "submission": _json_request(
                    SUBMISSIONS + "/demo/observation", headers={"X-Demo-Control": CONTROL}, method="GET")[1]}
                raw = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.send_header("Set-Cookie", "sudr_session=; HttpOnly; SameSite=Lax; Path=/; Max-Age=0")
                self._frame()
                self.end_headers()
                self.wfile.write(raw)
                return
            if record is None:
                self._json(401, {"ok": False, "reason": "Sign in first"})
                return
            identity.claims(record["token"])
            if path == "/api/read-through-agent":
                log("read-through-agent")
                self._json(200, through_agent("read", record))
                return
            if path == "/api/mark-through-agent":
                log("mark-through-agent")
                self._json(200, through_agent("mark-ready", record))
                return
            if path == "/api/mark-myself":
                log("mark-myself")
                self._json(200, as_human(record))
                return
        except identity.Closed as closed:
            self._json(200, {"ok": False, "failed_closed": True, "called_gateway": False, "reason": closed.reason})
            return
        self._json(404, {"message": "Not Found"})

    def _callback(self):
        query = parse_qs(urlparse(self.path).query)
        state = (query.get("state") or [""])[0]
        code = (query.get("code") or [""])[0]
        try:
            session = exchange_code(code, state)
        except identity.Closed:
            self._bytes(400, b"Sign-in was refused.", "text/plain; charset=utf-8")
            return
        log("signed-in")
        page = (
            "<!DOCTYPE html><meta charset=utf-8><title>Signed in</title><p>Signed in. You can close this window.</p>"
            "<script>if (window.opener) { window.opener.postMessage({type:'specialty-underwriting:signed-in'}, location.origin); window.close(); }"
            "else { location.replace('/'); }</script>"
        )
        raw = page.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Set-Cookie", f"sudr_session={session}; HttpOnly; SameSite=Lax; Path=/")
        self._frame()
        self.end_headers()
        self.wfile.write(raw)

    def _host_ok(self):
        if self.path.split("?", 1)[0] == "/health":
            return True
        if _host(self.headers.get("Host")) in ALLOWED:
            return True
        self._json(421, {"message": "Misdirected Request"})
        return False

    def _origin_ok(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        if _host(urlparse(origin).netloc) in ALLOWED:
            return True
        self._json(403, {"message": "Forbidden"})
        return False

    def _json_post(self):
        if "application/json" in self.headers.get("Content-Type", ""):
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length:
                self.rfile.read(length)
            return True
        self._json(415, {"message": "Unsupported Media Type"})
        return False

    def _frame(self):
        self.send_header("Content-Security-Policy", "frame-ancestors " + " ".join(LAB))

    def _json(self, status, body):
        self._bytes(status, json.dumps(body).encode(), "application/json")

    def _bytes(self, status, raw, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self._frame()
        self.end_headers()
        self.wfile.write(raw)

    def _clear_cookie(self):
        header = self.headers.get("Cookie") or ""
        for part in header.split(";"):
            name, _, value = part.strip().partition("=")
            if name == "sudr_session":
                SESSIONS.pop(value, None)


def main():
    required = {
        "AM_PUBLIC_ISSUER": ISSUER, "TOKEN_URL": TOKEN_URL, "WEB_CLIENT_ID": CLIENT_ID,
        "WEB_CLIENT_SECRET": CLIENT_SECRET, "AGENT_URL": AGENT, "GATEWAY_MCP_URL": GATEWAY,
        "SUBMISSIONS_URL": SUBMISSIONS, "CONTROL_TOKEN": CONTROL,
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise SystemExit("missing " + ", ".join(missing))
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
