"""Train the ticket classifier on the synthetic training set.

Usage: python3 ml/train.py
Writes ml/model.json (plain JSON, inspectable by hand).
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "services", "prediction-service"))
from classifier import TicketClassifier  # noqa: E402


def load(path):
    texts, categories, priorities = [], [], []
    with open(path, newline="") as f:
        for row in csv.DictReader(f):
            texts.append(row["text"])
            categories.append(row["category"])
            priorities.append(row["priority"])
    return texts, categories, priorities


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    texts, categories, priorities = load(os.path.join(base, "data", "tickets_train.csv"))
    clf = TicketClassifier()
    clf.train(texts, categories, priorities)
    out = os.path.join(base, "ml", "model.json")
    clf.save(out)
    print(f"trained on {len(texts)} tickets")
    print(f"categories: {sorted(set(categories))}")
    print(f"priorities: {sorted(set(priorities))}")
    print(f"model written to {out}")


if __name__ == "__main__":
    main()
