#!/bin/sh
# Gravitee public ACME Hotels creates a service application, client id hotel-ai-agent, in this
# same domain. The seeder does not delete an application whose file is gone, so this removes
# that client when it is still there. Then the seed runs.
set -e
python - << 'PY'
import base64
import json
import os
import time
import urllib.error
import urllib.request

base = os.environ["AM_MANAGEMENT_URL"].rstrip("/")
org = os.environ.get("AM_ORG", "DEFAULT")
env = os.environ.get("AM_ENV", "DEFAULT")
retired = "hotel-ai-agent"
token = base64.b64encode(f"{os.environ['AM_USERNAME']}:{os.environ['AM_PASSWORD']}".encode()).decode()


def call(method, path, bearer=None):
    headers = {"Authorization": f"Bearer {bearer}" if bearer else f"Basic {token}"}
    request = urllib.request.Request(base + path, headers=headers, method=method, data=b"" if method == "POST" else None)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode()
        raise SystemExit(f"Access Management {method} {path} failed: {error.code} {detail[:180]}")


def login():
    status, body = call("POST", "/management/auth/token")
    if status != 200 or not isinstance(body, dict) or "access_token" not in body:
        raise SystemExit(f"Access Management login failed: {status}")
    return body["access_token"]


bearer = None
for _ in range(10):
    try:
        bearer = login()
        break
    except SystemExit:
        time.sleep(2)
if not bearer:
    raise SystemExit("Access Management did not accept a login")

root = f"/management/organizations/{org}/environments/{env}"
status, domains = call("GET", f"{root}/domains", bearer)
rows = domains.get("data") if isinstance(domains, dict) else domains
domain = next((row for row in rows or [] if row.get("name") == "acme-hotels"), None)
if domain is None:
    raise SystemExit(0)

domain_url = f"{root}/domains/{domain['id']}"
status, apps = call("GET", f"{domain_url}/applications?size=100", bearer)
rows = apps.get("data") if isinstance(apps, dict) else apps
for app in rows or []:
    status, detail = call("GET", f"{domain_url}/applications/{app['id']}", bearer)
    oauth = (detail.get("settings") or {}).get("oauth") or {}
    if oauth.get("clientId") != retired:
        continue
    call("DELETE", f"{domain_url}/applications/{app['id']}", bearer)
    print(f"Removed {detail.get('name')}: the public playground's client is not part of this one", flush=True)
PY
python seed.py "$@"
