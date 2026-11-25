"""Claim checks for a delegated access token. No network and no token storage."""

import base64
import json
import time

READ_SCOPE = "submission:read"
MARK_SCOPE = "submission:mark-ready"
ACCESS_TOKEN = "urn:ietf:params:oauth:token-type:access_token"
EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"


class Closed(Exception):
    """The agent stops. It does not call the gateway and it does not retry with the subject token."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(reason)


def _segment(token):
    if token.count(".") != 2:
        raise Closed("delegated token is not a JWT")
    payload = token.split(".")[1]
    pad = "=" * (-len(payload) % 4)
    try:
        body = json.loads(base64.urlsafe_b64decode(payload + pad))
    except (ValueError, json.JSONDecodeError):
        raise Closed("delegated token payload cannot be read") from None
    if not isinstance(body, dict):
        raise Closed("delegated token payload cannot be read")
    return body


def audiences(payload):
    aud = payload.get("aud")
    if isinstance(aud, str) and aud:
        return [aud]
    if isinstance(aud, list):
        return [item for item in aud if isinstance(item, str) and item]
    return []


def assess(token, expected_sub, expected_actor, allowed_audiences, now=None):
    """Return the safe summary, or close. `token` is not returned."""
    if not token or not isinstance(token, str):
        raise Closed("delegated token is missing")
    if not expected_sub:
        raise Closed("subject is missing")
    if not expected_actor:
        raise Closed("actor is missing")
    payload = _segment(token)
    subject = payload.get("sub")
    if subject != expected_sub:
        raise Closed("subject does not match the signed-in person")
    act = payload.get("act")
    if not isinstance(act, dict) or act.get("sub") != expected_actor:
        raise Closed("actor does not match the registered agent")
    if "act" in act:
        raise Closed("delegation is deeper than one hop")
    moment = time.time() if now is None else now
    exp = payload.get("exp")
    iat = payload.get("iat")
    if not isinstance(exp, int) or exp <= moment:
        raise Closed("delegated token is expired or has no expiry")
    found = audiences(payload)
    allowed = [item for item in allowed_audiences if item]
    if not found or not allowed or not set(found) & set(allowed):
        raise Closed("delegated token audience does not match the submission resource")
    scopes = [item for item in str(payload.get("scope") or "").split() if item]
    if MARK_SCOPE in scopes:
        raise Closed("delegated token scope is wider than the agent may hold")
    if READ_SCOPE not in scopes:
        raise Closed("delegated token is missing the read scope")
    summary = {
        "iss": payload.get("iss"),
        "sub": subject,
        "act_sub": act.get("sub"),
        "scope": " ".join(scopes),
        "exp": exp,
        "expires_in": max(0, int(exp - moment)),
    }
    if isinstance(iat, int):
        summary["lifetime_seconds"] = exp - iat
    return summary


def form(subject_token, actor_token, resource):
    if not subject_token:
        raise Closed("subject token is missing")
    if not actor_token:
        raise Closed("actor token is missing")
    if subject_token == actor_token:
        raise Closed("actor token is not a distinct credential")
    body = {
        "grant_type": EXCHANGE_GRANT,
        "subject_token": subject_token,
        "subject_token_type": ACCESS_TOKEN,
        "actor_token": actor_token,
        "actor_token_type": ACCESS_TOKEN,
        "requested_token_type": ACCESS_TOKEN,
        "scope": READ_SCOPE,
    }
    if resource:
        body["resource"] = resource
    return body
