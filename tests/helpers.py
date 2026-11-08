"""Helpers for starting the three services in integration tests."""
import os
import subprocess
import sys
import time
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wait_for(url, timeout=15):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.3)
    return False


def start_services(tmpdir):
    """Start prediction, answer, intake on 8002/8003/8001 with temp DBs."""
    env = dict(os.environ)
    env["PREDICTION_DB"] = os.path.join(tmpdir, "predictions.db")
    env["ANSWER_DB"] = os.path.join(tmpdir, "runs.db")
    env["INTAKE_DB"] = os.path.join(tmpdir, "tickets.db")
    env["FLAGS_PATH"] = os.path.join(BASE, "flags.json")
    procs = []
    for service, port in (("prediction-service", "8002"),
                          ("answer-service", "8003"),
                          ("intake-service", "8001")):
        script = os.path.join(BASE, "services", service, "main.py")
        proc = subprocess.Popen(
            [sys.executable, script],
            env={**env, "PORT": port},
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        procs.append(proc)
    ok = all(wait_for(f"http://127.0.0.1:{p}/health")
             for p in ("8002", "8003", "8001"))
    return procs, ok


def stop_services(procs):
    for proc in procs:
        proc.terminate()
    for proc in procs:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
