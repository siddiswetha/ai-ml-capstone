"""Evaluate the trained classifier on the held-out synthetic test set.

Usage: python3 ml/evaluate.py
Writes evals/ml-eval-results.json. Prints real accuracy, precision,
recall and F1 — the numbers are computed here, never typed in by hand.
"""
import csv
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "services", "prediction-service"))
from classifier import TicketClassifier  # noqa: E402


def load(path):
    rows = []
    with open(path, newline="") as f:
        rows.extend(csv.DictReader(f))
    return rows


def prf(rows, predicted, actual, labels):
    out = {}
    for label in labels:
        tp = sum(1 for p, a in zip(predicted, actual) if p == label and a == label)
        fp = sum(1 for p, a in zip(predicted, actual) if p == label and a != label)
        fn = sum(1 for p, a in zip(predicted, actual) if p != label and a == label)
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        out[label] = {"precision": round(precision, 4), "recall": round(recall, 4),
                      "f1": round(f1, 4), "support": sum(1 for a in actual if a == label)}
    return out


def main():
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    clf = TicketClassifier.load(os.path.join(base, "ml", "model.json"))
    rows = load(os.path.join(base, "data", "tickets_test.csv"))
    cat_pred, cat_true, pri_pred, pri_true = [], [], [], []
    errors = []
    for row in rows:
        result = clf.predict(row["text"])
        cat_pred.append(result["category"])
        cat_true.append(row["category"])
        pri_pred.append(result["priority"])
        pri_true.append(row["priority"])
        if result["category"] != row["category"] or result["priority"] != row["priority"]:
            errors.append({"text": row["text"], "true_category": row["category"],
                           "predicted_category": result["category"],
                           "true_priority": row["priority"],
                           "predicted_priority": result["priority"]})
    cat_acc = sum(p == a for p, a in zip(cat_pred, cat_true)) / len(rows)
    pri_acc = sum(p == a for p, a in zip(pri_pred, pri_true)) / len(rows)
    results = {
        "test_size": len(rows),
        "category_accuracy": round(cat_acc, 4),
        "priority_accuracy": round(pri_acc, 4),
        "category_per_label": prf(rows, cat_pred, cat_true, sorted(set(cat_true))),
        "priority_per_label": prf(rows, pri_pred, pri_true, sorted(set(pri_true))),
        "errors": errors,
    }
    out = os.path.join(base, "evals", "ml-eval-results.json")
    with open(out, "w") as f:
        json.dump(results, f, indent=2)
    print(f"test size: {len(rows)}")
    print(f"category accuracy: {results['category_accuracy']}")
    print(f"priority accuracy: {results['priority_accuracy']}")
    print(f"results written to {out}")


if __name__ == "__main__":
    main()
