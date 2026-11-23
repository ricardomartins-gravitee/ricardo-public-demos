import json
import threading
import unittest
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import server


class Fill(unittest.TestCase):
    def test_a_setting_is_filled_and_a_missing_one_is_named(self):
        text, missing = server.substitute("http://gw/${PRESENT}/x", {"PRESENT": "shared"})
        self.assertEqual((text, missing), ("http://gw/shared/x", []))
        text, missing = server.substitute("${ABSENT}", {})
        self.assertEqual(missing, ["ABSENT"])

    def test_a_credential_header_is_masked(self):
        shown = server.mask({"X-Gravitee-Api-Key": "secret-value", "Accept": "application/json"})
        self.assertEqual(shown["X-Gravitee-Api-Key"], "••••")
        self.assertEqual(shown["Accept"], "application/json")


class Calls(unittest.TestCase):
    def setUp(self):
        self.file = Path(self.id().replace(".", "_") + ".json")
        self.file.write_text(json.dumps({
            "title": "Demo",
            "calls": [
                {"id": "plain", "name": "Plain", "method": "GET", "url": "http://127.0.0.1:9/missing", "show": "http://localhost/missing", "group": "Direct", "panel": "Route", "hops": ["Client", "API"]},
                {"id": "keyed", "name": "Keyed", "url": "http://127.0.0.1:9/missing", "keyFrom": "input", "keyHeader": "X-Gravitee-Api-Key"},
            ],
        }), encoding="utf-8")
        self.previous = server.CALLS_FILE
        server.CALLS_FILE = self.file

    def tearDown(self):
        server.CALLS_FILE = self.previous
        self.file.unlink(missing_ok=True)

    def test_the_page_list_hides_the_address_used_inside_the_network(self):
        listed = server.public_calls(server.load_calls({}))
        plain = listed["calls"][0]
        self.assertEqual(plain["show"], "http://localhost/missing")
        self.assertEqual(plain["group"], "Direct")
        self.assertEqual(plain["panel"], "Route")
        self.assertEqual(listed["calls"][1]["panel"], "")
        self.assertEqual(listed["calls"][1]["group"], "")
        self.assertTrue(listed["calls"][1]["needsKey"])
        self.assertNotIn("headers", plain)
        self.assertNotIn("hops", plain)

    def test_the_diagram_is_read_from_the_response(self):
        denied = server.trace(401, "Unauthorized", {"X-Gravitee-Request-Id": "abc"})
        self.assertEqual(denied["participants"], ["client", "gravitee"])
        served = server.trace(200, '{"count": 4}', {"X-Gravitee-Request-Id": "abc"})
        self.assertEqual(served["participants"], ["client", "gravitee", "api"])
        direct = server.trace(200, '{"count": 4}', {"Content-Type": "application/json"})
        self.assertEqual(direct["participants"], ["client", "api"])

    def test_an_unknown_id_is_refused_and_a_key_is_not_stored(self):
        class Once(BaseHTTPRequestHandler):
            seen = {}

            def do_GET(self):
                Once.seen["key"] = self.headers.get("X-Gravitee-Api-Key")
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                return

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Once)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]
        try:
            spec = server.load_calls({})
            spec["calls"][1]["url"] = f"http://127.0.0.1:{port}/v1/services"
            result = server.perform(spec["calls"][1], "live-key")
            self.assertEqual(result["status"], 200)
            self.assertEqual(Once.seen["key"], "live-key")
            self.assertEqual(result["request"]["headers"]["X-Gravitee-Api-Key"], "••••")
            self.assertNotIn("live-key", json.dumps(result))
        finally:
            httpd.shutdown()

    def test_a_token_call_sends_bearer_and_keeps_the_secret(self):
        class Token(BaseHTTPRequestHandler):
            seen = {}

            def do_POST(self):
                Token.seen["auth"] = self.headers.get("Authorization")
                length = int(self.headers.get("Content-Length") or 0)
                Token.seen["body"] = self.rfile.read(length).decode()
                body = b'{"access_token":"live-token","token_type":"bearer"}'
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_GET(self):
                Token.seen["bearer"] = self.headers.get("Authorization")
                body = b'{"ok":true}'
                self.send_response(200)
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, fmt, *args):
                return

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Token)
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        port = httpd.server_address[1]
        try:
            call = {
                "missing": [],
                "headers": {},
                "keyFrom": "",
                "keyHeader": "",
                "method": "GET",
                "url": f"http://127.0.0.1:{port}/v1/services",
                "show": "http://localhost/v1/services",
                "token": {
                    "url": f"http://127.0.0.1:{port}/oauth/token",
                    "clientId": "caller",
                    "clientSecret": "secret-value",
                    "scope": "shared-services",
                },
            }
            result = server.perform(call, "")
            self.assertEqual(result["status"], 200)
            self.assertEqual(Token.seen["bearer"], "Bearer live-token")
            self.assertIn("scope=shared-services", Token.seen["body"])
            self.assertTrue(Token.seen["auth"].startswith("Basic "))
            self.assertEqual(result["request"]["headers"]["Authorization"], "••••")
            shown = json.dumps(result)
            self.assertNotIn("live-token", shown)
            self.assertNotIn("secret-value", shown)
        finally:
            httpd.shutdown()


