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
# TEST POINTS (RUP1 ONLY)
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
POWER_TOL = 0.4


# ==============================
# HELPERS
# ==============================
def _decode_rup_power(byte):
    if byte < 0xA0:
        return None
    return (byte - 0xA0) * 2


def _wait_for_power_report(bus, timeout=2.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if not msg:
            continue
        if msg.arbitration_id != RUP_RESPONSE_ID:
            continue
        if not msg.data:
            continue

        return _decode_rup_power(msg.data[0]), msg.data[0]

    return None, None


def _check_power(measured, expected):
    low = expected * (1 - POWER_TOL)
    high = expected * (1 + POWER_TOL)
    return low <= measured <= high, low, high


# =========================================================
# PUBLIC API — CALLED BY UI
# =========================================================
def run_gate8_power_mode_check(log_cb=None):
    """
    Gate 8 (RUP1 only)

    Returns:
        True / False
    """

    def log(msg):
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    log("[GATE8] Starting power reporting check")

    # ---- CAN ----
    bus = can.interface.Bus(
        channel=CAN_IFACE,
        interface="socketcan"
    )

    # ---- PM125 ----
    try:
        pm = PM125()
        log("[GATE8] PM125 connected")
    except Exception as e:
        log(f"[GATE8][ERROR] PM125 connection failed: {e}")
        return False

    try:
        for p in TEST_POINTS:
            log(f"[GATE8] ---- Testing {p['label']} ----")

            # Flush RX
            while bus.recv(timeout=0.0):
                pass

            # 1) Set PDO
            msg = can.Message(
                arbitration_id=CAN_TX_ID,
                data=[p["can_cmd"]],
                is_extended_id=False
            )
            bus.send(msg)
            log(f"[GATE8] CAN TX → SET PDO {p['label']} (0x{p['can_cmd']:02X})")
            time.sleep(0.5)

            # 2) Pull power
            pm.set_voltage(p["pdo_index"], p["voltage_mv"])
            time.sleep(WAIT)

            pm.set_current(p["current_ma"])
            time.sleep(WAIT)

            stat = pm.get_statistics()
            meas_w = (stat["voltage_mv"] * stat["current_ma"]) / 1_000_000.0

            pm_ok, low, high = _check_power(meas_w, p["expected_w"])
            log(f"[GATE8] PM measured {meas_w:.2f} W")

            if not pm_ok:
                log(f"[GATE8][FAIL] PM power out of range [{low:.1f}, {high:.1f}]")
                pm.set_current(0)
                return False

            log("[GATE8] PM PASS")

            # 3) Ask RUP
            msg = can.Message(
                arbitration_id=CAN_TX_ID,
                data=[POWER_REPORT_REQUEST],
                is_extended_id=False
            )
            bus.send(msg)
            log("[GATE8] CAN TX → POWER_REPORT_REQUEST (0xA2)")

            rup_power, raw = _wait_for_power_report(bus)

            if rup_power is None:
                log("[GATE8][FAIL] No POWER_REPORT response from RUP")
                pm.set_current(0)
                return False

            log(f"[GATE8] RUP reports {rup_power} W (raw 0x{raw:02X})")

            if rup_power < p["expected_w"]:
                log("[GATE8][FAIL] RUP reported power below requested")
                pm.set_current(0)
                return False

            log("[GATE8] RUP PASS")

            pm.set_current(0)
            time.sleep(1)

        log("[GATE8] PASS — power reporting OK")
        return True

    finally:
        try:
            bus.shutdown()
        except Exception:
            pass
