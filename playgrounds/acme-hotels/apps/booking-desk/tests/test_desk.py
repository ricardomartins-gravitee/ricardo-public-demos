"""The booking desk's MCP answers and the text it reads from an A2A reply."""

import json
import unittest

import desk


class Answers(unittest.TestCase):
    def test_a_message_reply_is_its_text(self):
        self.assertEqual(desk.answer_text({"result": {"parts": [{"text": "Two hotels in Paris."}]}}),
                         "Two hotels in Paris.")

    def test_a_task_reply_is_the_status_message(self):
        payload = {"result": {"status": {"message": {"parts": [{"text": "The desk is closed."}]}}}}
        self.assertEqual(desk.answer_text(payload), "The desk is closed.")

    def test_a_reply_with_no_text_is_empty(self):
        self.assertEqual(desk.answer_text({"result": {}}), "")


class Tool(unittest.TestCase):
    def test_initialize_names_the_server_the_catalog_expects(self):
        result = desk.rpc_result({"id": 1, "method": "initialize"}, lambda question, authorization: "")
        self.assertEqual(result["serverInfo"]["name"], "acme-hotels-booking-desk")
        self.assertIn("prompts", result["capabilities"])
        self.assertIn("resources", result["capabilities"])

    def test_the_prompts_and_resources_are_listed(self):
        prompts = desk.rpc_result({"id": 1, "method": "prompts/list"}, lambda question, authorization: "")
        resources = desk.rpc_result({"id": 1, "method": "resources/list"}, lambda question, authorization: "")
        self.assertEqual([prompt["name"] for prompt in prompts["prompts"]], ["search-hotels", "loyalty-offer"])
        self.assertEqual([resource["uri"] for resource in resources["resources"]],
                         ["hotel://stay-policy", "hotel://guest-privacy"])

    def test_a_prompt_fills_the_city_and_a_resource_returns_its_text(self):
        prompt = desk.rpc_result(
            {"id": 1, "method": "prompts/get", "params": {"name": "loyalty-offer", "arguments": {"city": "Paris"}}},
            lambda question, authorization: "")
        resource = desk.rpc_result(
            {"id": 1, "method": "resources/read", "params": {"uri": "hotel://stay-policy"}},
            lambda question, authorization: "")
        self.assertEqual(prompt["messages"][0]["content"]["text"],
                         "Ask the loyalty desk what offer the guest gets for a stay in Paris.")
        self.assertIn("simulated for the demo", resource["contents"][0]["text"])

    def test_an_unknown_prompt_is_an_error(self):
        result = desk.rpc_result(
            {"id": 1, "method": "prompts/get", "params": {"name": "missing"}},
            lambda question, authorization: "")
        self.assertEqual(result["error"]["code"], -32602)

    def test_the_tools_are_the_booking_desk_and_the_loyalty_desk(self):
        result = desk.rpc_result({"id": 1, "method": "tools/list"}, lambda question, authorization: "")
        self.assertEqual([tool["name"] for tool in result["tools"]], ["ask_booking_desk", "ask_loyalty_desk"])

    def test_a_loyalty_question_uses_the_loyalty_handler(self):
        result = desk.rpc_result(
            {"id": 1, "method": "tools/call", "params": {"name": "ask_loyalty_desk", "arguments": {"question": "Paris"}}},
            lambda question, authorization: "booking",
            lambda question, authorization: f"loyalty {question}")
        self.assertEqual(result["content"][0]["text"], "loyalty Paris")

    def test_a_question_is_the_tool_answer(self):
        result = desk.rpc_result(
            {"id": 1, "method": "tools/call", "params": {"name": "ask_booking_desk", "arguments": {"question": "Paris"}}},
            lambda question, authorization: f"found {question}")
        self.assertEqual(result["content"][0]["text"], "found Paris")
        self.assertFalse(result["isError"])

    def test_a_missing_question_is_an_error_result(self):
        result = desk.rpc_result(
            {"id": 1, "method": "tools/call", "params": {"name": "ask_booking_desk", "arguments": {}}},
            lambda question, authorization: "")
        self.assertTrue(result["isError"])

    def test_a_notification_has_no_result(self):
        self.assertIsNone(desk.rpc_result({"method": "notifications/initialized"}, lambda question, authorization: ""))


class Call(unittest.TestCase):
    def test_the_guest_token_goes_to_the_desk_that_answers(self):
        self.assertEqual(desk.authorization_for("ask_booking_desk", "Bearer guest"), "Bearer guest")
        self.assertEqual(desk.authorization_for("ask_loyalty_desk", "Bearer guest"), "Bearer guest")
        self.assertIsNone(desk.authorization_for("searchHotels", "Bearer guest"))

    def test_the_question_is_posted_to_the_gateway_with_the_caller_token(self):
        seen = {}

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"result": {"parts": [{"text": "One hotel."}]}}).encode()

        def opener(request, timeout):
            seen["url"] = request.full_url
            seen["authorization"] = request.get_header("Authorization")
            seen["body"] = json.loads(request.data.decode())
            seen["timeout"] = timeout
            return Response()

        previous = desk.A2A_URL
        desk.A2A_URL = "http://gateway/booking-desk/"
        try:
            text = desk.ask_booking_desk("Hotels in Paris", "Bearer guest", opener)
        finally:
            desk.A2A_URL = previous
        self.assertEqual(text, "One hotel.")
        self.assertEqual(seen["url"], "http://gateway/booking-desk/")
        self.assertEqual(seen["authorization"], "Bearer guest")
        self.assertEqual(seen["body"]["method"], "message/send")
        self.assertEqual(seen["body"]["params"]["message"]["parts"], [{"text": "Hotels in Paris"}])
        self.assertEqual(seen["timeout"], desk.A2A_TIMEOUT)

    def test_a_gateway_error_is_raised(self):
        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps({"error": {"message": "refused"}}).encode()

        previous = desk.A2A_URL
        desk.A2A_URL = "http://gateway/booking-desk/"
        try:
            with self.assertRaisesRegex(RuntimeError, "refused"):
                desk.ask_booking_desk("Paris", None, lambda request, timeout: Response())
        finally:
            desk.A2A_URL = previous

    def test_the_cards_name_both_agents(self):
        self.assertEqual(desk.CONCIERGE_CARD["name"], "ACME Hotels Concierge")
        self.assertEqual(desk.BOOKING_CARD["supportedInterfaces"][0]["url"], "http://localhost:8082/booking-desk/")


if __name__ == "__main__":
    unittest.main()