class GraviteeLog(unittest.TestCase):
    def test_the_management_api_is_used_only_when_it_is_configured(self):
        self.assertIsNone(server.management_settings({}))
        ready = server.management_settings({
            "CALL_STAGE_MANAGEMENT_URL": "http://apim:8083/",
            "CALL_STAGE_MANAGEMENT_USERNAME": "admin",
            "CALL_STAGE_MANAGEMENT_PASSWORD": "secret",
        })
        self.assertEqual(ready["url"], "http://apim:8083")
        self.assertEqual(ready["env"], "DEFAULT")

    def test_the_request_path_selects_the_longest_api_prefix(self):
        apis = [
            {"id": "short", "listeners": [{"paths": [{"path": "/shared"}]}]},
            {"id": "services", "listeners": [{"paths": [{"path": "/shared-services/"}]}]},
            {"id": "other", "listeners": [{"paths": [{"path": "/other/"}]}]},
        ]
        self.assertEqual(server.match_api(apis, "/shared-services/v1/services")["id"], "services")
        self.assertIsNone(server.match_api(apis, "/health"))

    def test_a_log_keeps_the_gateway_reason_and_drops_an_unknown_plan(self):
        shown = server.project_log({
            "requestId": "abc-123",
            "message": "Unauthorized (no token)",
            "plan": {"name": "Unknown"},
            "application": {"name": "Unknown"},
            "gatewayResponseTime": 2,
            "method": "GET",
            "uri": "/shared-services/v1/services",
        })
        self.assertEqual(shown["message"], "Unauthorized (no token)")
        self.assertEqual(shown["plan"], "")
        self.assertEqual(shown["application"], "")
        self.assertEqual(shown["gatewayMs"], 2)
        self.assertNotIn("requestId", shown)

    def test_the_log_is_the_row_for_this_request_after_it_is_indexed(self):
        seen = []

        def opener(url, authorization):
            seen.append(url)
            if url.endswith("/apis?perPage=100"):
                return 200, {"data": [{"id": "api-1", "listeners": [{"paths": [{"path": "/shared-services/"}]}]}]}
            if sum(1 for item in seen if "/logs?" in item) == 1:
                return 200, {"data": [{"requestId": "other-id", "message": "no"}]}
            return 200, {"data": [{"requestId": "request-1", "message": "Rejected", "plan": {"name": "API Key"}, "application": {"name": "Consumer App A"}, "gatewayResponseTime": 4, "method": "GET", "uri": "/shared-services/v1/services"}]}

        slept = []
        log = server.gravitee_log(
            {"url": "http://apim", "user": "admin", "password": "secret", "org": "DEFAULT", "env": "DEFAULT"},
            "request-1",
            "/shared-services/v1/services",
            opener=opener,
            now_ms=1_000,
            sleep=slept.append,
            attempts=3,
            cache={},
        )
        self.assertEqual(log["message"], "Rejected")
        self.assertEqual(log["plan"], "API Key")
        self.assertEqual(log["application"], "Consumer App A")
        self.assertEqual(slept, [0.5])
        self.assertTrue(seen[0].endswith("/apis?perPage=100"))

    def test_a_refused_management_api_is_not_retried(self):
        def opener(url, authorization):
            if url.endswith("/apis?perPage=100"):
                return 200, {"data": [{"id": "api-1", "listeners": [{"paths": [{"path": "/shared-services/"}]}]}]}
            return 401, {}

        log = server.gravitee_log(
            {"url": "http://apim", "user": "admin", "password": "secret", "org": "DEFAULT", "env": "DEFAULT"},
            "request-1",
            "/shared-services/v1/services",
            opener=opener,
            now_ms=1_000,
            sleep=self.fail,
            cache={},
        )
        self.assertIsNone(log)


if __name__ == "__main__":
    unittest.main()
