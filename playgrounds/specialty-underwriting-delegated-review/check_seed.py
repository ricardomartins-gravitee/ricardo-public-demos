"""Static checks for the playground files. Run from the playground directory."""

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent
BANNED = ("nhs", "nusantara", "okta", "sailpoint", "proxygen")


def main():
    files = [path for path in ROOT.rglob("*") if path.is_file() and path.suffix != ".pyc" and path.name != "check_seed.py"]
    text = "\n".join(path.read_text(encoding="utf-8") for path in files)
    lowered = text.lower()
    found = [word for word in BANNED if word in lowered]
    if found:
        print("banned words: " + ", ".join(found))
        return 1
    policy = (ROOT / "seed/authz/policies/02-agent-cannot-mark-ready.yaml").read_text(encoding="utf-8")
    if "context has agent" not in policy or "mark_ready_for_quote" not in policy:
        print("agent forbid is missing")
        return 1
    domain = (ROOT / "seed/am/domain.yaml").read_text(encoding="utf-8")
    if "allowImpersonation: false" not in domain or "scopeHandling: downscoping" not in domain:
        print("token exchange is not delegation with downscoping")
        return 1
    web = (ROOT / "seed/am/applications/review-web.yaml").read_text(encoding="utf-8")
    grants = web.split("grantTypes:", 1)[-1].split("responseTypes:", 1)[0]
    if "- password" in grants or "client_credentials" in grants:
        print("the review page client has a grant it should not")
        return 1
    proxy = (ROOT / "seed/aim/mcp-proxies/submissions.yaml").read_text(encoding="utf-8")
    if "payload: false" not in proxy or "headers: false" not in proxy:
        print("gateway logging still records headers or payloads")
        return 1
    if "mcp-acl" in proxy:
        print("a tool list filter is not part of this proof")
        return 1
    print("seed contract ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
