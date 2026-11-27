import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

import exchange
import mcp
import server


class Record(BaseHTTPRequestHandler):
    seen = []

    def log_message(self, fmt, *args):
        return

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        raw = self.rfile.read(length).decode() or ""
        if self.path == "/token":
            body = {key: values[0] for key, values in parse_qs(raw).items()}
        else:
            body = json.loads(raw or "{}")
        type(self).seen.append({
            "path": self.path,
            "authorization": self.headers.get("Authorization"),
            "body": body,
        })
        if self.path == "/token":
            payload = {"iss": "http://am.example/specialty-underwriting", "sub": "human-1",
                       "act": {"sub": "cyber-review-agent"}, "aud": "specialty-underwriting-mcp",
                       "scope": "submission:read", "iat": 1, "exp": 10_000_000_000}
            import base64
            raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            token = f"h.{raw}.s"
            out = json.dumps({"access_token": token, "token_type": "Bearer"}).encode()
        else:
            out = json.dumps({"jsonrpc": "2.0", "id": body.get("id"), "result": {"ok": True}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        if self.path != "/token":
            self.send_header("Mcp-Session-Id", "session-1")
        self.end_headers()
        self.wfile.write(out)


class PerformTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Record)
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        base = f"http://127.0.0.1:{cls.httpd.server_address[1]}"
        server.TOKEN_URL = base + "/token"
        server.CLIENT_ID = "cyber-review-agent"
        server.CLIENT_SECRET = "test-secret"
        server.ACTOR = "cyber-review-agent"
        server.RESOURCE = base + "/mcp"
        server.AUDIENCES = ["specialty-underwriting-mcp"]
        server.GATEWAY = base + "/mcp"

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        Record.seen = []

    def test_gateway_receives_the_delegated_token_only(self):
        outcome = server.perform("mark-ready", "subject-token-value", "human-1", "CYB-001")
        self.assertTrue(outcome["called_gateway"])
        self.assertEqual(outcome["identity"]["act_sub"], "cyber-review-agent")
        authorizations = [item["authorization"] for item in Record.seen if item["path"] == "/mcp"]
        self.assertTrue(authorizations)
        self.assertNotIn("subject-token-value", " ".join(authorizations))
        self.assertTrue(all(item.startswith("Bearer ") for item in authorizations))

    def test_expired_exchange_does_not_call_the_gateway(self):
        def expired(subject, actor):
            payload = {"iss": "http://am.example/specialty-underwriting", "sub": "human-1",
                       "act": {"sub": "cyber-review-agent"}, "aud": "specialty-underwriting-mcp",
                       "scope": "submission:read", "iat": 1, "exp": 1}
            import base64
            raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
            return f"h.{raw}.s"

        original = server.delegated_token
        server.delegated_token = expired
        try:
            with self.assertRaises(exchange.Closed):
                server.perform("read", "subject-token-value", "human-1", "CYB-001")
            self.assertFalse(any(item["path"] == "/mcp" for item in Record.seen))
        finally:
            server.delegated_token = original

    def test_mcp_error_body_supplies_the_correlation_id(self):
        body = {"error": {"code": -32001, "data": {"requestId": "req-9"}}}
        result = mcp.parse(403, json.dumps(body).encode(), {"Content-Type": "application/json"})
        self.assertEqual(result.correlation_id, "req-9")
        self.assertEqual(result.status, 403)


if __name__ == "__main__":
    unittest.main()
