"""Prediction service — port 8002.

POST /predict {"text": "..."} -> category + priority from the trained
Naive Bayes model (ml/model.json). GET /health, GET /metrics.
Own SQLite table: predictions. Structured JSON logging, trace ids.
Standard library only.
"""
import json
import os
import sqlite3
import sys
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from classifier import TicketClassifier  # noqa: E402

PORT = int(os.environ.get("PORT", "8002"))
BASE = os.path.dirname(os.path.abspath(__file__))
DB = os.environ.get("PREDICTION_DB", os.path.join(BASE, "predictions.db"))
MODEL = os.environ.get("MODEL_PATH", os.path.join(BASE, "..", "..", "ml", "model.json"))

START = time.time()
METRICS = {"requests": 0, "errors": 0}
CLF = TicketClassifier.load(MODEL)


def log(service, trace_id, method, path, status, latency_ms):
    print(json.dumps({"time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                      "service": service, "trace_id": trace_id,
                      "method": method, "path": path, "status": status,
                      "latency_ms": round(latency_ms, 2)}), flush=True)


def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS predictions (
        id INTEGER PRIMARY KEY AUTOINCREMENT, trace_id TEXT, text TEXT,
        category TEXT, priority TEXT, category_confidence REAL,
        priority_confidence REAL, created_at REAL)""")
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
            payload, status = {"status": "ok", "service": "prediction"}, 200
        elif self.path == "/metrics":
            payload = {"service": "prediction", "requests": METRICS["requests"],
                       "errors": METRICS["errors"],
                       "uptime_seconds": round(time.time() - START, 1)}
            status = 200
        else:
            payload, status = {"error": "not found"}, 404
            METRICS["errors"] += 1
        log("prediction", trace_id, "GET", self.path, status,
            (time.time() - started) * 1000)
        self._send(status, payload, trace_id)

    def do_POST(self):
        started = time.time()
        trace_id = self._trace()
        METRICS["requests"] += 1
        if self.path != "/predict":
            METRICS["errors"] += 1
            log("prediction", trace_id, "POST", self.path, 404,
                (time.time() - started) * 1000)
            return self._send(404, {"error": "not found"}, trace_id)
        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length) or b"{}")
            text = (data.get("text") or "").strip()
            if not text:
                raise ValueError("text is required")
            result = CLF.predict(text)
            conn = sqlite3.connect(DB)
            conn.execute(
                "INSERT INTO predictions (trace_id, text, category, priority,"
                " category_confidence, priority_confidence, created_at)"
                " VALUES (?,?,?,?,?,?,?)",
                (trace_id, text, result["category"], result["priority"],
                 result["category_confidence"], result["priority_confidence"],
                 time.time()))
            conn.commit()
            conn.close()
            payload = {"trace_id": trace_id, **result}
            status = 200
        except Exception as exc:  # noqa: BLE001 - return a clean 400, never crash
            METRICS["errors"] += 1
            payload, status = {"error": str(exc), "trace_id": trace_id}, 400
        log("prediction", trace_id, "POST", self.path, status,
            (time.time() - started) * 1000)
        self._send(status, payload, trace_id)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    init_db()
    print(f"prediction service on port {PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()
