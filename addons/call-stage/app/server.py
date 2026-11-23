"""Call Stage: a page that sends the HTTP calls a file names and shows the path of each one.

The browser never calls the target. It asks this process, which calls only an id from the file,
so the page is not an open proxy. A header value written ${NAME} is read from the environment.
A call with "keyFrom": "input" takes the key from the request body and does not store it.
A call with "token" asks Access Management for a client-credentials token and sends it as Bearer. The secret stays here.
"""

import base64
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
CALLS_FILE = Path(os.environ.get("CALLS_FILE", HERE / "calls.json"))
PORT = int(os.environ.get("HTTP_PORT", "8080"))
SETTING = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
SECRET = re.compile(r"key|token|secret|password|authorization", re.I)
REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{8,80}$")
API_ID = re.compile(r"^[A-Za-z0-9-]+$")
BODY_LIMIT = 64_000
FRAMES = "frame-ancestors 'self' http://localhost:9000 http://127.0.0.1:9000"
_API_LIST = {"key": None, "at": 0, "rows": None}


def substitute(value, environ):
    """Replace ${NAME} with the environment. A missing name is an error, not the raw text."""
    missing = []

    def one(match):
        name = match.group(1)
        if name not in environ or environ[name] == "":
            missing.append(name)
            return ""
        return environ[name]

    text = SETTING.sub(one, value)
    return text, missing


def mask(headers):
    """Header values a person can show. A credential is replaced, never returned."""
    shown = {}
    for name, value in headers.items():
        shown[name] = "••••" if SECRET.search(name) else value
    return shown


def load_calls(environ=None):
    """The file, with settings filled in. Raises ValueError when the file or a setting is wrong."""
    environ = os.environ if environ is None else environ
    try:
        spec = json.loads(CALLS_FILE.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"No calls file at {CALLS_FILE}") from None
    except json.JSONDecodeError as error:
        raise ValueError(f"The calls file is not JSON: {error}") from None
    if not isinstance(spec, dict) or not isinstance(spec.get("calls"), list):
        raise ValueError("The calls file needs a calls list")
    ready = []
    for call in spec["calls"]:
        if not isinstance(call, dict) or not call.get("id") or not call.get("url"):
            raise ValueError("Each call needs an id and a url")
        url, missing = substitute(str(call["url"]), environ)
        headers, header_gaps = {}, []
        for name, value in (call.get("headers") or {}).items():
            filled, gaps = substitute(str(value), environ)
            headers[str(name)] = filled
            header_gaps.extend(gaps)
        token, token_gaps = read_token(call.get("token"), environ)
        ready.append({
            "id": str(call["id"]),
            "name": str(call.get("name") or call["id"]),
            "method": str(call.get("method") or "GET").upper(),
            "url": url,
            "show": str(call.get("show") or url),
            "headers": headers,
            "keyHeader": call.get("keyHeader") or "",
            "keyFrom": str(call.get("keyFrom") or ""),
            "token": token,
            "group": str(call.get("group") or ""),
            "panel": str(call.get("panel") or ""),
            "hint": str(call.get("hint") or ""),
            "missing": missing + header_gaps + token_gaps,
        })
    return {"title": str(spec.get("title") or "Call stage"), "calls": ready}


def read_token(spec, environ):
    """The client-credentials settings of a call, with ${NAME} filled. (None, []) when the call asks for none."""
    if spec is None:
        return None, []
    if not isinstance(spec, dict) or not spec.get("url") or not spec.get("clientId"):
        raise ValueError("A token needs a url and a clientId")
    url, missing = substitute(str(spec["url"]), environ)
    secret, gaps = substitute(str(spec.get("clientSecret") or ""), environ)
    return {
        "url": url,
        "clientId": str(spec["clientId"]),
        "clientSecret": secret,
        "scope": str(spec.get("scope") or ""),
    }, missing + gaps


def access_token(token):
    """A client-credentials access token. The secret is not returned."""
    form = {"grant_type": "client_credentials"}
    if token["scope"]:
        form["scope"] = token["scope"]
    request = urllib.request.Request(
        token["url"], data=urllib.parse.urlencode(form).encode(), method="POST",
        headers={
            "Authorization": "Basic " + base64.b64encode(
                f"{token['clientId']}:{token['clientSecret']}".encode()).decode("ascii"),
            "Accept": "application/json",
            "Content-Type": "application/x-www-form-urlencoded",
        })
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            issued = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError:
        return None, "Access Management refused the token"
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError):
        return None, "Access Management could not be reached"
    access = issued.get("access_token") if isinstance(issued, dict) else None
    if not isinstance(access, str) or not access:
        return None, "Access Management returned no access token"
    return access, None


