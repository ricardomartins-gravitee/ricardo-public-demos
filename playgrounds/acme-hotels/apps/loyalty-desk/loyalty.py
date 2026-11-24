"""The loyalty desk the Gravitee gateway calls.

``GET /ping`` and ``POST /invocations`` are the AgentCore runtime contract, and ``POST /`` is the A2A
message the gateway forwards. This process reads the stay through the hotels' MCP server and asks the
Gravitee LLM proxy to phrase the offer. Both addresses are the gateway, so Gravitee sees the model
call and the tool call.
"""

import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.request import Request, urlopen

PORT = int(os.environ.get("LOYALTY_PORT", "8080"))
LLM_BASE_URL = os.environ.get("LLM_BASE_URL", "http://apim-gateway:8082/llm-proxy")
LLM_MODEL = os.environ.get("LLM_MODEL", "ollama:gemma4:12b")
MCP_URL = os.environ.get("MCP_URL", "http://apim-gateway:8082/hotels-mcp/mcp")
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
        "description": "Offers points and late checkout for a hotel the guest names.",
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


def first_hotel(data):
    """The first hotel object in a tool result, in the shapes the hotels API uses."""
    if isinstance(data, list):
        return data[0] if data and isinstance(data[0], dict) else None
    if not isinstance(data, dict):
        return None
    for key in ("hotels", "items", "results", "data"):
        found = data.get(key)
        if isinstance(found, list) and found and isinstance(found[0], dict):
            return found[0]
    if data.get("name"):
        return data
    return None


def offer_facts(hotel, city):
    """The only facts the model is allowed to say. Points follow the star rating."""
    hotel = hotel or {}
    name = str(hotel.get("name") or "the hotel")
    where = str(hotel.get("city") or city or "the city")
    try:
        stars = int(float(hotel.get("stars") or hotel.get("rating") or 4))
    except (TypeError, ValueError):
        stars = 4
    stars = min(5, max(1, stars))
    points = 500 + stars * 100
    return f"{points} loyalty points and late checkout at 14:00 at {name} in {where}"


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


def mcp_call(url, name, arguments, opener=urlopen):
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


def offer(question, mcp=mcp_call, phrase=llm_phrase):
    """The loyalty offer for a question: the hotels' tools, then the model."""
    if not question:
        raise RuntimeError("Ask with a question.")
    city = city_of(question)
    arguments = {"city": city} if city else {"q": question[:200]}
    raw = mcp(MCP_URL, "searchHotels", arguments)
    hotel = first_hotel(parse_json(raw))
    facts = offer_facts(hotel, city)
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


def respond(method, path, raw, offer_fn=offer):
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
            text = offer_fn(question_of(body))
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
        status, payload, content_type = respond("POST", self.path, self.rfile.read(length))
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
