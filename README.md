# Support Ticket Intelligence

An end-to-end AI/ML capstone: a support-ticket triage system that predicts
a ticket's category and priority with a machine-learning model, retrieves
the relevant help articles, and drafts a reply using only those articles.

Three Python microservices work together over HTTP:

| Service | Port | Job |
| --- | --- | --- |
| Intake / gateway | 8001 | Receives a ticket, creates a trace id, calls prediction then answer |
| Prediction | 8002 | ML model predicts category and priority |
| Answer / RAG | 8003 | Retrieves help articles, drafts a reply, logs the run |

Each service has its own SQLite table, health check, metrics endpoint,
structured JSON logging, and Dockerfile. Everything is Python standard
library only — no paid API, no external packages, no real customer data.
All tickets, help articles, and product names are synthetic and invented.

## Results (all computed by the scripts, not typed in by hand)

- **Tests: 34/34 passed** — `python3 -m unittest discover -s tests`
- **ML eval (30 held-out tickets): category accuracy 1.0, priority
  accuracy 0.9667** — `python3 ml/evaluate.py`, results in
  `evals/ml-eval-results.json`
- **RAG eval: 12/12 passed** — `python3 evals/rag-eval.py`, results in
  `evals/rag-eval-results.csv`
- **Canary verified live:** 4 probe tickets, 0 failures, promoted, then
  reset to the default (`short`, canary off)

## Quick start (no Docker)

```bash
python3 ml/train.py        # train the classifier, writes ml/model.json
python3 run_local.py       # start all three services (8001, 8002, 8003)
```

Then, in another terminal:

```bash
python3 cli.py ticket "I was charged twice for my headphones this month"
python3 cli.py predict "My package has not arrived yet"
python3 cli.py health
python3 cli.py metrics
python3 cli.py runs
```

Example reply to a billing ticket:

```json
{
  "ticket_id": "603d6fce-...",
  "category": "billing",
  "priority": "high",
  "category_confidence": 0.9906,
  "draft": "Hello, thank you for writing about your billing issue (priority: high). Based on \"Billing: duplicate or wrong charge\": If you were charged twice or the wrong amount, check your order page first. Please follow those steps and let us know if it helps.",
  "sources": [{"file": "billing-charge.md", "title": "Billing: duplicate or wrong charge", "score": 3}]
}
```

## Docker

```bash
docker compose up --build
```

Docker and Kubernetes files were written and YAML-validated only. Docker
was not run on this machine, so the container path is untested at runtime.
The non-Docker path above was run and verified live.

Kubernetes manifests are in `k8s/` (one Deployment and one ClusterIP
Service per service, with liveness and readiness probes on `/health`).
They were YAML-validated only and have not been applied to a cluster.

## How it works

### Machine learning

Two Naive Bayes classifiers, written from scratch in the standard library
(`services/prediction-service/classifier.py`), one for category and one
for priority. Training data is 90 synthetic tickets
(`data/tickets_train.csv`, generated deterministically by
`ml/generate_data.py`) across six categories — billing, access, delivery,
defect, refund, account — and three priorities. The trained model is
`ml/model.json`, plain JSON that can be read by hand.

### Retrieval (RAG) and the language-model interface

Six invented help articles live in `docs/kb/`, one per category.
Retrieval scores articles by keyword overlap with light stemming, so
"returned" matches "return". The language-model interface
(`services/answer-service/llm.py`) is pluggable: `MockLLMClient` is the
default and drafts only from retrieved snippets; `RealLLMClient` is a stub
that refuses to run until a model is configured, so nothing is ever sent
to an external model by accident. If no article is retrieved, the draft
says so plainly and no answer is invented. Prompt templates and
guardrails are in `docs/prompts.md`.

### Observability, idempotence, fault tolerance

- Every request logs a structured JSON line (time, service, trace id,
  method, path, status, latency).
- `GET /metrics` on each service reports request count, error count,
  and uptime.
- Intake creates a `trace_id` per ticket and passes it in the
  `X-Trace-Id` header to both downstream services; it is stored in every
  service's database row.
- Send a `request_id` (or an `Idempotency-Key` header) and a repeat
  returns the stored ticket with `"duplicate": true` instead of calling
  downstream services again.
- If a downstream service is down, intake returns HTTP 502 with the
  trace id and never invents an answer.

### Safe deployment

- Feature flags in `flags.json`: `response_style` (`short` / `detailed`),
  read per request by the answer service.
- Canary: `scripts/canary.py` turns the canary on for a share of trace
  ids, sends probe tickets, checks the error rate, then promotes the new
  style or rolls back. Run it while the services are up:
  `python3 scripts/canary.py --percent 10 --probes 10`
- CI: `.github/workflows/ci.yml` runs compile, the 34 tests, the ML eval
  and the RAG eval on every push. No secrets are used.

## Project layout

```text
services/
  intake-service/main.py       # gateway, port 8001
  prediction-service/main.py   # ML prediction, port 8002
  prediction-service/classifier.py
  answer-service/main.py       # RAG + drafting, port 8003
  answer-service/rag.py
  answer-service/llm.py
ml/
  generate_data.py  train.py  evaluate.py  model.json
data/                          # synthetic tickets (train 90, test 30)
docs/
  design.md  prompts.md
  kb/                          # 6 invented help articles
evals/
  rag-eval-set.csv  rag-eval.py  rag-eval-results.csv
  ml-eval-results.json
tests/                         # 34 unit + integration tests
scripts/canary.py
k8s/                           # Deployment + Service per service
.github/workflows/ci.yml
cli.py  run_local.py  flags.json  docker-compose.yml
```

## Design

See `docs/design.md` for the full technical design: architecture, data
model, ML and RAG choices, observability, idempotence, safe deployment,
testing, trade-offs, and data governance. All data in this project is
synthetic and invented; no real customer data, personal data, or company
data of any kind is used or stored.
