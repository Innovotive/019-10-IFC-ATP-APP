from pm125 import PM125
import time

WAIT = 5             # seconds
POWER_TOL = 0.20     # ±20% tolerance for power validation

# KEEP EXACTLY AS USER WANTS — DO NOT MODIFY
GATE7_POINTS = [
    {"pdo_index": 4, "voltage_mv": 20000, "current_ma": 2990, "power_w": 60},  # 20V
    {"pdo_index": 3, "voltage_mv": 15000, "current_ma": 3000, "power_w": 45},  # 15V
    {"pdo_index": 2, "voltage_mv": 12000, "current_ma": 3000, "power_w": 36},  # 12V
    {"pdo_index": 1, "voltage_mv": 9000,  "current_ma": 3000, "power_w": 27},  # 9V
    {"pdo_index": 0, "voltage_mv": 5000,  "current_ma": 3000, "power_w": 15},  # 5V
]

def check_power_pass(measured_w, expected_w):
    low = expected_w * (1 - POWER_TOL)
    high = expected_w * (1 + POWER_TOL)
    return low <= measured_w <= high, low, high


# =========================================================
# GATE 8 — OVERCURRENT TEST (5V → 3A → 3.5A)
# =========================================================
def run_gate8_ocp(pm):
    print("\n=======================================")
    print("     GATE 8 — OVERCURRENT TEST (5V)")
    print("=======================================\n")

    # 1) NEGOTIATE 5V
    print("Setting 5V...")
    pm.set_voltage(0, 5000)
    time.sleep(WAIT)

    print("CONSTAT:", pm.get_connection_status())
    print("STAT:", pm.get_statistics())

    # 2) APPLY BASE LOAD (3A)
    print("\nApplying normal load: 3000 mA (3A)...")
    pm.set_current(3000)
    time.sleep(WAIT)

    stat = pm.get_statistics()
    print("STAT after 3A load:", stat)

    # 3) APPLY OVERCURRENT (3.5A)
    print("\n⚠️ Applying OVERCURRENT: 3500 mA (3.5A)")
    pm.set_current(3500)
    time.sleep(WAIT)

    oc_stat = pm.get_statistics()
    print("STAT after 3.5A overcurrent:", oc_stat)

    volt = oc_stat["voltage_mv"]
    curr = oc_stat["current_ma"]

    print("\n--------------------------------------")
    if curr < 2000 or volt < 4000:
        print("✔ PASS — OCP Triggered (foldback or shutdown detected)")
    else:
        print("❌ FAIL — No OCP detected")
    print("--------------------------------------")

    # 4) RESET PM125
    print("\nResetting PM125 to 5V @ 0mA...")
    pm.set_voltage(0, 5000)
    time.sleep(2)
    pm.set_current(0)
    time.sleep(3)

    print("Final STAT:", pm.get_statistics())
    print("Gate 8 completed.\n")


# =========================================================
# MAIN — GATE 7 AND GATE 8
# =========================================================

with PM125("/dev/ttyUSB0") as pm:

    print("\n=======================================")
    print("         GATE 7 — PD LOAD TEST")
    print("=======================================\n")

    for point in GATE7_POINTS:
        idx = point["pdo_index"]
        v_mv = point["voltage_mv"]
        i_ma = point["current_ma"]
        expected_w = point["power_w"]

        print("\n--------------------------------------------")
        print(f"Testing {v_mv/1000:.1f} V @ {i_ma/1000:.3f} A (expected {expected_w} W)")
        print("--------------------------------------------")

        # NEGOTIATE VOLTAGE
        pm.set_voltage(idx, v_mv)
        time.sleep(WAIT)
        print("CONSTAT:", pm.get_connection_status())

        # APPLY LOAD
        print(f"Applying load: {i_ma} mA")
        pm.set_current(i_ma)
        time.sleep(WAIT)

        stat = pm.get_statistics()
        print("STAT:", stat)

        meas_v = stat["voltage_mv"]
        meas_i = stat["current_ma"]

        measured_w = (meas_v * meas_i) / 1_000_000.0
        print(f"Measured Power: {measured_w:.2f} W")

        # PASS / FAIL CHECK
        passed, low, high = check_power_pass(measured_w, expected_w)
        if passed:
            print(f"✔ PASS — {measured_w:.2f} W inside [{low:.2f}, {high:.2f}]")
        else:
            print(f"❌ FAIL — {measured_w:.2f} W NOT inside [{low:.2f}, {high:.2f}]")

        # RESET LOAD
        pm.set_current(0)
        time.sleep(WAIT)

    print("\n=======================================")
    print("         GATE 7 COMPLETE")
    print("=======================================\n")

    # =========================================================
    # RUN GATE 8 — Over-Current Protection
    # =========================================================
    run_gate8_ocp(pm)
