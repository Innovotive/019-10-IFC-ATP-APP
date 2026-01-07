import time
from power_PT.relay import relay_on
from power_PT.power import read_power_state

def run_gate1_power_test(rup_id: int) -> bool:
    """
    Gate 1:
    - Turn ON relay
    - Keep it ON
    - Check power pass-through
    """

    # ✅ TURN ON RUP POWER
    relay_on()

    # Allow voltage to stabilize
    time.sleep(10)

    # ✅ Read voltage divider
    power_ok = read_power_state(timeout=1.0)

    # ❌ DO NOT turn relay off here
    return power_ok
