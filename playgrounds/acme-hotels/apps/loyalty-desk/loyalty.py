"""The loyalty desk the Gravitee gateway calls.

``GET /ping`` and ``POST /invocations`` are the AgentCore runtime contract, and ``POST /`` is the A2A
message the gateway forwards. This process reads the stay through the hotels' MCP server and asks the
Gravitee LLM proxy to phrase the offer. Both addresses are the gateway, so Gravitee sees the model
call and the tool call.
"""

import base64
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

PORT = int(os.environ.get("LOYALTY_PORT", "8080"))
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://apim-gateway:8082/llm-proxy")
LLM_MODEL = os.environ.get("LLM_MODEL", "ollama:gemma4:12b")
HOTELS_MCP_URL = os.environ.get("HOTELS_MCP_URL", "http://apim-gateway:8082/hotels/mcp")
AM_TOKEN_URL = os.environ.get("AM_TOKEN_URL", "http://am-gateway:8092/acme-hotels/oauth/token")
AM_CLIENT_ID = os.environ.get("AM_CLIENT_ID", "acme-hotels-loyalty-desk")
AM_CLIENT_SECRET = os.environ.get("AM_CLIENT_SECRET", "")
MCP_TIMEOUT = int(os.environ.get("LOYALTY_MCP_TIMEOUT", "5"))
LLM_TIMEOUT = int(os.environ.get("LOYALTY_LLM_TIMEOUT", "60"))
PROTOCOL = "2025-11-25"
CITIES = ("paris", "london", "tokyo", "new york")
THINKING = re.compile(r"<think>.*?</think>", re.DOTALL)

CARD = {
    "name": "ACME Hotels Loyalty Desk",
    "version": "1.0.0",
    "description": (
        "Writes a loyalty offer for a stay. It is the Bedrock AgentCore runtime in the local AWS account, "
        "and it calls the Gravitee LLM proxy and the hotels' tools."
    ),
    "supportedInterfaces": [{"url": "http://localhost:8082/loyalty-desk/", "protocolBinding": "JSONRPC"}],
    "capabilities": {"streaming": False},
    "skills": [{
        "id": "loyalty-offer",
        "name": "Loyalty offer",
        "description": "Offers the loyalty program, and points on a booking when the guest is signed in.",
        "tags": ["hotel", "loyalty"],
    }],
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
}


def parts_text(message):
    """The text parts of an A2A message, in order."""
    if not isinstance(message, dict):
        return ""
    found = []
    for part in message.get("parts") or []:
        if isinstance(part, dict) and part.get("text"):
            found.append(part["text"])
    return "\n".join(found)


def question_of(body):
    """The guest's words, from an A2A message or a plain prompt."""
    if not isinstance(body, dict):
        return ""
    if body.get("method") == "message/send":
        message = (body.get("params") or {}).get("message") or {}
        return parts_text(message).strip()
    if isinstance(body.get("prompt"), str):
        return body["prompt"].strip()
    return ""


def city_of(question):
    """A city named in the question, or nothing."""
    lowered = question.lower()
    for city in CITIES:
        if city in lowered:
            return "New York" if city == "new york" else city.title()
    return ""


def parse_json(text):
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        return None


GENERIC = (
    "500 to 1000 loyalty points on a stay and late checkout at 14:00. "
    "Sign in to see the offer on your booking."
)


def bearer(authorization):
    """The access token of a Bearer header, or nothing."""
    if not authorization:
        return ""
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return ""
    return token.strip()


def bookings_of(raw):
    """Booking objects in a tool result."""
    data = parse_json(raw)
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if not isinstance(data, dict):
        return []
    for key in ("bookings", "items", "results", "data"):
        found = data.get(key)
        if isinstance(found, list):
            return [item for item in found if isinstance(item, dict)]
    return []


def booking_for(bookings, city):
    """The stay the offer is for: one in the named city, or the first when no city was named."""
    if not bookings:
        return None
    if not city:
        return bookings[0]
    needle = city.lower()
    for booking in bookings:
        blob = " ".join(str(booking.get(key) or "") for key in ("hotel_name", "hotel_id", "city")).lower()
        if needle in blob:
            return booking
    return None


def booking_facts(booking):
    """The only facts the model may say about a stay the guest may see."""
    name = str(booking.get("hotel_name") or "the hotel")
    stay = str(booking.get("id") or "the stay")
    return f"1000 loyalty points and late checkout at 14:00 on booking {stay} at {name}"


