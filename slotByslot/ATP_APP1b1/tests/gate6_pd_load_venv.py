# tests/gate6_pd_load_venv.py
import argparse
import json
import time
import can

# ✅ These imports will work in the PM venv (brainstem installed there)
from switch.acroname_switch import select_rup_port_for_slot
from switch.pm125 import PM125


RESULT_PREFIX = "__GATE6_RESULT__:"


# CAN mapping
SLOT_TX_ID = {1: 0x001, 2: 0x002, 3: 0x004, 4: 0x003}
RUP_RESPONSE_ID = 0x063

CMD_PREFIX = 0x07
CMD_POWER_TO_60W = 0x21
CMD_POWER_TO_15W = 0x25
CMD_POWER_REPORT_REQUEST = 0xA2

POWER_TOL_PM = 0.3
POWER_TOL_RUP = 0.3

POWER_STEPS_60_MODE = [
    {"name": "60W",   "desired_mv": 20000, "target_power_w": 60},
    {"name": "45W",   "desired_mv": 15000, "target_power_w": 45},
    {"name": "30W",   "desired_mv": 12000, "target_power_w": 30},
    {"name": "22.5W", "desired_mv": 9000,  "target_power_w": 22.5},
    {"name": "15W",   "desired_mv": 5000,  "target_power_w": 15},
]
FINAL_15_MODE_STEP = {"name": "15W_AFTER_RUP_SET_15W", "desired_mv": 5000, "target_power_w": 15}


def log(msg: str):
    # IMPORTANT: wrapper will stream stdout
    print(msg, flush=True)


def _can_send(bus: can.BusABC, slot: int, cmd: int, payload=None):
    tx_id = SLOT_TX_ID.get(int(slot), 0x001)
    data = [CMD_PREFIX & 0xFF, cmd & 0xFF]
    if payload is not None:
        data += [b & 0xFF for b in payload]
    data = data[:8]

    msg = can.Message(arbitration_id=tx_id, data=data, is_extended_id=False)
    bus.send(msg)

    log(
        f"📤 CAN TX | can0  {tx_id:03X}   "
        f"[{len(data)}]  " +
        " ".join(f"{b:02X}" for b in data)
    )


def _measured_power_w(stat: dict) -> float:
    v = stat.get("voltage_mv", 0)
    i = stat.get("current_ma", 0)
    return (v * i) / 1_000_000.0


def _window(meas: float, target: float, tol: float):
    low = target * (1 - tol)
    high = target * (1 + tol)
    return (low <= meas <= high), low, high


def _negotiate_voltage(pm: PM125, desired_mv: int, try_indexes=(4, 3, 2, 1, 0), settle_s=2.0):
    for idx in try_indexes:
        pm.set_voltage(idx, desired_mv)
        time.sleep(settle_s)
        constat = pm.get_connection_status()
        actual_mv = constat.get("voltage_mv", -1)
        log(f"   try idx={idx} -> CONSTAT voltage={actual_mv} mV")
        if actual_mv > 0 and abs(actual_mv - desired_mv) <= int(desired_mv * 0.05):
            return True, idx, constat
    return False, None, pm.get_connection_status()


def _ramp_current(pm: PM125, target_ma: int, step_ma=250, delay_s=1.0):
    pm.set_current(0)
    time.sleep(0.5)
    current_ma = 0
    while current_ma < target_ma:
        current_ma = min(current_ma + step_ma, target_ma)
        pm.set_current(current_ma)
        time.sleep(delay_s)
        stat = pm.get_statistics()
        log(f"   ↳ set_current({current_ma} mA) | STAT: {stat}")


def _wait_until_pm_window(pm: PM125, target_w: float, timeout_s=20.0, poll_s=1.0):
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


def _flush_can(bus: can.BusABC, duration_s=0.25):
    t0 = time.time()
    while time.time() - t0 < duration_s:
        _ = bus.recv(timeout=0.01)


def _wait_for_power_report(bus: can.BusABC, timeout_s=2.0):
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


