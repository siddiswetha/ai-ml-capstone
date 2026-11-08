"""RAG eval: 12 cases. Pass bar is 12/12.

For each case, retrieval must return the expected knowledge-base article
(or no article at all for the out-of-scope case R12), and the drafted
reply must not invent an answer when no source was retrieved.
Writes evals/rag-eval-results.csv. Results are computed here.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..",
                                "services", "answer-service"))
from llm import MockLLMClient  # noqa: E402
from rag import load_kb, retrieve  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    articles = load_kb(os.path.join(BASE, "docs", "kb"))
    client = MockLLMClient()
    rows_out = []
    passed = 0
    with open(os.path.join(BASE, "evals", "rag-eval-set.csv"), newline="") as f:
        for row in csv.DictReader(f):
            sources = retrieve(row["text"], articles, top_k=2)
            files = [s["file"] for s in sources]
            draft = client.draft(row["text"], "general", "medium", sources, "short")
            if row["expected_source"] == "NONE":
                ok = not sources and "could not find" in draft
            else:
                ok = row["expected_source"] in files and draft and "could not find" not in draft
            passed += 1 if ok else 0
            rows_out.append({"id": row["id"], "text": row["text"],
                             "expected_source": row["expected_source"],
                             "retrieved": ";".join(files),
                             "passed": "yes" if ok else "no"})
    out = os.path.join(BASE, "evals", "rag-eval-results.csv")
    with open(out, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "text", "expected_source",
                                               "retrieved", "passed"])
        writer.writeheader()
        writer.writerows(rows_out)
    print(f"RAG eval: {passed}/{len(rows_out)} passed (pass bar: 12/12)")
    print(f"results written to {out}")
    if passed != len(rows_out):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
