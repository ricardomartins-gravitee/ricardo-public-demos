import json
import unittest
from pathlib import Path

from starlette.testclient import TestClient

from catalog import get_service
from server import OPENAPI_DOCUMENT, app

EXPECTED_IDS = [
    "service-001",
    "service-002",
    "service-003",
    "service-004",
]

OPENAPI_PATH_KEYS = {
    "/v1/health",
    "/v1/services",
    "/v1/services/{id}",
    "/v2/health",
    "/v2/services",
    "/v2/services/{id}",
    "/v1/notices",
    "/v1/notices/{id}",
}


class SharedServicesApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(app)

    def test_health_root(self):
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_health_v1(self):
        response = self.client.get("/v1/health")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_list_services(self):
        response = self.client.get("/v1/services")
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["count"], 4)
        ids = [service["id"] for service in body["services"]]
        self.assertEqual(ids, EXPECTED_IDS)

    def test_get_service_001(self):
        expected = get_service("service-001")
        response = self.client.get("/v1/services/service-001")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), expected)
        self.assertEqual(response.json()["name"], "Reporting Service")
        self.assertEqual(response.json()["status"], "operational")

    def test_get_unknown_service(self):
        response = self.client.get("/v1/services/does-not-exist")
        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["error"], "not_found")
        self.assertEqual(body["message"], "No service has the id does-not-exist.")

    def test_openapi_paths(self):
        self.assertEqual(set(OPENAPI_DOCUMENT["paths"].keys()), OPENAPI_PATH_KEYS)
        on_disk = json.loads(
            (Path(__file__).resolve().parent.parent / "openapi.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(set(on_disk["paths"].keys()), OPENAPI_PATH_KEYS)

    def test_openapi_example_matches_live_service_001(self):
        example = OPENAPI_DOCUMENT["paths"]["/v1/services/{id}"]["get"]["responses"][
            "200"
        ]["content"]["application/json"]["example"]
        live = get_service("service-001")
        self.assertEqual(example, live)

    def test_shared_services_prefix_list(self):
        direct = self.client.get("/v1/services").json()
        prefixed = self.client.get("/shared-services/v1/services").json()
        self.assertEqual(prefixed, direct)

    def test_version_2_adds_channel_and_version_1_omits_it(self):
        current = self.client.get("/v1/services/service-001").json()
        nxt = self.client.get("/v2/services/service-001").json()
        self.assertNotIn("channel", current)
        self.assertEqual(nxt["channel"], "reports")
        self.assertEqual(nxt["id"], "service-001")
        listed = self.client.get("/shared-services-v2/v2/services").json()
        self.assertEqual(listed["services"][0]["channel"], "reports")

    def test_notices(self):
        listed = self.client.get("/v1/notices").json()
        self.assertEqual(listed["count"], 2)
        self.assertEqual(listed["notices"][0]["id"], "notice-001")
        one = self.client.get("/platform-notices/v1/notices/notice-001")
        self.assertEqual(one.status_code, 200)
        self.assertEqual(one.json()["service"], "service-003")
        missing = self.client.get("/v1/notices/missing")
        self.assertEqual(missing.status_code, 404)

    def test_openapi_json_route(self):
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["info"]["title"], "Shared Services API")


if __name__ == "__main__":
    unittest.main()
