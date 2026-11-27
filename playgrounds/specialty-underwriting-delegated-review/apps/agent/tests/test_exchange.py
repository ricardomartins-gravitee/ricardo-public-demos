import base64
import json
import time
import unittest

import exchange


def jwt(payload):
    raw = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    return f"header.{raw}.sig"


def delegated(**extra):
    now = int(time.time())
    body = {
        "iss": "http://am.example/specialty-underwriting",
        "sub": "human-1",
        "act": {"sub": "cyber-review-agent"},
        "aud": "http://apim-gateway:8082/specialty-underwriting/mcp",
        "scope": "submission:read",
        "iat": now,
        "exp": now + 600,
    }
    body.update(extra)
    return jwt(body)


class AssessTest(unittest.TestCase):
    def assess(self, token, **kwargs):
        values = {"expected_sub": "human-1", "expected_actor": "cyber-review-agent",
                  "allowed_audiences": ["http://apim-gateway:8082/specialty-underwriting/mcp", "specialty-underwriting-mcp"]}
        values.update(kwargs)
        return exchange.assess(token, **values)

    def test_summary_keeps_subject_and_actor(self):
        summary = self.assess(delegated())
        self.assertEqual(summary["sub"], "human-1")
        self.assertEqual(summary["act_sub"], "cyber-review-agent")
        self.assertEqual(summary["scope"], "submission:read")
        self.assertEqual(summary["lifetime_seconds"], 600)
        self.assertNotIn("access_token", summary)

    def test_expired_token_is_closed(self):
        with self.assertRaises(exchange.Closed) as caught:
            self.assess(delegated(exp=int(time.time()) - 5))
        self.assertIn("expired", caught.exception.reason)

    def test_wrong_audience_is_closed(self):
        with self.assertRaises(exchange.Closed) as caught:
            self.assess(delegated(aud="http://other.example/mcp"))
        self.assertIn("audience", caught.exception.reason)

    def test_missing_audience_is_closed(self):
        token = delegated()
        payload = json.loads(base64.urlsafe_b64decode(token.split(".")[1] + "=="))
        del payload["aud"]
        with self.assertRaises(exchange.Closed):
            self.assess(jwt(payload))

    def test_wider_scope_is_closed(self):
        with self.assertRaises(exchange.Closed) as caught:
            self.assess(delegated(scope="submission:read submission:mark-ready"))
        self.assertIn("wider", caught.exception.reason)

    def test_mismatched_actor_is_closed(self):
        with self.assertRaises(exchange.Closed):
            self.assess(delegated(act={"sub": "other-agent"}))

    def test_mismatched_subject_is_closed(self):
        with self.assertRaises(exchange.Closed):
            self.assess(delegated(), expected_sub="someone-else")

    def test_missing_subject_token_is_not_a_form(self):
        with self.assertRaises(exchange.Closed):
            exchange.form("", "actor-token", "http://resource")

    def test_form_asks_for_the_read_scope_and_the_resource(self):
        body = exchange.form("subject-token", "actor-token", "http://apim-gateway:8082/specialty-underwriting/mcp")
        self.assertEqual(body["scope"], "submission:read")
        self.assertEqual(body["resource"], "http://apim-gateway:8082/specialty-underwriting/mcp")
        self.assertNotEqual(body["subject_token"], body["actor_token"])


if __name__ == "__main__":
    unittest.main()
