"""Command-line client for Support Ticket Intelligence.

Usage:
  python3 cli.py ticket "My package has not arrived yet"
  python3 cli.py ticket "I was charged twice" --request-id demo-1
  python3 cli.py predict "I cannot log in"
  python3 cli.py health
  python3 cli.py metrics
  python3 cli.py runs
Standard library only.
"""
import argparse
import json
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8001"
PREDICT = "http://127.0.0.1:8002"
ANSWER = "http://127.0.0.1:8003"


def get(url):
    with urllib.request.urlopen(url, timeout=10) as resp:
        return json.loads(resp.read())


def post(url, payload):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser(description="Support Ticket Intelligence CLI")
    sub = parser.add_subparsers(dest="command", required=True)
    ticket = sub.add_parser("ticket", help="Submit a ticket and get a triage + draft reply")
    ticket.add_argument("text")
    ticket.add_argument("--request-id", default=None)
    predict = sub.add_parser("predict", help="Predict category and priority only")
    predict.add_argument("text")
    sub.add_parser("health", help="Check all three services")
    sub.add_parser("metrics", help="Show metrics for all three services")
    sub.add_parser("runs", help="List recent answer-service runs")
    args = parser.parse_args()
    try:
        if args.command == "ticket":
            payload = {"text": args.text}
            if args.request_id:
                payload["request_id"] = args.request_id
            print(json.dumps(post(BASE + "/ticket", payload), indent=2))
        elif args.command == "predict":
            print(json.dumps(post(PREDICT + "/predict", {"text": args.text}), indent=2))
        elif args.command == "health":
            for name, url in (("intake", BASE), ("prediction", PREDICT), ("answer", ANSWER)):
                print(name, json.dumps(get(url + "/health")))
        elif args.command == "metrics":
            for name, url in (("intake", BASE), ("prediction", PREDICT), ("answer", ANSWER)):
                print(name, json.dumps(get(url + "/metrics")))
        elif args.command == "runs":
            print(json.dumps(get(ANSWER + "/runs"), indent=2))
    except urllib.error.URLError as exc:
        print(f"Error: could not reach the services ({exc}). "
              "Start them first with: python3 run_local.py")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
