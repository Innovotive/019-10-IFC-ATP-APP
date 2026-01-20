# tests/gate7_venv_entry.py
import argparse
import json

from tests.gate7 import run_gate7  # import the same gate7 module inside the venv

MARKER = "=== JSON_RESULT ==="

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", type=int, required=True)
    args = ap.parse_args()

    results, logs = run_gate7(slot=args.slot, log_cb=None)

    # Print marker + JSON so parent process can parse it
    print(MARKER)
    print(json.dumps(results))

if __name__ == "__main__":
    main()
