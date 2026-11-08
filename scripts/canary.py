"""Canary rollout for the detailed response style.

Usage: python3 scripts/canary.py [--percent 10] [--probes 10]
Reads flags.json, turns the canary on for a share of trace ids
(hash-bucketed), sends probe tickets to the intake service, checks the
error rate, then promotes the new style (writes response_style=detailed)
or rolls back (canary off). Leaves flags.json at the default (short,
canary off) unless promotion succeeds. Services must be running first:
python3 run_local.py
"""
import argparse
import hashlib
import json
import os
import urllib.error
import urllib.request

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FLAGS_PATH = os.path.join(BASE, "flags.json")
INTAKE = "http://127.0.0.1:8001/ticket"
PROBES = [
    "I was charged twice for my headphones this month",
    "My coffee maker arrived broken and does not turn on",
    "My backpack has not arrived yet and tracking has not moved",
    "I cannot log in to my account to check my order",
]


def load_flags():
    with open(FLAGS_PATH) as f:
        return json.load(f)


def save_flags(data):
    tmp = FLAGS_PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, FLAGS_PATH)


def probe(text):
    req = urllib.request.Request(
        INTAKE, data=json.dumps({"text": text}).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def main():
    parser = argparse.ArgumentParser(description="Canary rollout for the detailed reply style")
    parser.add_argument("--percent", type=int, default=10)
    parser.add_argument("--probes", type=int, default=10)
    args = parser.parse_args()
    flags = load_flags()
    flags["canary"] = {"enabled": True, "new_style": "detailed", "percent": args.percent}
    save_flags(flags)
    print(f"canary on: {args.percent}% of trace ids get the detailed style")
    errors = 0
    for i in range(args.probes):
        text = PROBES[i % len(PROBES)]
        try:
            result = probe(text)
            print(f"probe {i + 1}: {result['category']} / {result['priority']} "
                  f"(duplicate={result.get('duplicate')})")
        except (urllib.error.URLError, urllib.error.HTTPError) as exc:
            errors += 1
            print(f"probe {i + 1}: FAILED ({exc})")
    error_rate = errors / args.probes
    print(f"error rate: {error_rate:.0%} ({errors}/{args.probes})")
    if error_rate == 0:
        flags = load_flags()
        flags["response_style"] = "detailed"
        flags["canary"] = {"enabled": False, "new_style": "detailed", "percent": 10}
        save_flags(flags)
        print("PROMOTED: response_style is now 'detailed', canary off.")
    else:
        flags = load_flags()
        flags["canary"] = {"enabled": False, "new_style": "detailed", "percent": 10}
        save_flags(flags)
        print("ROLLED BACK: canary off, response_style unchanged.")


if __name__ == "__main__":
    main()