def public_calls(spec):
    """What the page lists. URLs and header names only, with credential values removed."""
    listed = []
    for call in spec["calls"]:
        listed.append({
            "id": call["id"],
            "name": call["name"],
            "method": call["method"],
            "show": call["show"],
            "needsKey": call["keyFrom"] == "input",
            "group": call["group"],
            "panel": call["panel"],
            "hint": call["hint"],
            "missing": call["missing"],
        })
    return {"title": spec["title"], "calls": listed}


def _json_body(text):
    try:
        json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return False
    return bool(text and str(text).strip())


def management_settings(environ=None):
    """Where to read Gravitee's own log. Absent when the page is not given a management API."""
    environ = os.environ if environ is None else environ
    url = str(environ.get("CALL_STAGE_MANAGEMENT_URL") or "").rstrip("/")
    user = str(environ.get("CALL_STAGE_MANAGEMENT_USERNAME") or "")
    password = str(environ.get("CALL_STAGE_MANAGEMENT_PASSWORD") or "")
    if not url or not user or not password:
        return None
    return {
        "url": url,
        "user": user,
        "password": password,
        "org": str(environ.get("CALL_STAGE_MANAGEMENT_ORG") or "DEFAULT"),
        "env": str(environ.get("CALL_STAGE_MANAGEMENT_ENV") or "DEFAULT"),
    }


def _authorization(settings):
    raw = f"{settings['user']}:{settings['password']}".encode()
    return "Basic " + base64.b64encode(raw).decode("ascii")


