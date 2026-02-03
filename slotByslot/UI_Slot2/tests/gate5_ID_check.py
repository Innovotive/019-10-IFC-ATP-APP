import time

from tests.CAN.can_commands import read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins
from tests.ID.id_pins_mcp23s17 import IDPins

TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5

# Now testing GPA3/4/5 instead of GPA0/1/2
PINS_TO_TEST = [3, 4, 5]

# If the CAN response is the 3-bit value (ID3 ID2 ID1),
# then when all ON = 111 (0x07)
# clearing:
#  - GPA3 (ID1) -> 110 (0x06)
#  - GPA4 (ID2) -> 101 (0x05)
#  - GPA5 (ID3) -> 011 (0x03)
EXPECTED_AFTER_CLEAR = {
    3: 0x03,  # clear ID1
    4: 0x05,  # clear ID2
    5: 0x06,  # clear ID3
}

def run_gate5_id_check() -> bool:
    print("\n========== GATE 5 (ID PINS) ==========")

    idpins = IDPins()

    try:
        print("[ID] Setting ALL ID pins ON (GPA3/4/5)")
        idpins.set_all_on()
        time.sleep(SETTLE_DELAY_S)

        for pin in PINS_TO_TEST:
            expected_val = EXPECTED_AFTER_CLEAR.get(pin)

            print(f"\n[ID] Turning OFF GPA{pin}")
            idpins.clear_pin(pin)
            time.sleep(SETTLE_DELAY_S)

            flush_rx()
            read_id_pins_request()

            val = wait_for_idpins(TIMEOUT_S)

            if val is None:
                print(f"❌  GATE 5 FAIL: no CAN response after clearing GPA{pin}")
                return False

            print(f"🔎 ID report = 0x{val:02X}")

            # If you’re unsure about the expected mapping, you can temporarily
            # comment this check and just observe values.
            if expected_val is not None and val != expected_val:
                print(
                    f"❌  GATE 5 FAIL: GPA{pin} → expected 0x{expected_val:02X}, "
                    f"got 0x{val:02X}"
                )
                return False

            print(f"✅ GPA{pin} verified")

            # restore pin
            idpins.set_pin(pin)
            time.sleep(SETTLE_DELAY_S)

        print("\n✅  GATE 5 PASS")
        return True

    finally:
        try:
            idpins.set_all_on()
        except Exception:
            pass
        idpins.close()

if __name__ == "__main__":
    res = run_gate5_id_check()
    print("\nRESULT:", "PASS" if res else "FAIL")
