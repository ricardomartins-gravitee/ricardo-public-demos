"""MCP tools the concierge calls, and the agent cards Agent Management registers.

The concierge cannot call another agent. It calls `ask_booking_desk` or `ask_loyalty_desk` here, and this
process sends that question through the gateway's A2A proxy, so the call is a gateway call. The cards are
served before either agent process is up: the seed reads them while it fills the catalog, and the agents
start after the seed.
"""

import json
import os
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

MCP_PORT = int(os.environ.get("DESK_MCP_PORT", "8088"))
CARD_PORT = int(os.environ.get("DESK_CARD_PORT", "8089"))
SERVER_NAME = "acme-hotels-booking-desk"
PROTOCOL = "2025-11-25"
A2A_URL = os.environ.get("BOOKING_A2A_URL", "")
A2A_TIMEOUT = int(os.environ.get("BOOKING_A2A_TIMEOUT", "90"))
LOYALTY_A2A_URL = os.environ.get("LOYALTY_A2A_URL", "")
LOYALTY_A2A_TIMEOUT = int(os.environ.get("LOYALTY_A2A_TIMEOUT", "90"))

CONCIERGE_CARD = {
    "name": "ACME Hotels Concierge",
    "version": "1.0.0",
    "description": "The guest's assistant. It answers on the website, asks the booking desk to search hotels, and asks the loyalty desk in AWS for an offer.",
    "supportedInterfaces": [{"url": "http://localhost:8082/hotel-agent/", "protocolBinding": "JSONRPC"}],
    "capabilities": {"streaming": True},
    "skills": [{
        "id": "guest-concierge",
        "name": "Guest concierge",
        "description": "Talks to the guest and hands a hotel search to the booking desk.",
        "tags": ["hotel", "concierge"],
    }],
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
}
BOOKING_CARD = {
    "name": "ACME Hotels Booking Desk",
    "version": "1.0.0",
    "description": "Searches hotels and reads a stay. The concierge asks it, through the gateway.",
    "supportedInterfaces": [{"url": "http://localhost:8082/booking-desk/", "protocolBinding": "JSONRPC"}],
    "capabilities": {"streaming": True},
    "skills": [{
        "id": "hotel-search",
        "name": "Hotel search",
        "description": "Finds hotels with the hotels' tools.",
        "tags": ["hotel", "search"],
    }],
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
}
CARDS = {"/concierge": CONCIERGE_CARD, "/booking": BOOKING_CARD}

QUESTION = {
    "type": "object",
    "properties": {"question": {"type": "string", "description": "What the guest asked, in their words"}},
    "required": ["question"],
}
TOOLS = [
    {
        "name": "ask_booking_desk",
        "description": (
            "Ask the booking desk to search for hotels or to list the guest's bookings. "
            "Pass the guest's request unchanged in question. Use this for any hotel search or for their bookings."
        ),
        "inputSchema": QUESTION,
    },
    {
        "name": "ask_loyalty_desk",
        "description": (
            "Ask the loyalty desk in AWS for a loyalty offer. "
            "A signed-in guest gets an offer on a booking. A guest who is not signed in gets the program. "
            "Pass the guest's request unchanged in question. Use this for points, late checkout, or the loyalty desk."
        ),
        "inputSchema": QUESTION,
    },
]
# What the catalog imports. The texts match the knowledge documents, so the desk and the catalog say the same rules
PROMPTS = [
    {
        "name": "search-hotels",
        "description": "Ask the booking desk for hotels in a city.",
        "arguments": [{"name": "city", "description": "The city the guest named", "required": True}],
    },
    {
        "name": "loyalty-offer",
        "description": "Ask the loyalty desk what offer the guest gets for a stay in a city.",
        "arguments": [{"name": "city", "description": "The city of the stay", "required": True}],
    },
]
STAY_POLICY = """# ACME Hotels stay policy

This policy is simulated for the demo. It is not a real hotel rule.

## A change

A stay can be moved once, at no charge, when the new dates are free. A second change is a new booking.

## A cancellation

- More than two days before arrival: the stay is refunded in full.
- The day before arrival: one night is kept.
- The day of arrival: the stay is kept.

The booking desk searches hotels and lists the signed-in guest's bookings. It exchanges that guest's token, and the gateway checks each booking.
"""
GUEST_PRIVACY = """# ACME Hotels guest privacy

This note is simulated for the demo.

The concierge talks to the guest who is signed in. A hotel search and the list of that guest's bookings
go to the booking desk, with the guest's token. The desk exchanges that token. The gateway checks each
booking, including a booking read by its id. A loyalty offer for a booking goes to the loyalty desk with
the same token. That desk exchanges it and reads only the bookings the gateway allows. A guest who is
not signed in gets the loyalty program, not an offer on a booking, and no guest's booking.
"""
RESOURCES = [
    {
        "uri": "hotel://stay-policy",
        "name": "Stay policy",
        "description": "Simulated cancellation and change rules the booking desk would follow.",
        "mimeType": "text/markdown",
    },
    {
        "uri": "hotel://guest-privacy",
        "name": "Guest privacy",
        "description": "Simulated rule for what the concierge may say about a guest.",
        "mimeType": "text/markdown",
    },
]
RESOURCE_TEXT = {"hotel://stay-policy": STAY_POLICY, "hotel://guest-privacy": GUEST_PRIVACY}
CAPABILITIES = {"tools": {}, "prompts": {"listChanged": False}, "resources": {"subscribe": False, "listChanged": False}}


