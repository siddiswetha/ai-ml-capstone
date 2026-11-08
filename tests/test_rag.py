"""Unit tests for RAG retrieval and the LLM interface."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "services", "answer-service"))
from llm import MockLLMClient, RealLLMClient  # noqa: E402
from rag import load_kb, retrieve, tokens  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KB = os.path.join(BASE, "docs", "kb")


class TestTokens(unittest.TestCase):
    def test_stemming_matches_word_forms(self):
        self.assertIn("return", tokens("I returned the product"))
        self.assertIn("crack", tokens("the screen is cracked"))

    def test_stopwords_removed(self):
        self.assertNotIn("the", tokens("the package is late"))


class TestRetrieval(unittest.TestCase):
    def setUp(self):
        self.articles = load_kb(KB)

    def test_loads_six_articles(self):
        self.assertEqual(len(self.articles), 6)

    def test_billing_query_finds_billing_article(self):
        results = retrieve("I was charged twice", self.articles)
        self.assertEqual(results[0]["file"], "billing-charge.md")

    def test_delivery_query_finds_delivery_article(self):
        results = retrieve("my package has not arrived, tracking not moved",
                           self.articles)
        self.assertEqual(results[0]["file"], "delivery-late.md")

    def test_unrelated_query_finds_nothing(self):
        self.assertEqual(retrieve("what is the capital of France?",
                                  self.articles), [])

    def test_results_are_ranked(self):
        results = retrieve("refund for the faulty product I returned",
                           self.articles)
        self.assertTrue(len(results) >= 1)
        self.assertIn("refund-return.md", [r["file"] for r in results])


class TestLLM(unittest.TestCase):
    def test_mock_drafts_from_sources_only(self):
        client = MockLLMClient()
        draft = client.draft("charged twice", "billing", "high",
                             [{"title": "Billing: duplicate or wrong charge",
                               "snippet": "check your order page first",
                               "file": "billing-charge.md", "score": 3}], "short")
        self.assertIn("Billing: duplicate or wrong charge", draft)

    def test_mock_refuses_without_sources(self):
        client = MockLLMClient()
        draft = client.draft("what is the capital of France?", "general",
                             "medium", [], "short")
        self.assertIn("could not find", draft)

    def test_detailed_style_is_longer(self):
        client = MockLLMClient()
        sources = [{"title": "Delivery: late or missing package",
                    "snippet": "deliveries usually arrive in three days",
                    "file": "delivery-late.md", "score": 2}]
        short = client.draft("late delivery", "delivery", "medium", sources, "short")
        detailed = client.draft("late delivery", "delivery", "medium", sources, "detailed")
        self.assertGreater(len(detailed), len(short))

    def test_real_client_refuses_when_unconfigured(self):
        with self.assertRaises(RuntimeError):
            RealLLMClient().draft("hello", "general", "medium", [], "short")


if __name__ == "__main__":
    unittest.main()
