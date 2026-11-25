import base64
import json
import threading
import time
import unittest
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import server


def jwt(exp):
    payload = {"iss": "http://am.example/specialty-underwriting", "sub": "human-1", "scope": "submission:read submission:mark-ready",
               "iat": int(time.time()), "exp": exp}
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"h.{raw}.s"


class Upstream(BaseHTTPRequestHandler):
    calls = []

    def log_message(self, fmt, *args):
        return

    def do_GET(self):
        body = json.dumps({"status": "IN_REVIEW", "write_handler_calls": 0}).encode()
        if self.path != "/health":
            body = json.dumps({"status": "IN_REVIEW", "write_handler_calls": 0, "submission_id": "CYB-001"}).encode()
        self._send(200, body)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length)
        type(self).calls.append({
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": json.loads(raw.decode() or "{}"),
        })
        if self.path == "/act":
            out = {"ok": False, "failed_closed": False, "called_gateway": True, "http_status": 403,
                   "correlation_id": "req-agent", "identity": {"iss": "http://am.example/specialty-underwriting",
                   "sub": "human-1", "act_sub": "cyber-review-agent", "scope": "submission:read", "expires_in": 500},
                   "mcp": {"error": {"code": -32001, "message": "Not allowed"}}}
        else:
            out = {"jsonrpc": "2.0", "id": 2, "result": {"ok": True}}
        self._send(200, json.dumps(out).encode())

    def _send(self, status, raw):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)


def post(base, path, headers=None):
    req = urllib.request.Request(base + path, data=b"{}", headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode())
    except urllib.error.HTTPError as error:
        raw = error.read().decode() or "{}"
        error.close()
        return error.code, json.loads(raw)


class RouteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upstream = ThreadingHTTPServer(("127.0.0.1", 0), Upstream)
        threading.Thread(target=cls.upstream.serve_forever, daemon=True).start()
        host = f"http://127.0.0.1:{cls.upstream.server_address[1]}"
        server.ISSUER = host
        server.TOKEN_URL = host + "/token"
        server.CLIENT_ID = "specialty-underwriting-web"
        server.CLIENT_SECRET = "test"
        server.AGENT = host
        server.GATEWAY = host + "/mcp"
        server.SUBMISSIONS = host
        server.CONTROL = "test-control"
        server.ALLOWED = {"127.0.0.1", "localhost"}
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.upstream.shutdown()

    def setUp(self):
        Upstream.calls = []
        server.SESSIONS.clear()

    def test_desk_reports_file_status_without_a_tool_call(self):
        with urllib.request.urlopen(self.base + "/api/desk") as response:
            body = json.loads(response.read().decode())
        self.assertEqual(body["submission"]["status"], "IN_REVIEW")
        self.assertEqual(body["submission"]["submission_id"], "CYB-001")
        self.assertFalse(body["signed_in"])
        self.assertFalse(Upstream.calls)

    def test_cross_site_post_is_refused(self):
        status, _ = post(self.base, "/api/reset", {"Origin": "http://evil.example"})
        self.assertEqual(status, 403)

    def test_form_post_is_refused(self):
        req = urllib.request.Request(self.base + "/api/reset", data=b"a=b", headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req)
        caught.exception.close()
        self.assertEqual(caught.exception.code, 415)

    def test_agent_and_human_paths_use_different_calls(self):
        server.SESSIONS["session"] = {"token": jwt(int(time.time()) + 600), "summary": server.identity.claims(jwt(int(time.time()) + 600))}
        cookie = {"Cookie": "sudr_session=session"}
        agent = post(self.base, "/api/mark-through-agent", cookie)[1]
        human = post(self.base, "/api/mark-myself", cookie)[1]
        self.assertEqual(agent["correlation_id"], "req-agent")
        self.assertEqual(agent["identity"]["act_sub"], "cyber-review-agent")
        self.assertEqual(human["source"], "human")
        agent_calls = [item for item in Upstream.calls if item["path"] == "/act"]
        gateway_calls = [item for item in Upstream.calls if item["path"] == "/mcp"]
        self.assertEqual(len(agent_calls), 1)
        self.assertTrue(gateway_calls)
        self.assertNotIn(server.SESSIONS["session"]["token"], agent_calls[0]["authorization"] or "")
        self.assertTrue(any(item["authorization"] and item["authorization"].endswith(server.SESSIONS["session"]["token"]) for item in gateway_calls))

    def test_expired_human_token_does_not_call_the_gateway(self):
        token = jwt(int(time.time()) - 30)
        server.SESSIONS["session"] = {"token": token, "summary": {"sub": "human-1", "iss": "x", "scope": "", "exp": 1, "expires_in": 0}}
        body = post(self.base, "/api/mark-myself", {"Cookie": "sudr_session=session"})[1]
        self.assertTrue(body["failed_closed"])
        self.assertFalse(any(item["path"] == "/mcp" for item in Upstream.calls))


if __name__ == "__main__":
    unittest.main()