def generic_facts(city=""):
    """The program, when there is no signed-in stay to attach an offer to."""
    if city:
        return f"No booking in {city} to attach an offer to. {GENERIC}"
    return GENERIC


def model_text(payload):
    """The assistant text of an OpenAI chat completion, without a reasoning trace."""
    if not isinstance(payload, dict):
        return ""
    choices = payload.get("choices") or []
    if not choices or not isinstance(choices[0], dict):
        return ""
    message = choices[0].get("message") or {}
    text = message.get("content") if isinstance(message, dict) else ""
    if not isinstance(text, str):
        return ""
    return THINKING.sub("", text).strip()


def read_body(response):
    """JSON from a response, including an SSE body that carries one JSON event."""
    raw = response.read().decode()
    headers = getattr(response, "headers", None)
    content_type = headers.get("Content-Type", "") if headers is not None else ""
    if "text/event-stream" in content_type:
        events = [line[5:].strip() for line in raw.splitlines() if line.startswith("data:")]
        raw = events[-1] if events else "{}"
    return json.loads(raw or "{}")


def header(response, name):
    headers = getattr(response, "headers", None)
    if headers is None:
        return ""
    return headers.get(name) or ""


def mcp_call(url, name, arguments, opener=urlopen, authorization=""):
    """One MCP tool call. The session header from initialize is sent with the call."""
    session = {}

    def post(payload, note=False):
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": PROTOCOL,
        }
        if session.get("id"):
            headers["Mcp-Session-Id"] = session["id"]
        if authorization:
            headers["Authorization"] = authorization
        request = Request(url, data=json.dumps(payload).encode(), headers=headers, method="POST")
        with opener(request, timeout=MCP_TIMEOUT) as response:
            found = header(response, "Mcp-Session-Id")
            if found:
                session["id"] = found
            if note:
                return None
            return read_body(response)

    post({
        "jsonrpc": "2.0", "id": 1, "method": "initialize",
        "params": {"protocolVersion": PROTOCOL, "capabilities": {},
                   "clientInfo": {"name": "acme-hotels-loyalty", "version": "1.0.0"}},
    })
    post({"jsonrpc": "2.0", "method": "notifications/initialized"}, note=True)
    answered = post({
        "jsonrpc": "2.0", "id": 2, "method": "tools/call",
        "params": {"name": name, "arguments": arguments},
    })
    if not isinstance(answered, dict):
        raise RuntimeError("The hotels' tools returned nothing")
    if answered.get("error"):
        message = answered["error"].get("message") if isinstance(answered["error"], dict) else answered["error"]
        raise RuntimeError(str(message))
    result = answered.get("result") if isinstance(answered.get("result"), dict) else {}
    if result.get("isError"):
        raise RuntimeError(parts_text({"parts": result.get("content")}) or "The hotels' tools failed")
    texts = []
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("text"):
            texts.append(block["text"])
    return "\n".join(texts)


class Blocked(RuntimeError):
    """The gateway's guard rails rejected the guest's words."""


class NotSignedIn(RuntimeError):
    """The guest token could not be exchanged, so the offer stays the program."""


def exchange(subject, opener=urlopen):
    """RFC 8693 delegation. The loyalty desk is the actor, once, for this guest."""
    if not AM_TOKEN_URL or not AM_CLIENT_ID or not AM_CLIENT_SECRET:
        raise NotSignedIn("The loyalty desk has no Access Management client")
    basic = base64.b64encode(f"{AM_CLIENT_ID}:{AM_CLIENT_SECRET}".encode()).decode()

    def token(fields):
        request = Request(
            AM_TOKEN_URL,
            data=urlencode(fields).encode(),
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Accept": "application/json",
                "Authorization": f"Basic {basic}",
            },
            method="POST",
        )
        try:
            with opener(request, timeout=30) as response:
                payload = read_body(response)
        except HTTPError as error:
            error.read()
            if error.code in (400, 401, 403):
                raise NotSignedIn("The guest is not signed in") from None
            raise RuntimeError(f"Access Management refused the exchange ({error.code})") from None
        if not isinstance(payload, dict) or not payload.get("access_token"):
            raise NotSignedIn("The guest is not signed in")
        return payload["access_token"]

    actor = token({"grant_type": "client_credentials"})
    return token({
        "grant_type": "urn:ietf:params:oauth:grant-type:token-exchange",
        "subject_token": subject,
        "subject_token_type": "urn:ietf:params:oauth:token-type:access_token",
        "actor_token": actor,
        "actor_token_type": "urn:ietf:params:oauth:token-type:access_token",
    })


