#!/usr/bin/env python3
"""
=========================================================
GATE 8 — DIRECT POWER MODE CHECK (FINAL)
60W & 30W — PM125 LOAD + RUP POWER REPORT
=========================================================
"""

import time
import can
from tests.switch.pm125 import PM125

# ==============================
# CAN CONFIG
# ==============================
CAN_IFACE = "can0"
CAN_TX_ID = 0x002
RUP_RESPONSE_ID = 0x065

POWER_REPORT_REQUEST = 0xA2

# ==============================
# TEST POINTS (ONLY WHAT YOU WANT)
# ==============================
TEST_POINTS = [
    {
        "label": "60W",
        "can_cmd": 0x21,      # POWER_TO_60W
        "pdo_index": 4,
        "voltage_mv": 20000,
        "current_ma": 2990,
        "expected_w": 60,
    },
    {
        "label": "30W",
        "can_cmd": 0x23,      # POWER_TO_30W
        "pdo_index": 3,
        "voltage_mv": 15000,
        "current_ma": 2000,
        "expected_w": 30,
    },
]

WAIT = 3
POWER_TOL = 0.25  # ±25%

# ==============================
# HELPERS
# ==============================
def send_can(bus, byte, desc=""):
    msg = can.Message(
        arbitration_id=CAN_TX_ID,
        data=[byte],
        is_extended_id=False
    )
    bus.send(msg)
    print(f"📤 CAN TX | {desc} | 0x{byte:02X}")

def flush_rx(bus):
    while bus.recv(timeout=0.0):
        pass

def decode_rup_power(byte):
    """
    Firmware sends:
        byte = 0xA0 + (power / 2)

    Accept ANY byte >= 0xA0
    """
    if byte < 0xA0:
        return None
    return (byte - 0xA0) * 2

def check_power(measured, expected):
    low = expected * (1 - POWER_TOL)
    high = expected * (1 + POWER_TOL)
    return low <= measured <= high, low, high

def wait_for_power_report(bus, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if not msg:
            continue
        if msg.arbitration_id != RUP_RESPONSE_ID:
            continue
        if not msg.data:
            continue

        raw = msg.data[0]
        power = decode_rup_power(raw)

        print(f"📥 CAN RX | DATA={[hex(b) for b in msg.data]}")

        if power is not None:
            return power, raw

    return None, None

# ==============================
# MAIN
# ==============================
def main():
    print("\n=======================================")
    print("   GATE 8 — DIRECT POWER MODE CHECK     ")
    print("=======================================\n")

    # ---- CAN ----
    bus = can.interface.Bus(
        channel=CAN_IFACE,
        interface="socketcan"   # bustype deprecated → fixed
    )

    # ---- PM125 ----
    pm = PM125()
    print("✅ PM125 connected\n")

    all_pass = True

    for p in TEST_POINTS:
        print("\n--------------------------------------------")
        print(f"Testing {p['label']} (Target ≥ {p['expected_w']}W)")
        print("--------------------------------------------")

        flush_rx(bus)

        # 1) Set RUP PDO preference
        send_can(bus, p["can_cmd"], f"SET PDO → {p['label']}")
        time.sleep(0.5)

        # 2) PM125 negotiates + pulls power
        pm.set_voltage(p["pdo_index"], p["voltage_mv"])
        time.sleep(WAIT)

        pm.set_current(p["current_ma"])
        time.sleep(WAIT)

        stat = pm.get_statistics()
        meas_v = stat["voltage_mv"]
        meas_i = stat["current_ma"]
        meas_w = (meas_v * meas_i) / 1_000_000.0

        print(f"PM125 measured: {meas_w:.2f} W")

        pm_ok, low, high = check_power(meas_w, p["expected_w"])
        if pm_ok:
            print(f"✔ PM PASS [{low:.1f}–{high:.1f}] W")
        else:
            print(f"❌ PM FAIL [{low:.1f}–{high:.1f}] W")
            all_pass = False

        # 3) Ask RUP what power it thinks it has
        send_can(bus, POWER_REPORT_REQUEST, "POWER_REPORT_REQUEST")

        rup_power, raw = wait_for_power_report(bus)

        if rup_power is None:
            print("❌ RUP did NOT respond with power report")
            all_pass = False
        else:
            print(f"RUP reports: {rup_power} W (raw 0x{raw:02X})")

            # ACCEPTANCE CRITERIA (REALISTIC)
            if rup_power >= p["expected_w"]:
                print("✔ RUP REPORT PASS (negotiated PDO ≥ requested)")
            else:
                print("❌ RUP REPORT FAIL (power below requested)")
                all_pass = False

        # Reset load
        pm.set_current(0)
        time.sleep(1)

    print("\n=======================================")
    if all_pass:
        print("✅ GATE 8 PASS — POWER REPORTING OK")
    else:
        print("❌ GATE 8 FAIL — CHECK LOGS")
    print("=======================================\n")

    bus.shutdown()
    return 0 if all_pass else 1


if __name__ == "__main__":
    exit(main())
