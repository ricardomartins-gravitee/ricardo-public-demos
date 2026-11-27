"""MCP client for the gateway. One initialize, then one tools/call. No second token."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROTOCOL = "2025-11-25"


class GatewayResult:
    def __init__(self, status, body, correlation_id):
        self.status = status
        self.body = body
        self.correlation_id = correlation_id


def correlation(headers, body):
    for name in ("x-gravitee-request-id", "x-correlation-id", "x-request-id"):
        value = headers.get(name) if headers is not None else None
        if value:
            return value
    error = body.get("error") if isinstance(body, dict) else None
    data = error.get("data") if isinstance(error, dict) else None
    if isinstance(data, dict) and data.get("requestId"):
        return str(data["requestId"])
    return None


def parse(status, raw, headers):
    text = raw.decode() if raw else ""
    kind = headers.get("Content-Type", "") if headers is not None else ""
    body = {}
    if "json" in kind:
        try:
            body = json.loads(text) if text else {}
        except json.JSONDecodeError:
            body = {"message": "Unreadable gateway response"}
    else:
        for line in text.splitlines():
            if line.startswith("data:"):
                try:
                    body = json.loads(line[5:].strip())
                except json.JSONDecodeError:
                    body = {"message": "Unreadable gateway response"}
                break
        if not body and text:
            body = {"message": "Unreadable gateway response"}
    if not isinstance(body, dict):
        body = {"message": "Unreadable gateway response"}
    return GatewayResult(status, body, correlation(headers, body))


def post(url, payload, headers, timeout):
    request = Request(url, data=json.dumps(payload).encode(), headers=dict(headers), method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return parse(response.status, response.read(), response.headers), response.headers.get("Mcp-Session-Id")
    except HTTPError as error:
        return parse(error.code, error.read(), error.headers), None
    except URLError:
        return GatewayResult(0, {"message": "Gateway unreachable"}, None), None


def call_tool(url, token, name, submission_id, timeout=15):
    """Initialize, then call one tool. The bearer is the token the caller already checked."""
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": PROTOCOL,
        "Authorization": f"Bearer {token}",
    }
    opened, session = post(url, {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": PROTOCOL,
            "capabilities": {},
            "clientInfo": {"name": "specialty-review-runner", "version": "1"},
        },
    }, headers, timeout)
    if opened.status != 200:
        return opened
    if session:
        headers["Mcp-Session-Id"] = session
    post(url, {"jsonrpc": "2.0", "method": "notifications/initialized"}, headers, timeout)
    called, _session = post(url, {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/call",
        "params": {"name": name, "arguments": {"submission_id": submission_id}},
    }, headers, timeout)
    return called
