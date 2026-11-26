#!/bin/sh
# The seeder keeps an application it finds by client id, including its type. The booking desk and the
# loyalty desk are hosted delegated agents. An earlier seed may have left them as service applications.
# Access Management has no call that changes that type, so this removes those two and the seed creates
# the agents. An application that is already an agent is left as it is.
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
clients = {"acme-hotels-booking-desk", "acme-hotels-loyalty-desk"}
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
    client = oauth.get("clientId")
    if client == retired:
        call("DELETE", f"{domain_url}/applications/{app['id']}", bearer)
        print(f"Removed {detail.get('name')}: that client no longer exchanges a token", flush=True)
        continue
    if client not in clients or str(detail.get("type") or "").lower() == "agent":
        continue
    call("DELETE", f"{domain_url}/applications/{app['id']}", bearer)
    print(f"Removed {detail.get('name')}: it was a service application, and the seed creates the agent", flush=True)
PY

# Gamma keeps one Access Management link for the environment. The seeder will not move a link that
# already serves another domain, so this points Agent Identity at acme-hotels before and after the seed.
point_gamma() {
python - << 'PY'
import base64
import json
import os
import urllib.error
import urllib.request

am = os.environ["AM_MANAGEMENT_URL"].rstrip("/")
apim = os.environ["APIM_MANAGEMENT_URL"].rstrip("/")
org = os.environ.get("AM_ORG", "DEFAULT")
env = os.environ.get("AM_ENV", "DEFAULT")
am_basic = base64.b64encode(f"{os.environ['AM_USERNAME']}:{os.environ['AM_PASSWORD']}".encode()).decode()
apim_basic = base64.b64encode(f"{os.environ['APIM_USERNAME']}:{os.environ['APIM_PASSWORD']}".encode()).decode()


def request(root, method, path, basic, body=None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Authorization": f"Basic {basic}"}
    if data is not None:
        headers["Content-Type"] = "application/json"
    call = urllib.request.Request(root + path, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(call, timeout=20) as response:
            raw = response.read().decode()
            return response.status, json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode()
        raise SystemExit(f"{method} {path} failed: {error.code} {detail[:180]}")


login = urllib.request.Request(
    am + "/management/auth/token",
    data=b"",
    headers={"Authorization": f"Basic {am_basic}"},
    method="POST",
)
with urllib.request.urlopen(login, timeout=20) as response:
    token_body = json.load(response)
bearer = token_body.get("access_token") if isinstance(token_body, dict) else None
if not bearer:
    raise SystemExit(f"Access Management login failed: {status}")

def am_get(path):
    call = urllib.request.Request(am + path, headers={"Authorization": f"Bearer {bearer}"})
    with urllib.request.urlopen(call, timeout=20) as response:
        return json.load(response)

root = f"/management/organizations/{org}/environments/{env}"
rows = am_get(f"{root}/domains")
rows = rows.get("data") if isinstance(rows, dict) else rows
domain = next((row for row in rows or [] if row.get("name") == "acme-hotels"), None)
if domain is None:
    raise SystemExit(0)
detail = am_get(f"{root}/domains/{domain['id']}")
hrid = detail.get("hrid") or detail.get("name") or "acme-hotels"

gamma = f"/gamma/organizations/{org}/environments/{env}/modules/platform/am/am-config"
status, saved = request(apim, "GET", gamma, apim_basic)
if not isinstance(saved, dict) or not saved.get("hasAccessToken"):
    raise SystemExit(0)
if saved.get("defaultDomainId") == detail["id"]:
    raise SystemExit(0)
previous = saved.get("defaultDomainHrid") or saved.get("defaultDomainId")
wanted = {
    "baseUrl": os.environ["AM_MANAGEMENT_URL"],
    "amOrganizationId": org,
    "environmentId": env,
    "defaultDomainId": detail["id"],
    "defaultDomainHrid": hrid,
    "gatewayUrl": os.environ["AM_PUBLIC_URL"],
}
request(apim, "PUT", gamma, apim_basic, wanted)
print(f"Agent Identity now lists {hrid}. It was {previous}.", flush=True)
PY
}

point_gamma
python seed.py "$@"
point_gamma