def _run_step(pm, can_bus, slot, step, results):
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
    }

    log("--------------------------------------------------")
    log(f"[ GATE6] STEP {name} | desired {desired_mv/1000:.1f}V | target {target_w}W")

    log("[ GATE6] PM125: negotiating voltage...")
    ok_v, _, constat = _negotiate_voltage(pm, desired_mv)
    log(f"[ GATE6] FINAL CONSTAT: {constat}")

    if not ok_v:
        step_res["reason"] = f"Could not negotiate {desired_mv/1000:.1f}V"
        results["failed_step"] = name
        results["steps"].append(step_res)
        return False

    step_res["negotiated"] = True
    max_i_ma = int(constat.get("max_current_ma", 3000))

    v_v = desired_mv / 1000.0
    target_i_ma = int((target_w / v_v) * 1000)

    if target_i_ma > max_i_ma:
        log(f"[ GATE6] Clamp: target {target_i_ma} mA > max {max_i_ma} mA")
        target_i_ma = max_i_ma

    log(f"[ GATE6] PM125: ramp current to {target_i_ma} mA")
    _ramp_current(pm, target_i_ma)

    ok_pm, pm_w, low, high, _ = _wait_until_pm_window(pm, target_w)
    step_res["pm_w"] = pm_w
    if not ok_pm:
        step_res["reason"] = f"PM power {pm_w:.2f}W not in [{low:.2f},{high:.2f}]"
        results["failed_step"] = name
        results["steps"].append(step_res)
        return False

    step_res["pm_ok"] = True
    log(f"[ GATE6] PM PASS — {pm_w:.2f}W in [{low:.2f},{high:.2f}]")

    log("[ GATE6] RUP: POWER_REPORT_REQUEST (0xA2)")
    _flush_can(can_bus, 0.25)
    _can_send(can_bus, slot, CMD_POWER_REPORT_REQUEST)

    rup_w, raw0, raw_data = _wait_for_power_report(can_bus, timeout_s=2.0)
    if rup_w is None:
        step_res["reason"] = "No / invalid POWER_REPORT from RUP"
        results["failed_step"] = name
        results["steps"].append(step_res)
        return False

    step_res["rup_w"] = rup_w
    step_res["rup_ok"] = True
    log(f"[ GATE6] RUP reports {rup_w}W (raw0=0x{raw0:02X}, data={[f'0x{b:02X}' for b in raw_data]})")

    rup_ok, rlow, rhigh = _window(float(rup_w), float(target_w), POWER_TOL_RUP)
    if not rup_ok:
        step_res["reason"] = f"RUP {rup_w}W NOT in [{rlow:.1f},{rhigh:.1f}] for TARGET {target_w}W"
        results["failed_step"] = name
        results["steps"].append(step_res)
        return False

    log(f"[ GATE6] RUP PASS — {rup_w}W in [{rlow:.1f},{rhigh:.1f}] for TARGET {target_w}W")

    log("[ GATE6] Reset PM125 current to 0 mA")
    pm.set_current(0)
    time.sleep(2)

    results["steps"].append(step_res)
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", type=int, required=True)
    args = ap.parse_args()
    slot = int(args.slot)

    results = {"pass": False, "slot": slot, "failed_step": None, "steps": []}

    try:
        log(f"[ GATE6] (venv) slot={slot} starting")

        # 0) Switch Acroname to this slot
        port = select_rup_port_for_slot(slot, log_cb=log)
        log(f"[ACRONAME] Slot {slot} -> port {port}")

        # 1) CAN bus
        can_bus = can.Bus(interface="socketcan", channel="can0")

        # 2) PM125
        pm = PM125("/dev/ttyUSB0")
        log("[ GATE6] PM125 connected")

        # clean start
        log("[ GATE6] PM125 clean start: set 5V and 0mA")
        pm.set_current(0)
        time.sleep(0.3)
        pm.set_voltage(0, 5000)
        time.sleep(2.0)

        # RUP to 60W mode
        log("[ GATE6] RUP: sending POWER_TO_60W")
        _can_send(can_bus, slot, CMD_POWER_TO_60W)
        time.sleep(5.0)

        # steps
        for step in POWER_STEPS_60_MODE:
            if not _run_step(pm, can_bus, slot, step, results):
                raise RuntimeError("Gate6 failed")

        # switch to 15W mode and verify 15W again
        log("[ GATE6] RUP: sending POWER_TO_15W")
        _can_send(can_bus, slot, CMD_POWER_TO_15W)
        time.sleep(2.0)

        if not _run_step(pm, can_bus, slot, FINAL_15_MODE_STEP, results):
            raise RuntimeError("Gate6 failed")

        results["pass"] = True
        log("[ GATE6] PASS — All steps OK")

        # cleanup PM + CAN (local to this subprocess only)
        try:
            pm.set_current(0)
        except Exception:
            pass
        try:
            pm.close()
        except Exception:
            pass
        try:
            can_bus.shutdown()
        except Exception:
            pass

        # print JSON marker for wrapper
        print(RESULT_PREFIX + json.dumps(results), flush=True)
        raise SystemExit(0)

    except Exception as e:
        log(f"[ GATE6][FAIL] {e}")
        results["pass"] = False
        if results["failed_step"] is None:
            results["failed_step"] = "EXCEPTION"
        print(RESULT_PREFIX + json.dumps(results), flush=True)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
