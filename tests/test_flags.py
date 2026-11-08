"""Unit tests for feature flags and canary bucketing."""
import hashlib
import json
import os
import unittest


def canary_bucket(trace_id):
    return int(hashlib.sha256(trace_id.encode()).hexdigest(), 16) % 100


def style_for(trace_id, flags):
    style = flags.get("response_style", "short")
    canary = flags.get("canary", {})
    if canary.get("enabled") and canary_bucket(trace_id) < int(canary.get("percent", 10)):
        return canary.get("new_style", "detailed")
    return style


class TestFlags(unittest.TestCase):
    def test_default_flags_file(self):
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(base, "flags.json")) as f:
            flags = json.load(f)
        self.assertEqual(flags["response_style"], "short")
        self.assertFalse(flags["canary"]["enabled"])

    def test_canary_off_returns_default_style(self):
        flags = {"response_style": "short",
                 "canary": {"enabled": False, "new_style": "detailed", "percent": 10}}
        self.assertEqual(style_for("any-trace-id", flags), "short")

    def test_canary_100_percent_returns_new_style(self):
        flags = {"response_style": "short",
                 "canary": {"enabled": True, "new_style": "detailed", "percent": 100}}
        self.assertEqual(style_for("any-trace-id", flags), "detailed")

    def test_canary_0_percent_returns_default_style(self):
        flags = {"response_style": "short",
                 "canary": {"enabled": True, "new_style": "detailed", "percent": 0}}
        self.assertEqual(style_for("any-trace-id", flags), "short")

    def test_bucket_is_stable_for_same_trace_id(self):
        self.assertEqual(canary_bucket("trace-123"), canary_bucket("trace-123"))

    def test_bucket_is_in_range(self):
        for trace_id in ("a", "b", "c", "trace-1", "trace-2"):
            self.assertTrue(0 <= canary_bucket(trace_id) < 100)


if __name__ == "__main__":
    unittest.main()
