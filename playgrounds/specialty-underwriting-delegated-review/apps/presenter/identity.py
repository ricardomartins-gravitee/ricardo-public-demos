"""Safe fields of an access token. The token itself is not returned."""

import base64
import json
import time


class Closed(Exception):
    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def claims(token, now=None):
    if not token or token.count(".") != 2:
        raise Closed("access token cannot be read")
    payload = token.split(".")[1]
    try:
        body = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (ValueError, json.JSONDecodeError):
        raise Closed("access token cannot be read") from None
    if not isinstance(body, dict) or not body.get("sub"):
        raise Closed("access token has no subject")
    moment = time.time() if now is None else now
    exp = body.get("exp")
    if not isinstance(exp, int) or exp <= moment:
        raise Closed("access token is expired or has no expiry")
    iat = body.get("iat")
    summary = {
        "iss": body.get("iss"),
        "sub": body.get("sub"),
        "scope": body.get("scope") or "",
        "exp": exp,
        "expires_in": max(0, int(exp - moment)),
    }
    if isinstance(iat, int):
        summary["lifetime_seconds"] = exp - iat
    return summary