def parts_text(message):
    """The text parts of an A2A message, in order."""
    if not isinstance(message, dict):
        return ""
    found = []
    for part in message.get("parts") or []:
        if isinstance(part, dict) and part.get("text"):
            found.append(part["text"])
    return "\n".join(found)


def answer_text(payload):
    """The booking desk's reply, whether the proxy returns a message or a task."""
    result = payload.get("result") if isinstance(payload, dict) else None
    if not isinstance(result, dict):
        return ""
    text = parts_text(result) or parts_text(result.get("message"))
    if text:
        return text
    status = result.get("status") if isinstance(result.get("status"), dict) else {}
    text = parts_text(status.get("message"))
    if text:
        return text
    for artifact in result.get("artifacts") or []:
        text = parts_text(artifact)
        if text:
            return text
    return ""


def a2a_body(question):
    return {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {"message": {"role": "user", "messageId": str(uuid.uuid4()), "parts": [{"text": question}]}},
    }


def ask_agent(url, question, authorization, opener=urlopen, timeout=A2A_TIMEOUT, missing="The agent address is not set"):
    """One turn with an agent, through the gateway. The caller's token is forwarded when there is one."""
    if not url:
        raise RuntimeError(missing)
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if authorization:
        headers["Authorization"] = authorization
    request = Request(url, data=json.dumps(a2a_body(question)).encode(), headers=headers, method="POST")
    with opener(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode())
    if isinstance(payload, dict) and payload.get("error"):
        message = payload["error"].get("message") if isinstance(payload["error"], dict) else payload["error"]
        raise RuntimeError(str(message))
    text = answer_text(payload)
    if not text:
        raise RuntimeError("The agent returned no text")
    return text


def authorization_for(tool, authorization):
    """The guest token goes to the desk that answers. Each desk exchanges it when the call needs the guest."""
    if tool in ("ask_booking_desk", "ask_loyalty_desk"):
        return authorization
    return None


def ask_booking_desk(question, authorization, opener=urlopen):
    """One turn with the booking desk, through the gateway."""
    return ask_agent(A2A_URL, question, authorization, opener, A2A_TIMEOUT, "BOOKING_A2A_URL is not set")


def ask_loyalty_desk(question, authorization, opener=urlopen):
    """One turn with the loyalty desk, through the gateway."""
    return ask_agent(LOYALTY_A2A_URL, question, authorization, opener, LOYALTY_A2A_TIMEOUT, "LOYALTY_A2A_URL is not set")


def prompt_get(name, arguments):
    """The user message of a prompt, with the city filled in. None when the desk has no prompt of that name."""
    found = next((prompt for prompt in PROMPTS if prompt["name"] == name), None)
    if found is None:
        return None
    city = arguments.get("city") if isinstance(arguments, dict) else None
    city = city.strip() if isinstance(city, str) and city.strip() else "the city the guest named"
    if name == "loyalty-offer":
        text = f"Ask the loyalty desk what offer the guest gets for a stay in {city}."
    else:
        text = f"Ask the booking desk for hotels in {city}."
    return {"description": found["description"],
            "messages": [{"role": "user", "content": {"type": "text", "text": text}}]}


