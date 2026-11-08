"""Answer / RAG service — port 8003.

POST /answer {"text", "category", "priority"} -> retrieved knowledge-base
sources + a drafted reply (mock LLM by default, only from retrieved
sources). GET /runs, GET /health, GET /metrics. Own SQLite table: runs.
Feature flag: response_style (short/detailed) read from flags.json per
request. Structured JSON logging, trace ids. Standard library only.
"""
import json
import os
import sqlite3
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from llm import get_client  # noqa: E402
from rag import load_kb, retrieve  # noqa: E402

PORT = int(os.environ.get("PORT", "8003"))
BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(BASE, "..", "..")
DB = os.environ.get("ANSWER_DB", os.path.join(BASE, "runs.db"))
KB_DIR = os.environ.get("KB_DIR") or (
    os.path.join(ROOT, "docs", "kb")
    if os.path.isdir(os.path.join(ROOT, "docs", "kb"))
    else os.path.join(BASE, "kb"))
FLAGS = os.environ.get("FLAGS_PATH", os.path.join(ROOT, "flags.json"))

START = time.time()
METRICS = {"requests": 0, "errors": 0}
ARTICLES = load_kb(KB_DIR)


def log(service, trace_id, method, path, status, latency_ms):
    print(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "service": service, "trace_id": trace_id,
                      "method": method, "path": path, "status": status,
                      "latency_ms": round(latency_ms, 2)}), flush=True)


def read_flags():
    try:
        with open(FLAGS) as f:
            data = json.load(f)
        style = data.get("response_style", "short")
        canary = data.get("canary", {})
        if canary.get("enabled"):
            return style, canary
        return style, {"enabled": False}
    except Exception:  # noqa: BLE001 - flags are optional; fall back to short
        return "short", {"enabled": False}


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY, trace_id TEXT, request_id TEXT,
        text TEXT, category TEXT, priority TEXT, draft TEXT,
        sources TEXT, style TEXT, created_at REAL)""")
    conn.commit()
    conn.close()


class Handler(BaseHTTPRequestHandler):
    def _send(self, status, payload, trace_id):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Trace-Id", trace_id)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _trace(self):
        return self.headers.get("X-Trace-Id") or str(uuid.uuid4())

    def do_GET(self):
        started = time.time()
        trace_id = self._trace()
        METRICS["requests"] += 1
        if self.path == "/health":
            payload, status = {"status": "ok", "service": "answer"}, 200
        elif self.path == "/metrics":
            payload = {"service": "answer", "requests": METRICS["requests"],
                       "errors": METRICS["errors"],
                       "uptime_seconds": round(time.time() - START, 1)}
            status = 200
        elif self.path == "/runs":
            conn = sqlite3.connect(DB)
            rows = conn.execute(
                "SELECT run_id, trace_id, text, category, priority, draft,"
                " sources, style FROM runs ORDER BY created_at DESC LIMIT 50"
            ).fetchall()
            conn.close()
            payload = {"runs": [
                {"run_id": r[0], "trace_id": r[1], "text": r[2],
                 "category": r[3], "priority": r[4], "draft": r[5],
                 "sources": json.loads(r[6]), "style": r[7]} for r in rows]}
            status = 200
        else:
            payload, status = {"error": "not found"}, 404
            METRICS["errors"] += 1
        log("answer", trace_id, "GET", self.path, status,
            (time.time() - started) * 1000)
        self._send(status, payload, trace_id)

    def do_POST(self):
        started = time.time()
        trace_id = self._trace()
        METRICS["requests"] += 1
        if self.path != "/answer":
            METRICS["errors"] += 1
            log("answer", trace_id, "POST", self.path, 404,
                (time.time() - started) * 1000)
            return self._send(404, {"error": "not found"}, trace_id)
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            text = (data.get("text") or "").strip()
            if not text:
                raise ValueError("text is required")
            request_id = data.get("request_id") or self.headers.get("Idempotency-Key")
            # Idempotence: a repeated request_id returns the stored draft.
            if request_id:
                conn = sqlite3.connect(DB)
                row = conn.execute(
                    "SELECT run_id, draft, sources, style FROM runs"
                    " WHERE request_id = ?", (request_id,)).fetchone()
                conn.close()
                if row:
                    payload = {"run_id": row[0], "trace_id": trace_id,
                               "draft": row[1], "sources": json.loads(row[2]),
                               "style": row[3], "duplicate": True}
                    log("answer", trace_id, "POST", self.path, 200,
                        (time.time() - started) * 1000)
                    return self._send(200, payload, trace_id)
            style, canary = read_flags()
            if canary.get("enabled"):
                # Hash-bucket the trace id: only the canary share gets the new style.
                bucket = int(uuid.uuid5(uuid.NAMESPACE_DNS, trace_id).int % 100)
                if bucket < int(canary.get("percent", 10)):
                    style = canary.get("new_style", "detailed")
            sources = retrieve(text, ARTICLES, top_k=2)
            client = get_client()
            draft = client.draft(text, data.get("category", "general"),
                                 data.get("priority", "medium"), sources, style)
            run_id = str(uuid.uuid4())
            conn = sqlite3.connect(DB)
            conn.execute(
                "INSERT INTO runs (run_id, trace_id, request_id, text,"
                " category, priority, draft, sources, style, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (run_id, trace_id, request_id, text, data.get("category"),
                 data.get("priority"), draft, json.dumps(sources), style,
                 time.time()))
            conn.commit()
            conn.close()
            payload = {"run_id": run_id, "trace_id": trace_id, "draft": draft,
                       "sources": sources, "style": style, "duplicate": False}
            status = 200
        except Exception as exc:  # noqa: BLE001 - return a clean 400, never crash
            METRICS["errors"] += 1
            payload, status = {"error": str(exc), "trace_id": trace_id}, 400
        log("answer", trace_id, "POST", self.path, status,
            (time.time() - started) * 1000)
        self._send(status, payload, trace_id)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    init_db()
    print(f"answer service on port {PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
