"""Ticket intake / gateway service — port 8001.

POST /ticket {"text": "...", "request_id": "..."} -> creates a trace id,
calls the prediction service (port 8002) then the answer service
(port 8003), and returns category, priority, draft reply and sources.
GET /health, GET /metrics. Own SQLite table: tickets.
Idempotence: a repeated request_id returns the stored ticket and does
not call downstream services again. Downstream failure -> HTTP 502
with the trace id; an answer is never invented. Standard library only.
"""
import json
import os
import sqlite3
import time
import urllib.error
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8001"))
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("INTAKE_DB", os.path.join(BASE, "tickets.db"))
PREDICT_URL = os.environ.get("PREDICT_URL", "http://127.0.0.1:8002/predict")
ANSWER_URL = os.environ.get("ANSWER_URL", "http://127.0.0.1:8003/answer")

START = time.time()
METRICS = {"requests": 0, "errors": 0}


def log(service, trace_id, method, path, status, latency_ms):
    print(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "service": service, "trace_id": trace_id,
                      "method": method, "path": path, "status": status,
                      "latency_ms": round(latency_ms, 2)}), flush=True)


def call_service(url, payload, trace_id, timeout=10):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", "X-Trace-Id": trace_id},
        method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS tickets (
        ticket_id TEXT PRIMARY KEY, trace_id TEXT, request_id TEXT,
        text TEXT, category TEXT, priority TEXT, draft TEXT,
        sources TEXT, run_id TEXT, created_at REAL)""")
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
            payload, status = {"status": "ok", "service": "intake"}, 200
        elif self.path == "/metrics":
            payload = {"service": "intake", "requests": METRICS["requests"],
                       "errors": METRICS["errors"],
                       "uptime_seconds": round(time.time() - START, 1)}
            status = 200
        else:
            payload, status = {"error": "not found"}, 404
            METRICS["errors"] += 1
        log("intake", trace_id, "GET", self.path, status,
            (time.time() - started) * 1000)
        self._send(status, payload, trace_id)

    def do_POST(self):
        started = time.time()
        trace_id = self._trace()
        METRICS["requests"] += 1
        if self.path != "/ticket":
            METRICS["errors"] += 1
            log("intake", trace_id, "POST", self.path, 404,
                (time.time() - started) * 1000)
            return self._send(404, {"error": "not found"}, trace_id)
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            text = (data.get("text") or "").strip()
            if not text:
                raise ValueError("text is required")
            request_id = data.get("request_id") or self.headers.get("Idempotency-Key")
            if request_id:
                conn = sqlite3.connect(DB)
                row = conn.execute(
                    "SELECT ticket_id, category, priority, draft, sources, run_id"
                    " FROM tickets WHERE request_id = ?", (request_id,)).fetchone()
                conn.close()
                if row:
                    payload = {"ticket_id": row[0], "trace_id": trace_id,
                               "category": row[1], "priority": row[2],
                               "draft": row[3], "sources": json.loads(row[4]),
                               "run_id": row[5], "duplicate": True}
                    log("intake", trace_id, "POST", self.path, 200,
                        (time.time() - started) * 1000)
                    return self._send(200, payload, trace_id)
            try:
                prediction = call_service(PREDICT_URL, {"text": text}, trace_id)
                answer = call_service(
                    ANSWER_URL,
                    {"text": text, "category": prediction["category"],
                     "priority": prediction["priority"], "request_id": request_id},
                    trace_id)
            except (urllib.error.URLError, urllib.error.HTTPError) as exc:
                METRICS["errors"] += 1
                payload = {"error": f"downstream service unavailable: {exc}",
                           "trace_id": trace_id}
                log("intake", trace_id, "POST", self.path, 502,
                    (time.time() - started) * 1000)
                return self._send(502, payload, trace_id)
            ticket_id = str(uuid.uuid4())
            conn = sqlite3.connect(DB)
            conn.execute(
                "INSERT INTO tickets (ticket_id, trace_id, request_id, text,"
                " category, priority, draft, sources, run_id, created_at)"
                " VALUES (?,?,?,?,?,?,?,?,?,?)",
                (ticket_id, trace_id, request_id, text,
                 prediction["category"], prediction["priority"],
                 answer["draft"], json.dumps(answer["sources"]),
                 answer["run_id"], time.time()))
            conn.commit()
            conn.close()
            payload = {"ticket_id": ticket_id, "trace_id": trace_id,
                       "category": prediction["category"],
                       "priority": prediction["priority"],
                       "category_confidence": prediction.get("category_confidence"),
                       "draft": answer["draft"], "sources": answer["sources"],
                       "run_id": answer["run_id"], "duplicate": False}
            status = 200
        except Exception as exc:  # noqa: BLE001 - return a clean 400, never crash
            METRICS["errors"] += 1
            payload, status = {"error": str(exc), "trace_id": trace_id}, 400
        log("intake", trace_id, "POST", self.path, status,
            (time.time() - started) * 1000)
        self._send(status, payload, trace_id)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    init_db()
    print(f"intake service on port {PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
