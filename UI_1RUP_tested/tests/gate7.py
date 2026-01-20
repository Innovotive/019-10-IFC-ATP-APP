# tests/gate7.py
"""
GATE 7 — Power mode + reporting check (PM125 vs RUP)

Change you requested:
- Compare RUP reported power vs the *TARGET power* of the step (not vs PM measured power).

Flow:
1) PM125 clean start (5V + 0mA)
2) Send RUP POWER_TO_60W once
3) Run PM steps: 60, 45, 30, 22.5, 15
   - PM negotiates voltage, ramps current, confirms PM reached power (still checked)
   - Request RUP POWER_REPORT_REQUEST, decode, compare RUP vs TARGET power
4) Send RUP POWER_TO_15W
5) Pull 15W again, request RUP report again, compare RUP vs TARGET(15W)

Public APIs:
- run_gate7(...) -> returns (results_dict, logs_list)
- run_gate7_bool(...) -> returns True/False

CLI:
    python3 -m tests.gate7
"""

import time
import can
from tests.switch.pm125 import PM125

from tests.CAN.can_bus import get_can_bus
from tests.CAN.can_commands import power_60w, power_15w, power_report_request


# ==============================
# CONFIG
# ==============================
POWER_TOL_PM = 0.3        # PM pass window (±30%)
POWER_TOL_RUP = 0.3        # RUP vs TARGET window (±30%) 

RUP_RESPONSE_ID = 0x063

POWER_STEPS_60_MODE = [
    {"name": "60W",   "desired_mv": 20000, "target_power_w": 60},
    {"name": "45W",   "desired_mv": 15000, "target_power_w": 45},
    {"name": "30W",   "desired_mv": 12000, "target_power_w": 30},
    {"name": "22.5W", "desired_mv": 9000,  "target_power_w": 22.5},
    {"name": "15W",   "desired_mv": 5000,  "target_power_w": 15},
]

FINAL_15_MODE_STEP = {"name": "15W_AFTER_RUP_SET_15W", "desired_mv": 5000, "target_power_w": 15}


# ==============================
# INTERNAL HELPERS
# ==============================
def _measured_power_w(stat: dict) -> float:
    v = stat.get("voltage_mv", 0)
    i = stat.get("current_ma", 0)
    return (v * i) / 1_000_000.0

def _window(meas: float, target: float, tol: float):
    low = target * (1 - tol)
    high = target * (1 + tol)
    return (low <= meas <= high), low, high

def _negotiate_voltage(pm: PM125, desired_mv: int, log,
                      try_indexes=(4, 3, 2, 1, 0), settle_s: float = 2.0):
    for idx in try_indexes:
        pm.set_voltage(idx, desired_mv)
        time.sleep(settle_s)

        constat = pm.get_connection_status()
        actual_mv = constat.get("voltage_mv", -1)
        log(f"   try idx={idx} -> CONSTAT voltage={actual_mv} mV")

        if actual_mv > 0 and abs(actual_mv - desired_mv) <= int(desired_mv * 0.05):
            return True, idx, constat

    return False, None, pm.get_connection_status()

def _ramp_current(pm: PM125, target_ma: int, log, step_ma: int = 250, delay_s: float = 1.0):
    pm.set_current(0)
    time.sleep(0.5)

    current_ma = 0
    while current_ma < target_ma:
        current_ma = min(current_ma + step_ma, target_ma)
        pm.set_current(current_ma)
        time.sleep(delay_s)

        stat = pm.get_statistics()
        log(f"   ↳ set_current({current_ma} mA) | STAT: {stat}")

