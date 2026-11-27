import unittest

import store


class StoreTest(unittest.TestCase):
    def setUp(self):
        store.reset()

    def test_reset_is_idempotent(self):
        first = store.reset()
        second = store.reset()
        self.assertEqual(first, second)
        self.assertEqual(second["status"], "IN_REVIEW")
        self.assertEqual(second["write_handler_calls"], 0)
        self.assertEqual(second["line_of_business"], "CYBER")

    def test_read_does_not_enter_the_write_handler(self):
        store.read_context("CYB-001")
        self.assertEqual(store.observation()["write_handler_calls"], 0)

    def test_mark_ready_changes_status_once(self):
        updated = store.mark_ready("CYB-001")
        self.assertEqual(updated["status"], "READY_FOR_QUOTE")
        self.assertEqual(updated["write_handler_calls"], 1)
        again = store.mark_ready("CYB-001")
        self.assertEqual(again["status"], "READY_FOR_QUOTE")
        self.assertEqual(again["write_handler_calls"], 2)

    def test_unknown_submission_does_not_count_a_write(self):
        self.assertIsNone(store.mark_ready("CYB-999"))
        self.assertEqual(store.observation()["write_handler_calls"], 0)


if __name__ == "__main__":
    unittest.main()
