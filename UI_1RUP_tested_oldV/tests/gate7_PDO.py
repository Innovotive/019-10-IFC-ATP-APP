import subprocess
import json

PM_VENV_PYTHON = "/home/raspberry/ATP/PM/acroname_env/bin/python"
GATE7_SCRIPT = "/home/raspberry/ATP/PM/switch/full_rup_negociation.py"


def run_gate7_all_rups():
    """
    Gate 7 – REAL Power Negotiation (ALL RUPs)

    Returns:
        results: dict {1: bool, 2: bool, 3: bool, 4: bool}
        logs:    str (full collected logs)
    """

    print("[GATE7] Starting power negotiation for ALL RUPs")

    logs = []

    try:
        proc = subprocess.Popen(
    [PM_VENV_PYTHON, "-u", GATE7_SCRIPT],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1
)

    except Exception as e:
        return {1: False, 2: False, 3: False, 4: False}, str(e)

    # 🔥 STREAM OUTPUT LIVE
    for line in proc.stdout:
        print(line, end="")        # → terminal
        logs.append(line)          # → UI

    proc.wait()
    full_logs = "".join(logs)

    if proc.returncode != 0:
        return {1: False, 2: False, 3: False, 4: False}, full_logs

    try:
        marker = "=== JSON_RESULT ==="
        if marker not in full_logs:
            raise ValueError("JSON_RESULT marker not found")

        json_text = full_logs.split(marker, 1)[1].strip()
        parsed = json.loads(json_text)

        results = {
            1: bool(parsed.get("1", False)),
            2: bool(parsed.get("2", False)),
            3: bool(parsed.get("3", False)),
            4: bool(parsed.get("4", False)),
        }

        return results, full_logs

    except Exception as e:
        full_logs += f"\n[GATE7] JSON parse failed: {e}"
        return {1: False, 2: False, 3: False, 4: False}, full_logs