def _wait_until_pm_window(pm: PM125, target_w: float, log,
                          timeout_s: float = 20.0, poll_s: float = 1.0):
    t0 = time.time()
    last_stat = None
    last_w = 0.0
    low = high = 0.0

    while time.time() - t0 < timeout_s:
        last_stat = pm.get_statistics()
        last_w = _measured_power_w(last_stat)
        ok, low, high = _window(last_w, target_w, POWER_TOL_PM)

        v = last_stat.get("voltage_mv", 0) / 1000.0
        i = last_stat.get("current_ma", 0) / 1000.0
        log(f"… PM125: {v:.2f} V, {i:.3f} A => {last_w:.2f} W (target {target_w} W)")

        if ok:
            return True, last_w, low, high, last_stat

        time.sleep(poll_s)

    return False, last_w, low, high, last_stat

def _decode_rup_power(byte0: int):
    if byte0 < 0xA0:
        return None
    return (byte0 - 0xA0) * 2  # W

def _flush_can(bus: can.BusABC, duration_s: float = 0.25):
    t0 = time.time()
    while time.time() - t0 < duration_s:
        _ = bus.recv(timeout=0.01)

def _wait_for_power_report(bus: can.BusABC, timeout_s: float = 2.0):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if not msg:
            continue
        if msg.arbitration_id != RUP_RESPONSE_ID:
            continue
        if not msg.data or len(msg.data) < 1:
            continue

        raw0 = msg.data[0]
        rup_w = _decode_rup_power(raw0)
        return rup_w, raw0, list(msg.data)

    return None, None, None


def _run_single_pm_step(pm: PM125, can_bus: can.BusABC, step: dict, log, fail_fn):
    desired_mv = step["desired_mv"]
    target_w = step["target_power_w"]
    name = step["name"]

    step_res = {
        "name": name,
        "desired_mv": desired_mv,
        "target_w": target_w,
        "negotiated": False,
        "pm_ok": False,
        "rup_ok": False,
        "pm_w": None,
        "rup_w": None,
        "reason": None,
        "rup_vs_target_low": None,
        "rup_vs_target_high": None,
    }

    log("--------------------------------------------------")
    log(f"[GATE7] STEP {name} | desired {desired_mv/1000:.1f}V | target {target_w}W")

    # 1) Negotiate voltage
    log("[GATE7] PM125: negotiating voltage...")
    ok_v, _, constat = _negotiate_voltage(pm, desired_mv, log)
    log(f"[GATE7] FINAL CONSTAT: {constat}")

    if not ok_v:
        return fail_fn(name, step_res, f"Could not negotiate {desired_mv/1000:.1f}V")

    step_res["negotiated"] = True
    max_i_ma = constat.get("max_current_ma", 3000)

    # target current from target power and desired voltage
    v_v = desired_mv / 1000.0
    target_i_ma = int((target_w / v_v) * 1000)

    if target_i_ma > max_i_ma:
        log(f"[GATE7] Clamp: target {target_i_ma} mA > max {max_i_ma} mA")
        target_i_ma = max_i_ma

    # 2) Ramp current
    log(f"[GATE7] PM125: ramp current to {target_i_ma} mA")
    _ramp_current(pm, target_i_ma, log, step_ma=250, delay_s=1.0)

    # 3) Wait for PM power window (still required)
    ok_pm, pm_w, low, high, _ = _wait_until_pm_window(pm, target_w, log, timeout_s=20, poll_s=1.0)
    step_res["pm_w"] = pm_w

    if not ok_pm:
        return fail_fn(name, step_res, f"PM power {pm_w:.2f}W not in [{low:.2f},{high:.2f}]")

    step_res["pm_ok"] = True
    log(f"[GATE7] PM PASS — {pm_w:.2f}W in [{low:.2f},{high:.2f}]")

    # 4) Request RUP power report
    log("[GATE7] RUP: POWER_REPORT_REQUEST (0xA2)")
    _flush_can(can_bus, 0.25)
    power_report_request()

    rup_w, raw0, raw_data = _wait_for_power_report(can_bus, timeout_s=2.0)
    if rup_w is None:
        return fail_fn(name, step_res, "No / invalid POWER_REPORT from RUP")

    step_res["rup_w"] = rup_w
    step_res["rup_ok"] = True
    log(f"[GATE7] RUP reports {rup_w}W (raw0=0x{raw0:02X}, data={[f'0x{b:02X}' for b in raw_data]})")

    # 5) Compare RUP vs TARGET (your requested change)
    rup_ok, rlow, rhigh = _window(float(rup_w), float(target_w), POWER_TOL_RUP)
    step_res["rup_vs_target_low"] = rlow
    step_res["rup_vs_target_high"] = rhigh

    if not rup_ok:
        return fail_fn(
            name,
            step_res,
            f"RUP {rup_w}W NOT in [{rlow:.1f},{rhigh:.1f}] for TARGET {target_w}W"
        )

    log(f"[GATE7] RUP PASS — {rup_w}W in [{rlow:.1f},{rhigh:.1f}] for TARGET {target_w}W")

    # Reset load between steps
    log("[GATE7] Reset PM125 current to 0 mA")
    pm.set_current(0)
    time.sleep(2)

    return step_res