def resource_read(uri):
    """The text of one resource. None when the desk does not publish that URI."""
    text = RESOURCE_TEXT.get(uri)
    if text is None:
        return None
    found = next(resource for resource in RESOURCES if resource["uri"] == uri)
    return {"contents": [{"uri": uri, "mimeType": found["mimeType"], "text": text}]}


def rpc_result(body, handler, loyalty=None):
    """The JSON-RPC result for one MCP call. A notification has none."""
    if "id" not in body:
        return None
    method, params = body.get("method"), body.get("params") or {}
    if method == "initialize":
        return {"protocolVersion": PROTOCOL, "capabilities": CAPABILITIES,
                "serverInfo": {"name": SERVER_NAME, "version": "1.0.0"}}
    if method == "tools/list":
        return {"tools": TOOLS}
    if method == "prompts/list":
        return {"prompts": PROMPTS}
    if method == "prompts/get":
        found = prompt_get(params.get("name"), params.get("arguments") or {})
        return found if found is not None else {"error": {"code": -32602, "message": "Unknown prompt"}}
    if method == "resources/list":
        return {"resources": RESOURCES}
    if method == "resources/read":
        found = resource_read(params.get("uri"))
        return found if found is not None else {"error": {"code": -32002, "message": "Resource not found"}}
    asked = params.get("name")
    if method == "tools/call" and asked in ("ask_booking_desk", "ask_loyalty_desk"):
        question = (params.get("arguments") or {}).get("question")
        if not isinstance(question, str) or not question.strip():
            return {"content": [{"type": "text", "text": "Ask with a question."}], "isError": True}
        call = loyalty if asked == "ask_loyalty_desk" and loyalty is not None else handler
        try:
            text = call(question.strip(), None)
        except Exception as error:
            return {"content": [{"type": "text", "text": str(error)}], "isError": True}
        return {"content": [{"type": "text", "text": text}], "isError": False}
    return {"error": {"code": -32601, "message": f"Method not found: {method}"}}


class DeskHandler(BaseHTTPRequestHandler):
    """MCP on the desk port. The caller's Authorization is closed over per request."""

    server_version = "acme-hotels-booking-desk"

    def do_GET(self):
        if self.path.split("?", 1)[0] == "/health":
            self._send(200, b"ok", "text/plain")
            return
        self._send(404, b"not found", "text/plain")

    def do_POST(self):
        if self.path.split("?", 1)[0] != "/mcp":
            self._send(404, b"not found", "text/plain")
            return
        length = int(self.headers.get("Content-Length", "0"))
        try:
            body = json.loads(self.rfile.read(length).decode() or "{}")
        except json.JSONDecodeError:
            self._send(400, b"not json", "text/plain")
            return
        authorization = self.headers.get("Authorization")

        def booking(question, _ignored):
            return ask_booking_desk(question, authorization_for("ask_booking_desk", authorization))

        def loyalty(question, _ignored):
            return ask_loyalty_desk(question, authorization_for("ask_loyalty_desk", authorization))

        answered = rpc_result(body, booking, loyalty)
        if answered is None:
            self._send(202, b"", "application/json")
            return
        if "error" in answered and "content" not in answered:
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "error": answered["error"]}
        else:
            payload = {"jsonrpc": "2.0", "id": body.get("id"), "result": answered}
        self._send(200, json.dumps(payload).encode(), "application/json")

    def log_message(self, fmt, *args):
        return

    def _send(self, status, payload, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


class CardHandler(BaseHTTPRequestHandler):
    server_version = "acme-hotels-cards"

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/health":
            self._send(200, b"ok", "text/plain")
            return
        for prefix, card in CARDS.items():
            if path == f"{prefix}/.well-known/agent-card.json":
                self._send(200, json.dumps(card).encode(), "application/json")
                return
        self._send(404, b"not found", "text/plain")

    def log_message(self, fmt, *args):
        return

    def _send(self, status, payload, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve():
    mcp = ThreadingHTTPServer(("0.0.0.0", MCP_PORT), DeskHandler)
    cards = ThreadingHTTPServer(("0.0.0.0", CARD_PORT), CardHandler)
    threading.Thread(target=cards.serve_forever, daemon=True).start()
    mcp.serve_forever()


if __name__ == "__main__":
    serve()
