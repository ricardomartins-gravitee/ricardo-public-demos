"""The concierge keeps the guest's bearer and does not read any other header."""

import unittest

import forward_subject_token as forward


class SubjectToken(unittest.TestCase):
    def test_a_bearer_is_the_token(self):
        self.assertEqual(forward.subject_token("Bearer guest-token"), "guest-token")

    def test_the_scheme_is_case_insensitive(self):
        self.assertEqual(forward.subject_token("bearer guest-token"), "guest-token")

    def test_a_missing_or_other_header_is_none(self):
        self.assertIsNone(forward.subject_token(None))
        self.assertIsNone(forward.subject_token(""))
        self.assertIsNone(forward.subject_token("Basic guest-token"))
        self.assertIsNone(forward.subject_token("Bearer "))


if __name__ == "__main__":
    unittest.main()
