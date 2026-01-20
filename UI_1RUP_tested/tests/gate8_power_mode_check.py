# tests/gate8_test.py
"""
Gate 8 — Power mode + reporting check (PM125 vs RUP)

Returns:
    True  -> PASS
    False -> FAIL

You can call:  from tests.gate8_test import run_gate8_power_mode_check
"""

import time
import can
from tests.switch.pm125 import PM125

from tests.CAN.can_bus import get_can_bus
from tests.CAN.can_commands import power_60w, power_report_request

WAIT_NEGOTIATE = 5
POWER_TOL_PM = 0.20        # PM pass window (±20%)
POWER_TOL_MATCH = 0.25     # PM vs RUP match window (±25%)

RUP_RESPONSE_ID = 0x065

# PM-only test steps (RUP set to 60W once at start, as you decided)
POWER_STEPS = [
    {"name": "60W",   "desired_mv": 20000, "target_power_w": 60},
    {"name": "45W",   "desired_mv": 15000, "target_power_w": 45},
    {"name": "30W",   "desired_mv": 12000, "target_power_w": 30},
    {"name": "22.5W", "desired_mv": 9000,  "target_power_w": 22.5},
    {"name": "15W",   "desired_mv": 5000,  "target_power_w": 15},
]

def _measured_power_w(stat: dict) -> float:
    v = stat.get("voltage_mv", 0)
    i = stat.get("current_ma", 0)
    return (v * i) / 1_000_000.0

def _in_pm_window(meas_w: float, target_w: float):
    low = target_w * (1 - POWER_TOL_PM)
    high = target_w * (1 + POWER_TOL_PM)
    return (low <= meas_w <= high), low, high

def _match_within_tolerance(a: float, b: float, tol: float):
    low = b * (1 - tol)
    high = b * (1 + tol)
    return (low <= a <= high), low, high

def _negotiate_voltage(pm: PM125, desired_mv: int, try_indexes=(4, 3, 2, 1, 0), settle_s: float = 2.0, log=None):
    for idx in try_indexes:
        pm.set_voltage(idx, desired_mv)
        time.sleep(settle_s)

        constat = pm.get_connection_status()
        actual_mv = constat.get("voltage_mv", -1)
        if log:
            log(f"   try idx={idx} -> CONSTAT voltage={actual_mv} mV")

        if actual_mv > 0 and abs(actual_mv - desired_mv) <= int(desired_mv * 0.05):
            return True, idx, constat

    return False, None, pm.get_connection_status()

def _ramp_current(pm: PM125, target_ma: int, step_ma: int = 250, delay_s: float = 1.0, log=None):
    pm.set_current(0)
    time.sleep(0.5)

    current_ma = 0
    while current_ma < target_ma:
        current_ma = min(current_ma + step_ma, target_ma)
        pm.set_current(current_ma)
        time.sleep(delay_s)

        stat = pm.get_statistics()
        if log:
            log(f"   ↳ set_current({current_ma} mA) | STAT: {stat}")

def _wait_until_power(pm: PM125, target_w: float, timeout_s: float = 20.0, poll_s: float = 1.0, log=None):
    t0 = time.time()
    last_stat = None
    last_w = 0.0
    low = high = 0.0

    while time.time() - t0 < timeout_s:
        last_stat = pm.get_statistics()
        last_w = _measured_power_w(last_stat)
        ok, low, high = _in_pm_window(last_w, target_w)

        if log:
            v = last_stat.get("voltage_mv", 0) / 1000.0
            i = last_stat.get("current_ma", 0) / 1000.0
            log(f"… PM125: {v:.2f} V, {i:.3f} A => {last_w:.2f} W (target {target_w} W)")

        if ok:
            return True, last_w, low, high, last_stat

        time.sleep(poll_s)

    return False, last_w, low, high, last_stat

def _decode_rup_power(byte0: int):
    # Your decode rule
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