def screen(question, opener=urlopen):
    """The guest's words go to the LLM proxy before any search, so the guard rails can reject them."""
    if not LLM_BASE_URL:
        raise RuntimeError("LLM_BASE_URL is not set")
    payload = {
        "model": LLM_MODEL,
        "temperature": 0,
        "max_tokens": 1,
        "messages": [{"role": "user", "content": question}],
    }
    request = Request(
        LLM_BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with opener(request, timeout=LLM_TIMEOUT) as response:
            read_body(response)
    except HTTPError as error:
        detail = error.read().decode(errors="replace")
        if error.code in (400, 403) or "MALICIOUS" in detail:
            raise Blocked("Your request was blocked because it was deemed invalid or unsafe.") from None
        raise RuntimeError(f"The model refused the question ({error.code})") from None


def llm_phrase(facts, opener=urlopen):
    """One sentence from the LLM proxy. The facts are the whole brief."""
    if not LLM_BASE_URL:
        raise RuntimeError("LLM_BASE_URL is not set")
    payload = {
        "model": LLM_MODEL,
        "temperature": 0,
        "messages": [{
            "role": "user",
            "content": (
                "You are the ACME Hotels loyalty desk. "
                f"Write one sentence offering exactly this, and nothing else: {facts}"
            ),
        }],
    }
    request = Request(
        LLM_BASE_URL.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with opener(request, timeout=LLM_TIMEOUT) as response:
        text = model_text(read_body(response))
    if not text:
        raise RuntimeError("The model returned no offer")
    return text


def offer(question, mcp=mcp_call, phrase=llm_phrase, screen=screen, *, authorization="", exchange=exchange):
    """The program for a guest who is not signed in, or points on a booking they may see."""
    if not question:
        raise RuntimeError("Ask with a question.")
    screen(question)
    subject = bearer(authorization)
    if not subject:
        return phrase(GENERIC)
    try:
        token = exchange(subject)
        raw = mcp(HOTELS_MCP_URL, "listBookings", {}, authorization=f"Bearer {token}")
    except NotSignedIn:
        return phrase(GENERIC)
    except RuntimeError:
        return phrase(GENERIC)
    city = city_of(question)
    booking = booking_for(bookings_of(raw), city)
    facts = booking_facts(booking) if booking is not None else generic_facts(city)
    return phrase(facts)


def a2a_result(body, text):
    return {
        "jsonrpc": "2.0",
        "id": body.get("id") if isinstance(body, dict) else None,
        "result": {"role": "agent", "parts": [{"text": text}]},
    }


def a2a_error(body, message):
    return {"jsonrpc": "2.0", "id": body.get("id") if isinstance(body, dict) else None,
            "error": {"code": -32000, "message": message}}


def respond(method, path, raw, offer_fn=offer, authorization=""):
    """The status and body for one request the gateway or AgentCore would send."""
    path = path.split("?", 1)[0]
    if method == "GET" and path == "/ping":
        return 200, json.dumps({"status": "Healthy"}).encode(), "application/json"
    if method == "GET" and path == "/health":
        return 200, b"ok", "text/plain"
    if method == "GET" and path == "/.well-known/agent-card.json":
        return 200, json.dumps(CARD).encode(), "application/json"
    if method == "POST" and path in ("/invocations", "/"):
        try:
            body = json.loads(raw.decode() or "{}")
        except (ValueError, UnicodeDecodeError):
            body = {}
        try:
            text = offer_fn(question_of(body), authorization=authorization)
        except Blocked as error:
            return 200, json.dumps(a2a_result(body, str(error))).encode(), "application/json"
        except Exception as error:
            return 200, json.dumps(a2a_error(body, str(error))).encode(), "application/json"
        return 200, json.dumps(a2a_result(body, text)).encode(), "application/json"
    return 404, b"not found", "text/plain"


class Handler(BaseHTTPRequestHandler):
    server_version = "acme-hotels-loyalty"

    def do_GET(self):
        status, payload, content_type = respond("GET", self.path, b"")
        self._send(status, payload, content_type)

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        status, payload, content_type = respond(
            "POST", self.path, self.rfile.read(length), authorization=self.headers.get("Authorization") or "")
        self._send(status, payload, content_type)

    def log_message(self, fmt, *args):
        return

    def _send(self, status, payload, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)


def serve():
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    serve()
