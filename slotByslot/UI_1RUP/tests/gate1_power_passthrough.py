
import time
from tests.power_PT.relay import relay_on
from tests.power_PT.power import read_power_state


def run_gate1_power_test() -> bool:

    print("[GATE1] Starting power pass-through test for RUP1")

    # 1) Relay ON
    relay_on()

    # 2) Let power stabilize
    time.sleep(0.5)

    # 3) Read power detect GPIO
    power_ok = read_power_state()

    print(f"[GATE1] RUP1 {'PASS' if power_ok else 'FAIL'}")

    return power_ok


