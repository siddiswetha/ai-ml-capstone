"""Integration test: starts all three services and submits a ticket."""
import json
import os
import sys
import tempfile
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from helpers import start_services, stop_services  # noqa: E402


def post(url, payload, headers=None):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read()), resp.headers.get("X-Trace-Id")


def get(url):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


class TestIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.procs, ok = start_services(cls.tmp.name)
        assert ok, "services did not start"

    @classmethod
    def tearDownClass(cls):
        stop_services(cls.procs)
        cls.tmp.cleanup()

    def test_all_health_checks(self):
        for port in ("8001", "8002", "8003"):
            self.assertEqual(get(f"http://127.0.0.1:{port}/health")["status"], "ok")

    def test_ticket_end_to_end(self):
        result, trace_id = post(
            "http://127.0.0.1:8001/ticket",
            {"text": "I was charged twice for my headphones this month",
             "request_id": "int-billing-1"})
        self.assertEqual(result["category"], "billing")
        self.assertEqual(result["priority"], "high")
        self.assertIn("Billing", result["draft"])
        self.assertTrue(result["sources"])
        self.assertFalse(result["duplicate"])
        self.assertTrue(trace_id)

    def test_duplicate_request_id_returns_stored_ticket(self):
        first, _ = post("http://127.0.0.1:8001/ticket",
                        {"text": "My blender arrived broken",
                         "request_id": "int-dup-1"})
        second, _ = post("http://127.0.0.1:8001/ticket",
                         {"text": "My blender arrived broken",
                          "request_id": "int-dup-1"})
        self.assertTrue(second["duplicate"])
        self.assertEqual(first["ticket_id"], second["ticket_id"])

    def test_out_of_scope_ticket_gets_no_invented_answer(self):
        result, _ = post("http://127.0.0.1:8001/ticket",
                         {"text": "What is the capital of France?",
                          "request_id": "int-oos-1"})
        self.assertEqual(result["sources"], [])
        self.assertIn("could not find", result["draft"])

    def test_metrics_endpoints(self):
        for port in ("8001", "8002", "8003"):
            metrics = get(f"http://127.0.0.1:{port}/metrics")
            self.assertGreaterEqual(metrics["requests"], 1)

    def test_answer_runs_are_listed(self):
        post("http://127.0.0.1:8001/ticket",
             {"text": "My package has not arrived yet",
              "request_id": "int-runs-1"})
        runs = get("http://127.0.0.1:8003/runs")
        self.assertTrue(len(runs["runs"]) >= 1)


if __name__ == "__main__":
    unittest.main()
