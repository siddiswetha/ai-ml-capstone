"""Unit tests for the from-scratch Naive Bayes ticket classifier."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "services", "prediction-service"))
from classifier import NaiveBayes, TicketClassifier, tokenize  # noqa: E402


def train_small():
    clf = TicketClassifier()
    clf.train(
        ["I was charged twice for my headphones", "my card was charged wrong",
         "I cannot log in to my account", "password reset link not working",
         "my package has not arrived", "delivery is late",
         "my blender arrived broken", "product is cracked and faulty",
         "I want a refund for my order", "please return my money",
         "change the email on my account", "update my delivery address"],
        ["billing", "billing", "access", "access", "delivery", "delivery",
         "defect", "defect", "refund", "refund", "account", "account"],
        ["high", "high", "high", "high", "medium", "medium",
         "high", "high", "medium", "medium", "low", "low"])
    return clf


class TestTokenize(unittest.TestCase):
    def test_lowercases_and_drops_stopwords(self):
        self.assertEqual(tokenize("I was Charged Twice, please help"),
                         ["charged", "twice", "help"])

    def test_empty_text_gives_no_tokens(self):
        self.assertEqual(tokenize(""), [])


class TestNaiveBayes(unittest.TestCase):
    def test_predicts_learned_label(self):
        model = NaiveBayes()
        model.train(["charged twice", "charged wrong amount"],
                    ["billing", "billing"])
        label, confidence, _ = model.predict("charged twice again")
        self.assertEqual(label, "billing")
        self.assertGreater(confidence, 0.5)

    def test_save_and_load_round_trip(self):
        clf = train_small()
        path = os.path.join(os.path.dirname(__file__), "..", "ml", "model.json")
        loaded = TicketClassifier.load(path)
        self.assertEqual(loaded.predict("I was charged twice")["category"], "billing")


class TestTicketClassifier(unittest.TestCase):
    def setUp(self):
        self.clf = train_small()

    def test_billing_ticket(self):
        result = self.clf.predict("I was charged twice for my headphones")
        self.assertEqual(result["category"], "billing")
        self.assertEqual(result["priority"], "high")

    def test_access_ticket(self):
        result = self.clf.predict("I cannot log in to my account")
        self.assertEqual(result["category"], "access")

    def test_delivery_ticket(self):
        result = self.clf.predict("my package has not arrived yet")
        self.assertEqual(result["category"], "delivery")

    def test_defect_ticket(self):
        result = self.clf.predict("my blender arrived broken")
        self.assertEqual(result["category"], "defect")

    def test_refund_ticket(self):
        result = self.clf.predict("I want a refund for my order")
        self.assertEqual(result["category"], "refund")

    def test_account_ticket(self):
        result = self.clf.predict("change the email on my account")
        self.assertEqual(result["category"], "account")
        self.assertEqual(result["priority"], "low")

    def test_confidences_are_between_zero_and_one(self):
        result = self.clf.predict("my package has not arrived")
        self.assertTrue(0 <= result["category_confidence"] <= 1)
        self.assertTrue(0 <= result["priority_confidence"] <= 1)


if __name__ == "__main__":
    unittest.main()
