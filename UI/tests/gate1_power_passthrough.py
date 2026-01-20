import time

from tests.power_PT.power_1_4 import (
    read_power_state_rup1,
    read_power_state_rup2,
    read_power_state_rup3,
    read_power_state_rup4,
)

def run_gate1_power_test(slot: int = 1) -> bool:
    """
    Gate1: Power pass-through / power detect check.

    IMPORTANT:
    - Does NOT control relays anymore.
    - The caller (QuickRunner/Main) is responsible for powering ON the desired RUP.
    """

    print(f"[GATE1] Starting power detect test for RUP{slot}")

    # Small settle time after relay ON (runner already waited too, but safe)
    time.sleep(0.2)

    if slot == 1:
        power_ok = read_power_state_rup1()
    elif slot == 2:
        power_ok = read_power_state_rup2()
    elif slot == 3:
        power_ok = read_power_state_rup3()
    elif slot == 4:
        power_ok = read_power_state_rup4()
    else:
        raise ValueError(f"Invalid slot: {slot}")

    print(f"[GATE1] RUP{slot} {'PASS' if power_ok else 'FAIL'}")
    return bool(power_ok)