# =========================================================
# PUBLIC API — DETAILED (returns results + logs)
# =========================================================
def run_gate7(log_cb=None):
    logs = []
    results = {"pass": False, "failed_step": None, "steps": []}

    def log(msg: str):
        logs.append(msg)
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    def fail(step_name: str, step_res: dict, reason: str):
        step_res["reason"] = reason
        results["steps"].append(step_res)
        results["failed_step"] = step_name
        log(f"[GATE7][FAIL] {reason}")
        return results, logs

    can_bus = None
    pm = None

    try:
        log("[GATE7] Starting Gate 7 power check")

        can_bus = get_can_bus()
        pm = PM125("/dev/ttyUSB0")
        log("[GATE7] PM125 connected")

        # Clean start
        try:
            log("[GATE7] PM125 clean start: set 5V and 0mA")
            pm.set_current(0)
            time.sleep(0.3)
            pm.set_voltage(0, 5000)
            time.sleep(2.0)
        except Exception as e:
            log(f"[GATE7][WARN] PM125 clean start failed: {e}")

        # PART 1: RUP 60W once, then run 60/45/30/22.5/15
        log("[GATE7] RUP: sending POWER_TO_60W (once at start)")
        power_60w()
        time.sleep(2.0)

        for step in POWER_STEPS_60_MODE:
            out = _run_single_pm_step(pm, can_bus, step, log, fail)
            if isinstance(out, tuple):  # fail returned (results, logs)
                return out
            results["steps"].append(out)

        # PART 2: switch RUP to 15W, then pull 15W again + compare vs TARGET(15)
        log("==================================================")
        log("[GATE7] FINAL: switch RUP to 15W, pull 15W again, read RUP report")
        log("==================================================")

        log("[GATE7] RUP: sending POWER_TO_15W")
        power_15w()
        time.sleep(1.5)

        out = _run_single_pm_step(pm, can_bus, FINAL_15_MODE_STEP, log, fail)
        if isinstance(out, tuple):
            return out
        results["steps"].append(out)

        results["pass"] = True
        log("[GATE7] PASS — All steps OK")
        return results, logs

    except Exception as e:
        log(f"[GATE7][ERROR] Exception: {e}")
        results["pass"] = False
        results["failed_step"] = results["failed_step"] or "EXCEPTION"
        return results, logs

    finally:
        try:
            if pm:
                pm.set_current(0)
        except Exception:
            pass
        try:
            if pm and hasattr(pm, "close"):
                pm.close()
        except Exception:
            pass
        try:
            if can_bus:
                can_bus.shutdown()
        except Exception:
            pass


# =========================================================
# UI-FRIENDLY WRAPPER — RETURNS ONLY True/False
# =========================================================
def run_gate7_bool(log_cb=None) -> bool:
    results, _logs = run_gate7(log_cb=log_cb)
    return bool(results.get("pass", False))

"""
# =========================================================
# CLI RUNNER
# =========================================================
if __name__ == "__main__":
    results, logs = run_gate7()
    print("\nRESULT:", results)
    raise SystemExit(0 if results.get("pass") else 1)
"""