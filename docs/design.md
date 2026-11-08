# Support Ticket Intelligence — Technical Design

## Problem

A support team gets written tickets all day. Each ticket needs three things:
a category (what it is about), a priority (how urgent it is), and a reply
that actually answers it from the team's own help articles. Doing that by
hand is slow, and replies that guess at answers are worse than no reply.

This project is a small, complete version of that system. It takes a ticket,
predicts its category and priority with a machine-learning model, finds the
relevant help articles with retrieval, and drafts a reply using only those
articles. Everything runs locally, on synthetic data, with no paid service
and no real customer data.

## Architecture

Three Python services talk to each other over HTTP. Each one owns its own
SQLite table, its own health check, its own metrics, and its own Dockerfile.
No service shares a database with another service.

| Service | Port | Job | Own table |
| --- | --- | --- | --- |
| Intake / gateway | 8001 | Receives a ticket, creates a trace id, calls prediction then answer, stores the ticket | `tickets` |
| Prediction | 8002 | Predicts category and priority from the trained model | `predictions` |
| Answer / RAG | 8003 | Retrieves help articles, drafts a reply, logs the run | `runs` |

Request flow:

1. A client sends `POST /ticket {"text": "...", "request_id": "..."}` to intake.
2. Intake creates a `trace_id` (one id for the whole request) and passes it
   in the `X-Trace-Id` header to both downstream services.
3. Prediction loads `ml/model.json` and returns category, priority and
   confidence scores.
4. Answer retrieves the top 2 help articles, drafts a reply with the mock
   language-model client, and stores the run.
5. Intake stores the ticket and returns category, priority, draft, sources,
   run id and trace id.

## Data model

- `tickets(ticket_id, trace_id, request_id, text, category, priority, draft, sources, run_id, created_at)` — intake.
- `predictions(id, trace_id, text, category, priority, category_confidence, priority_confidence, created_at)` — prediction.
- `runs(run_id, trace_id, request_id, text, category, priority, draft, sources, style, created_at)` — answer.

SQLite was chosen because it needs no server, each service gets one file,
and the data is small. A production version would use a managed relational
database, one schema per service, with the same table shapes.

## Machine learning

- Model: two Naive Bayes classifiers (one for category, one for priority),
  written from scratch in the Python standard library. No external ML
  library is used. Tokens are lower-cased words with a small stopword list;
  Laplace smoothing handles unseen words.
- Training data: 90 synthetic tickets in `data/tickets_train.csv`, six
  categories (billing, access, delivery, defect, refund, account) and three
  priorities (high, medium, low). The data generator is `ml/generate_data.py`
  and is deterministic.
- Model file: `ml/model.json` — plain JSON (vocab, token counts, label
  counts), so anyone can read what the model learned.
- Evaluation: `ml/evaluate.py` scores the model on 30 held-out synthetic
  tickets in `data/tickets_test.csv` and writes `evals/ml-eval-results.json`.
  Real results on this build: **category accuracy 1.0, priority accuracy
  0.9667** (29/30). The one priority miss is recorded in the results file.
  These numbers are computed by the eval script, not typed in by hand.

## Retrieval (RAG) and the language-model interface

- Knowledge base: six invented help articles in `docs/kb/`, one per
  category, written for this project.
- Retrieval (`services/answer-service/rag.py`): keyword overlap with light
  stemming, so "returned" matches "return" and "cracked" matches "crack".
  Returns the top 2 articles with a score and a snippet.
- Language model (`services/answer-service/llm.py`): a pluggable interface.
  `MockLLMClient` is the default — it drafts a reply from the retrieved
  snippets only, in a fixed template, and refuses to draft when no source
  was found ("I could not find a knowledge-base article..."). `RealLLMClient`
  is a stub that raises an error until a model is configured; it never calls
  any external API and no API key is stored in this project.
- RAG eval: `evals/rag-eval.py` runs 12 cases against the retriever and the
  mock client, including one out-of-scope question that must get no invented
  answer. Real result on this build: **12/12 passed**. Results are in
  `evals/rag-eval-results.csv`.

## Observability

- Structured JSON log lines on every request: time, service, trace_id,
  method, path, status, latency in milliseconds.
- `GET /metrics` on each service: request count, error count, uptime.
- Distributed tracing: intake creates a `trace_id` per ticket, passes it in
  the `X-Trace-Id` header and in the request body, and every service stores
  it in its own database row and log lines.

## Idempotence and fault tolerance

- A client sends a `request_id` (or an `Idempotency-Key` header). Intake and
  answer both store it. A repeat with the same id returns the stored ticket
  or draft with `"duplicate": true` and does not call downstream services
  again. This was verified live: the duplicate returned the same ticket id.
- If a downstream service is down, intake returns HTTP 502 with the trace
  id and never invents an answer.
- Each service validates its input and returns a clean HTTP 400 for a
  missing or empty ticket text instead of crashing.

## Safe deployment

- Feature flags in `flags.json`: `response_style` (`short` / `detailed`),
  read per request by the answer service, so the reply style can change
  without a redeploy. An environment variable does not override it; the
  file is the single source of truth.
- Canary: `scripts/canary.py` turns the canary on for a share of trace ids
  (hash-bucketed), sends probe tickets, checks the error rate, then promotes
  the new style or rolls back. Verified live: 4 probes, 0 failures,
  promoted, then reset to the default (`short`, canary off).
- CI: `.github/workflows/ci.yml` runs `py_compile`, the 34 unit and
  integration tests, the ML eval and the RAG eval on every push. No secrets
  are used.

## Testing

- 34 tests (`python3 -m unittest discover -s tests`): unit tests for the
  classifier, retrieval, the language-model interface and flag/canary
  logic, plus an integration test that starts all three services and
  submits tickets, including a duplicate request and an out-of-scope
  question. All 34 pass on this build.
- The CLI (`cli.py`) covers the same flows by hand: `ticket`, `predict`,
  `health`, `metrics`, `runs`.

## Trade-offs and limits

- Naive Bayes is simple and explainable, which fits 90 training tickets.
  With more, messier real data, a stronger model and proper text features
  would be needed, and the eval would show it.
- Keyword retrieval is simple and explainable. It works well on a small,
  well-worded knowledge base; a larger base would need embeddings and a
  vector store.
- The mock language-model client drafts from templates, not from a real
  model. That is deliberate: it proves the guardrail (never invent an
  answer) without a paid API. Swapping in a real client means implementing
  `RealLLMClient.draft` and keeping the same guardrail.
- Docker and Kubernetes files were written and YAML-validated only. Docker
  was not run on this machine, so the container path is untested at
  runtime. The non-Docker path (`python3 run_local.py`) was run and
  verified live.
- Concurrency: each service uses `ThreadingHTTPServer`, so requests run in
  parallel. SQLite writes are short and single-row, which keeps contention
  low at this scale; a production service would use a connection pool and a
  database that handles concurrent writers.

## Data governance

All data in this project is synthetic and invented: ticket texts, help
articles, product names. No real customer data, no personal data, no
company data of any kind is used or stored. The mock language-model client
sends nothing anywhere.
