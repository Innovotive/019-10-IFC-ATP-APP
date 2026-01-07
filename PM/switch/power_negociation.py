# power_negociation.py
import time

WAIT = 5
POWER_TOL = 0.40   # ±40% tolerance

GATE7_POINTS = [
    {"pdo_index": 4, "voltage_mv": 20000, "current_ma": 2990, "power_w": 60},
    {"pdo_index": 3, "voltage_mv": 15000, "current_ma": 3000, "power_w": 45},
    {"pdo_index": 2, "voltage_mv": 12000, "current_ma": 3000, "power_w": 36},
    {"pdo_index": 1, "voltage_mv": 9000,  "current_ma": 3000, "power_w": 27},
    {"pdo_index": 0, "voltage_mv": 5000,  "current_ma": 3000, "power_w": 15},
]


def check_power_pass(measured_w, expected_w):
    low = expected_w * (1 - POWER_TOL)
    high = expected_w * (1 + POWER_TOL)
    return low <= measured_w <= high, low, high


def run_gate7(pm) -> bool:
    print("\n=======================================")
    print("         GATE 7 — PD LOAD TEST          ")
    print("=======================================\n")

    overall_pass = True

    for point in GATE7_POINTS:
        idx = point["pdo_index"]
        v_mv = point["voltage_mv"]
        i_ma = point["current_ma"]
        expected_w = point["power_w"]

        print("\n--------------------------------------------")
        print(f"Testing {v_mv/1000:.1f} V @ {i_ma/1000:.3f} A (expected {expected_w} W)")
        print("--------------------------------------------")

        pm.set_voltage(idx, v_mv)
        time.sleep(WAIT)

        print("CONSTAT:", pm.get_connection_status())

        print(f"Applying load: {i_ma} mA")
        pm.set_current(i_ma)
        time.sleep(WAIT)

        stat = pm.get_statistics()
        print("STAT:", stat)

        meas_v = stat["voltage_mv"]
        meas_i = stat["current_ma"]
        measured_w = (meas_v * meas_i) / 1_000_000.0

        passed, low, high = check_power_pass(measured_w, expected_w)

        if passed:
            print(f"✔ PASS — {measured_w:.2f} W inside [{low:.2f}, {high:.2f}]")
        else:
            print(f"❌ FAIL — {measured_w:.2f} W outside [{low:.2f}, {high:.2f}]")
            overall_pass = False

        pm.set_current(0)
        time.sleep(WAIT)

    print("\n=======================================")
    print("         GATE 7 COMPLETE                ")
    print("=======================================\n")

    return overall_pass


__all__ = ["run_gate7"]
