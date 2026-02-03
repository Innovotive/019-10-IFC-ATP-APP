# tests/gate6_pd_load.py
import subprocess
import json
import os

# ✅ your PM venv python (contains brainstem + PM125 deps)
PM_VENV_PYTHON = "/home/raspberry/ATP/PM/acroname_env/bin/python"

# ✅ script that will run INSIDE the venv
# Put gate6_pd_load_venv.py in this repo under tests/
GATE6_VENV_SCRIPT = os.path.join(os.path.dirname(__file__), "gate6_pd_load_venv.py")

RESULT_PREFIX = "__GATE6_RESULT__:"


def run_gate6_pd_load(slot: int, log_cb=None):
    """
    Gate6 executed inside PM virtualenv via subprocess.

    Returns:
        (results_dict, logs_list)

    results_dict example:
      {"pass": True, "slot": 2, "steps": [...], "failed_step": None}
    """

    slot = int(slot)
    logs = []

    def log(line: str):
        logs.append(line)
        if log_cb:
            log_cb(line)
        else:
            print(line)

    if not os.path.exists(PM_VENV_PYTHON):
        out = f"[GATE6][ERROR] PM_VENV_PYTHON not found: {PM_VENV_PYTHON}"
        log(out)
        return {"pass": False, "slot": slot, "failed_step": "VENV_MISSING", "steps": [], "error": out}, logs

    if not os.path.exists(GATE6_VENV_SCRIPT):
        out = f"[GATE6][ERROR] GATE6_VENV_SCRIPT not found: {GATE6_VENV_SCRIPT}"
        log(out)
        return {"pass": False, "slot": slot, "failed_step": "SCRIPT_MISSING", "steps": [], "error": out}, logs

    log(f"[GATE6] (venv) Starting Gate6 for slot={slot}")
    log(f"[GATE6] (venv) python={PM_VENV_PYTHON}")
    log(f"[GATE6] (venv) script={GATE6_VENV_SCRIPT}")

    results = None

    try:
        proc = subprocess.Popen(
            [PM_VENV_PYTHON, "-u", GATE6_VENV_SCRIPT, "--slot", str(slot)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        # stream logs line-by-line
        for line in proc.stdout:
            line = (line or "").rstrip("\n")
            if not line:
                continue

            # If it's the JSON result marker, parse it
            if line.startswith(RESULT_PREFIX):
                payload = line[len(RESULT_PREFIX):].strip()
                try:
                    results = json.loads(payload)
                except Exception as e:
                    log(f"[GATE6][ERROR] Failed to parse result JSON: {e} | payload={payload}")
                continue

            log(line)

        rc = proc.wait(timeout=5)

        if results is None:
            # no marker printed -> treat as fail
            log(f"[GATE6][ERROR] No result marker received. rc={rc}")
            results = {"pass": False, "slot": slot, "failed_step": "NO_RESULT", "steps": [], "rc": rc}

        # If script exit code nonzero but results say pass, trust results, but warn
        if rc != 0 and results.get("pass", False):
            log(f"[GATE6][WARN] venv rc={rc} but results.pass=True (keeping pass=True).")

        return results, logs

    except Exception as e:
        log(f"[GATE6][ERROR] Exception running venv: {e}")
        return {"pass": False, "slot": slot, "failed_step": "EXCEPTION", "steps": [], "error": str(e)}, logs
