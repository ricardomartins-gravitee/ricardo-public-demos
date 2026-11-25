import json
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import server


def start():
    server.CONTROL = "test-control"
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}"


def request(url, method="GET", body=None, headers=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return response.status, json.loads(response.read().decode() or "null"), response.headers
    except urllib.error.HTTPError as error:
        raw = error.read().decode()
        error.close()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return error.code, parsed, error.headers


class HttpTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd, cls.base = start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def setUp(self):
        status, _, _ = request(self.base + "/demo/reset", "POST", {}, {
            "Content-Type": "application/json",
            "X-Demo-Control": "test-control",
        })
        self.assertEqual(status, 200)

    def test_reset_without_the_control_token_does_not_change_state(self):
        request(self.base + "/", "POST", {
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {},
        }, {"Content-Type": "application/json"})
        # A write through MCP, then a refused reset, leaves the write in place.
        self._call("mark_ready_for_quote")
        status, _, _ = request(self.base + "/demo/reset", "POST", {}, {"Content-Type": "application/json"})
        self.assertEqual(status, 403)
        observed = request(self.base + "/demo/observation", headers={"X-Demo-Control": "test-control"})[1]
        self.assertEqual(observed["status"], "READY_FOR_QUOTE")
        self.assertEqual(observed["write_handler_calls"], 1)

    def _session(self):
        status, body, headers = request(self.base + "/", "POST", {
            "jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {"protocolVersion": "2025-11-25"},
        }, {"Content-Type": "application/json", "Accept": "application/json"})
        self.assertEqual(status, 200)
        self.assertEqual(body["result"]["serverInfo"]["name"], "Specialty Underwriting MCP")
        return {"Content-Type": "application/json", "Mcp-Session-Id": headers["Mcp-Session-Id"]}

    def _call(self, name):
        headers = self._session()
        return request(self.base + "/", "POST", {
            "jsonrpc": "2.0", "id": 2, "method": "tools/call",
            "params": {"name": name, "arguments": {"submission_id": "CYB-001"}},
        }, headers)

    def test_both_tools_are_listed(self):
        headers = self._session()
        body = request(self.base + "/", "POST", {
            "jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {},
        }, headers)[1]
        names = sorted(tool["name"] for tool in body["result"]["tools"])
        self.assertEqual(names, ["get_submission_context", "mark_ready_for_quote"])

    def test_read_then_mark_ready(self):
        read = self._call("get_submission_context")[1]["result"]["structuredContent"]
        self.assertEqual(read["status"], "IN_REVIEW")
        self.assertEqual(read["write_handler_calls"], 0)
        marked = self._call("mark_ready_for_quote")[1]["result"]["structuredContent"]
        self.assertEqual(marked["status"], "READY_FOR_QUOTE")
        self.assertEqual(marked["line_of_business"], "CYBER")


if __name__ == "__main__":
    unittest.main()