def _http_json(url, authorization):
    request = urllib.request.Request(url, headers={"Authorization": authorization, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        return error.code, {}
    except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, ValueError):
        return 0, {}


def _covers(prefix, path):
    prefix = "/" + str(prefix or "").strip("/")
    path = "/" + str(path or "").strip("/")
    if prefix == "/":
        return False
    return path == prefix or path.startswith(prefix + "/")


def match_api(apis, path):
    """The API whose listener path is the longest prefix of this request path."""
    best, best_len = None, -1
    for api in apis or []:
        for listener in api.get("listeners") or []:
            for item in listener.get("paths") or []:
                prefix = str((item or {}).get("path") or "")
                if _covers(prefix, path) and len(prefix.strip("/")) > best_len:
                    best, best_len = api, len(prefix.strip("/"))
    return best


def _named(value):
    text = str(value or "").strip()
    return "" if text.lower() == "unknown" else text


def project_log(row):
    """The part of a Gravitee log a person can read. No ids, headers or secrets."""
    if not isinstance(row, dict):
        return None
    gateway = row.get("gatewayResponseTime")
    return {
        "message": str(row.get("message") or ""),
        "plan": _named((row.get("plan") or {}).get("name")),
        "application": _named((row.get("application") or {}).get("name")),
        "gatewayMs": gateway if isinstance(gateway, (int, float)) else None,
        "method": str(row.get("method") or ""),
        "uri": str(row.get("uri") or ""),
    }


def _apis(settings, opener, now, cache):
    key = (settings["url"], settings["org"], settings["env"])
    if cache.get("key") == key and cache.get("rows") is not None and now - cache.get("at", 0) < 30:
        return cache["rows"]
    url = (
        f"{settings['url']}/management/v2/organizations/{urllib.parse.quote(settings['org'])}"
        f"/environments/{urllib.parse.quote(settings['env'])}/apis?perPage=100"
    )
    status, body = opener(url, _authorization(settings))
    rows = body.get("data") if status == 200 and isinstance(body, dict) else []
    cache["key"], cache["at"], cache["rows"] = key, now, rows if isinstance(rows, list) else []
    return cache["rows"]


def gravitee_log(settings, request_id, path, opener=None, now_ms=None, sleep=time.sleep, attempts=24, pause=0.5, cache=None):
    """The management-API log for this gateway request. The log is written after the call, so this waits for it.

    A management API that refuses, or a request id that is not a single token, returns nothing. Only a missing row is retried.
    """
    if settings is None or not REQUEST_ID.fullmatch(str(request_id or "")):
        return None
    opener = _http_json if opener is None else opener
    now_ms = int(time.time() * 1000) if now_ms is None else now_ms
    cache = _API_LIST if cache is None else cache
    api = match_api(_apis(settings, opener, now_ms / 1000, cache), path)
    api_id = str((api or {}).get("id") or "")
    if not API_ID.fullmatch(api_id):
        return None
    base = (
        f"{settings['url']}/management/v2/organizations/{urllib.parse.quote(settings['org'])}"
        f"/environments/{urllib.parse.quote(settings['env'])}/apis/{api_id}/logs"
    )
    authorization = _authorization(settings)
    for attempt in range(attempts):
        window = urllib.parse.urlencode({"from": now_ms - 120_000, "to": now_ms + 60_000, "page": 1, "perPage": 20})
        status, body = opener(f"{base}?{window}", authorization)
        if status != 200 or not isinstance(body, dict):
            return None
        found = next((row for row in body.get("data") or [] if row.get("requestId") == request_id), None)
        if found:
            return project_log(found)
        if attempt + 1 < attempts:
            sleep(pause)
            now_ms += int(pause * 1000)
    return None


def trace(status, body, response_headers):
    """Who took part in this call, read from the response. Nothing here is chosen before the call runs.

    A Gravitee header means Gravitee was on the path. A JSON body means the API answered. A Gravitee
    rejection is not JSON, so the API is not part of that call.
    """
    via = any(str(name).lower().startswith("x-gravitee-") for name in response_headers)
    answered = _json_body(body)
    participants = ["client"]
    if via:
        participants.append("gravitee")
    if answered or not via:
        participants.append("api")
    return {"participants": participants, "viaGravitee": via, "apiAnswered": answered or not via}


def perform(call, key):
    """Send one configured call. The key is added only when the file asks the page for it."""
    if call["missing"]:
        return {"error": "Missing setting: " + ", ".join(call["missing"])}
    headers = dict(call["headers"])
    if call["keyFrom"] == "input":
        if not key:
            return {"error": "Paste the key first"}
        headers[call["keyHeader"] or "X-Gravitee-Api-Key"] = key
    if call.get("token"):
        access, problem = access_token(call["token"])
        if problem:
            return {"error": problem}
        headers["Authorization"] = "Bearer " + access
    request = urllib.request.Request(call["url"], method=call["method"], headers=headers)
    started = time.perf_counter()
    response_headers = {}
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            body = response.read(BODY_LIMIT + 1)
            status = response.status
            response_headers = mask(dict(response.headers.items()))
    except urllib.error.HTTPError as error:
        body = error.read(BODY_LIMIT + 1)
        status = error.code
        response_headers = mask(dict(error.headers.items())) if error.headers else {}
    except urllib.error.URLError as error:
        return {"error": str(error.reason)}
    elapsed = int((time.perf_counter() - started) * 1000)
    text = body[:BODY_LIMIT].decode("utf-8", "replace")
    return {
        "status": status,
        "elapsed": elapsed,
        "body": text,
        "truncated": len(body) > BODY_LIMIT,
        "request": {"method": call["method"], "url": call["show"], "headers": mask(headers)},
        "responseHeaders": response_headers,
        "trace": trace(status, text, response_headers),
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _send(self, status, body, content_type):
        data = body if isinstance(body, bytes) else body.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", FRAMES)
        self.end_headers()
        self.wfile.write(data)

    def _json(self, status, payload):
        self._send(status, json.dumps(payload), "application/json")

    def _file(self, name, content_type):
        path = HERE / name
        if not path.is_file():
            self._json(404, {"error": "missing"})
            return
        self._send(200, path.read_bytes(), content_type)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path in ("/", "/index.html"):
            self._file("index.html", "text/html; charset=utf-8")
        elif parsed.path == "/app.css":
            self._file("app.css", "text/css; charset=utf-8")
        elif parsed.path == "/app.js":
            self._file("app.js", "text/javascript; charset=utf-8")
        elif parsed.path == "/health":
            self._json(200, {"status": "ok"})
        elif parsed.path == "/api/calls":
            try:
                self._json(200, public_calls(load_calls()))
            except ValueError as error:
                self._json(500, {"error": str(error)})
        elif parsed.path == "/api/gravitee":
            query = urllib.parse.parse_qs(parsed.query)
            request_id = (query.get("requestId") or [""])[0]
            path = (query.get("path") or [""])[0]
            if not REQUEST_ID.fullmatch(request_id):
                self._json(400, {"error": "That request id is not usable"})
                return
            log = gravitee_log(management_settings(), request_id, path)
            self._json(200, {"log": log})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if not self.path.startswith("/api/calls/"):
            self._json(404, {"error": "not found"})
            return
        call_id = self.path.removeprefix("/api/calls/").split("?", 1)[0]
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(min(length, 8000)) if length else b""
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._json(400, {"error": "The body is not JSON"})
            return
        try:
            spec = load_calls()
        except ValueError as error:
            self._json(500, {"error": str(error)})
            return
        call = next((item for item in spec["calls"] if item["id"] == call_id), None)
        if call is None:
            self._json(404, {"error": "That call is not configured"})
            return
        result = perform(call, str((body or {}).get("key") or ""))
        self._json(200 if "status" in result else 400, result)


def main():
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
