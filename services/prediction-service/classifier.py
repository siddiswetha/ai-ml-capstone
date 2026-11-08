"""A small Naive Bayes text classifier, written from scratch.

No external ML library is used. Tokens are lower-cased words, Laplace
smoothing is applied, and the trained model is plain JSON so it can be
inspected by hand. Two labels are learned: ticket category and priority.
"""
import json
import math
import re

STOPWORDS = {
    "i", "my", "me", "the", "a", "an", "and", "or", "to", "for", "of", "in",
    "on", "is", "was", "it", "please", "hello", "thank", "you", "can", "would",
    "like", "after", "with", "at", "but", "not", "yet", "has", "have",
}

TOKEN_RE = re.compile(r"[a-z0-9]+")


def tokenize(text):
    return [t for t in TOKEN_RE.findall(text.lower()) if t not in STOPWORDS]


class NaiveBayes:
    def __init__(self):
        self.labels = []
        self.label_counts = {}
        self.token_counts = {}
        self.vocab = set()
        self.total = 0

    def train(self, texts, labels):
        for text, label in zip(texts, labels):
            self.total += 1
            self.label_counts[label] = self.label_counts.get(label, 0) + 1
            if label not in self.token_counts:
                self.token_counts[label] = {}
                self.labels.append(label)
            for token in tokenize(text):
                self.vocab.add(token)
                counts = self.token_counts[label]
                counts[token] = counts.get(token, 0) + 1

    def predict(self, text):
        tokens = tokenize(text)
        vocab_size = len(self.vocab)
        best_label, best_score = None, None
        scores = {}
        for label in self.labels:
            label_total = sum(self.token_counts[label].values())
            score = math.log(self.label_counts[label] / self.total)
            for token in tokens:
                count = self.token_counts[label].get(token, 0)
                score += math.log((count + 1) / (label_total + vocab_size))
            scores[label] = score
            if best_score is None or score > best_score:
                best_label, best_score = label, score
        # Confidence: softmax over the label scores.
        top = max(scores.values())
        weights = {k: math.exp(v - top) for k, v in scores.items()}
        total_w = sum(weights.values())
        return best_label, weights[best_label] / total_w, scores

    def to_dict(self):
        return {
            "labels": self.labels,
            "label_counts": self.label_counts,
            "token_counts": self.token_counts,
            "vocab": sorted(self.vocab),
            "total": self.total,
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        obj.labels = data["labels"]
        obj.label_counts = data["label_counts"]
        obj.token_counts = data["token_counts"]
        obj.vocab = set(data["vocab"])
        obj.total = data["total"]
        return obj


class TicketClassifier:
    """Predicts both category and priority for a ticket."""

    def __init__(self):
        self.category_model = NaiveBayes()
        self.priority_model = NaiveBayes()

    def train(self, texts, categories, priorities):
        self.category_model.train(texts, categories)
        self.priority_model.train(texts, priorities)

    def predict(self, text):
        category, cat_conf, _ = self.category_model.predict(text)
        priority, pri_conf, _ = self.priority_model.predict(text)
        return {
            "category": category,
            "category_confidence": round(cat_conf, 4),
            "priority": priority,
            "priority_confidence": round(pri_conf, 4),
        }

    def to_dict(self):
        return {
            "category": self.category_model.to_dict(),
            "priority": self.priority_model.to_dict(),
        }

    @classmethod
    def from_dict(cls, data):
        obj = cls()
        obj.category_model = NaiveBayes.from_dict(data["category"])
        obj.priority_model = NaiveBayes.from_dict(data["priority"])
        return obj

    def save(self, path):
        with open(path, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path):
        with open(path) as f:
            return cls.from_dict(json.load(f))
