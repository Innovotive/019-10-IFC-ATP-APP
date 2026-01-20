# tests/gate7.py
"""
GATE 7 — Run power negotiation in PM/acroname venv via subprocess (slot-aware)

FullRunner calls:
    results, logs = run_gate7(slot, log_cb=...)

Your external script must print a marker and JSON at the end:
    === JSON_RESULT ===
    {"pass": true, "slot": 1, ...}
"""

import subprocess
import json
from typing import Callable, Dict, Any, List, Tuple, Optional

PM_VENV_PYTHON = "/home/raspberry/ATP/PM/acroname_env/bin/python"
GATE7_SCRIPT   = "/home/raspberry/ATP/PM/switch/full_rup_negociation.py"

MARKER = "=== JSON_RESULT ==="


def run_gate7(slot: int, log_cb: Optional[Callable[[str], None]] = None) -> Tuple[Dict[str, Any], List[str]]:
    """
    Runs Gate7 for a SINGLE slot via subprocess (venv python).
    Returns: (results_dict, logs_list)
      results_dict MUST contain: {"pass": bool}
    """
    logs: List[str] = []
    results: Dict[str, Any] = {"pass": False, "slot": slot, "reason": None}

    def log(msg: str):
        # keep the same behavior as your UI logging
        logs.append(msg)
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    cmd = [PM_VENV_PYTHON, "-u", GATE7_SCRIPT, "--slot", str(slot)]
    log(f"[GATE7] Launching subprocess for slot {slot}")
    log(f"[GATE7] CMD: {' '.join(cmd)}")

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except Exception as e:
        results["reason"] = f"subprocess start failed: {e}"
        log(f"[GATE7][ERROR] {results['reason']}")
        return results, logs

    # Stream output live
    full_output_lines: List[str] = []
    try:
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip("\n")
            full_output_lines.append(line)
            log(line)
    finally:
        proc.wait()

    if proc.returncode != 0:
        results["reason"] = f"subprocess returncode={proc.returncode}"
        log(f"[GATE7][FAIL] {results['reason']}")
        return results, logs

    # Parse JSON from marker
    try:
        full_text = "\n".join(full_output_lines)

        if MARKER not in full_text:
            raise ValueError(f"marker '{MARKER}' not found in output")

        json_text = full_text.split(MARKER, 1)[1].strip()
        parsed = json.loads(json_text)

        # Accept either:
        #  A) {"pass": true, ...}
        #  B) {"1": true, "2": false, ...}  (older style)
        if isinstance(parsed, dict) and "pass" in parsed:
            results.update(parsed)
            results["pass"] = bool(results.get("pass", False))
        else:
            # older style: dict keyed by slot string
            results["pass"] = bool(parsed.get(str(slot), False))
            results["parsed_raw"] = parsed

        log(f"[GATE7] Parsed result: pass={results['pass']}")
        return results, logs

    except Exception as e:
        results["reason"] = f"JSON parse failed: {e}"
        log(f"[GATE7][ERROR] {results['reason']}")
        return results, logs