# =========================================================
# PUBLIC API — CALL THIS FROM UI
# =========================================================
def run_gate8_power_mode_check(log_cb=None) -> bool:
    """
    Gate 8:
    - Send POWER_TO_60W once at start
    - For each step, PM125 negotiates voltage + ramps current to hit target power
    - Request POWER_REPORT from RUP and compare vs PM measured power

    Returns:
        True / False
    """

    def log(msg: str):
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    can_bus = None
    pm = None

    try:
        log("[GATE8] Starting Gate 8 power check")

        # ---- CAN ----
        can_bus = get_can_bus()

        # ---- PM125 ----
        pm = PM125("/dev/ttyUSB0")
        log("[GATE8] PM125 connected")

        # ---- Send RUP 60W ONCE ----
        log("[GATE8] RUP: sending POWER_TO_60W (once at start)")
        power_60w()
        time.sleep(1.0)

        for step in POWER_STEPS:
            desired_mv = step["desired_mv"]
            target_w = step["target_power_w"]

            log("--------------------------------------------------")
            log(f"[GATE8] STEP {step['name']} | desired {desired_mv/1000:.1f}V | target {target_w}W")

            # 1) Negotiate voltage
            log("[GATE8] PM125: negotiating voltage...")
            ok_v, used_idx, constat = _negotiate_voltage(pm, desired_mv, log=log)
            log(f"[GATE8] FINAL CONSTAT: {constat}")

            if not ok_v:
                log(f"[GATE8][FAIL] Could not negotiate {desired_mv/1000:.1f}V")
                return False

            max_i_ma = constat.get("max_current_ma", 3000)

            # target current from target power and desired voltage
            v_v = desired_mv / 1000.0
            target_i_ma = int((target_w / v_v) * 1000)

            if target_i_ma > max_i_ma:
                log(f"[GATE8] Clamp: target {target_i_ma} mA > max {max_i_ma} mA")
                target_i_ma = max_i_ma

            # 2) Ramp current
            log(f"[GATE8] PM125: ramp current to {target_i_ma} mA")
            _ramp_current(pm, target_i_ma, step_ma=250, delay_s=1.0, log=log)

            # 3) Wait for PM power window
            ok_pm, pm_w, low, high, _ = _wait_until_power(pm, target_w, timeout_s=20, poll_s=1.0, log=log)
            if not ok_pm:
                log(f"[GATE8][FAIL] PM power {pm_w:.2f}W not in [{low:.2f},{high:.2f}]")
                return False

            log(f"[GATE8] PM PASS — {pm_w:.2f}W in [{low:.2f},{high:.2f}]")

            # 4) Request RUP power report
            log("[GATE8] RUP: POWER_REPORT_REQUEST (0xA2)")
            _flush_can(can_bus, 0.25)
            power_report_request()

            rup_w, raw0, raw_data = _wait_for_power_report(can_bus, timeout_s=2.0)
            if rup_w is None:
                log("[GATE8][FAIL] No / invalid POWER_REPORT from RUP")
                return False

            log(f"[GATE8] RUP reports {rup_w}W (raw0=0x{raw0:02X}, data={[f'0x{b:02X}' for b in raw_data]})")

            # 5) Compare RUP vs PM
            match, mlow, mhigh = _match_within_tolerance(rup_w, pm_w, POWER_TOL_MATCH)
            if not match:
                log(f"[GATE8][FAIL] MISMATCH — RUP {rup_w}W not in [{mlow:.1f},{mhigh:.1f}] of PM {pm_w:.1f}W")
                return False

            log(f"[GATE8] MATCH PASS — RUP {rup_w}W within [{mlow:.1f},{mhigh:.1f}] of PM {pm_w:.1f}W")

            # Reset load between steps
            log("[GATE8] Reset PM125 current to 0 mA")
            pm.set_current(0)
            time.sleep(2)

        log("[GATE8] PASS — All steps OK")
        return True

    except Exception as e:
        log(f"[GATE8][ERROR] Exception: {e}")
        return False

    finally:
        # Always try to reset load + close devices
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
