"""Run all three services locally without Docker.

Usage: python3 run_local.py
Stops all services with Ctrl-C. Services: intake 8001, prediction 8002,
answer 8003. Uses the same ports as docker-compose.yml.
"""
import os
import signal
import subprocess
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
SERVICES = [
    ("prediction", os.path.join(BASE, "services", "prediction-service", "main.py"), "8002"),
    ("answer", os.path.join(BASE, "services", "answer-service", "main.py"), "8003"),
    ("intake", os.path.join(BASE, "services", "intake-service", "main.py"), "8001"),
]


def main():
    procs = []

    def _stop(signum, frame):  # noqa: ARG001 - stop children on SIGTERM too
        for _, proc in procs:
            proc.terminate()
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)
    try:
        for name, script, port in SERVICES:
            env = dict(os.environ, PORT=port)
            proc = subprocess.Popen([sys.executable, script], env=env)
            procs.append((name, proc))
            print(f"started {name} on port {port} (pid {proc.pid})", flush=True)
        print("All services running. Press Ctrl-C to stop.", flush=True)
        for _, proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        print("Stopping services...", flush=True)
    finally:
        for name, proc in procs:
            proc.terminate()
        for name, proc in procs:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("Stopped.", flush=True)


if __name__ == "__main__":
    main()
