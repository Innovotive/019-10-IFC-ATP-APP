import time

from tests.CAN.can_commands import read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins
from tests.ID.id_pins_mcp23s17 import IDPins  # <-- this must be the Slot4 GPB3/4/5 version

TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5

# Slot4: GPB3/4/5
PINS_TO_TEST = [3, 4, 5]

# Slot4 baseline config = 100 (ID3 ID2 ID1) = 0x04
# Clearing:
#  - GPB3 (ID1) -> still 100 (0x04)
#  - GPB4 (ID2) -> still 100 (0x04)
#  - GPB5 (ID3) -> 000 (0x00)
EXPECTED_AFTER_CLEAR = {
    3: 0x01,  # clear ID1
    4: 0x05,  # clear ID2
    5: 0x06,  # clear ID3
}

def run_gate5_id_check() -> bool:
    print("\n========== GATE 5 (ID PINS) — SLOT4 (GPB3/4/5) ==========")

    idpins = IDPins()

    try:
        print("[ID] Setting ID pins to Slot4 config (100) on GPB3/4/5")
        # If your class has set_100(), use it; otherwise set_mask(0b100)
        if hasattr(idpins, "set_100"):
            idpins.set_100()
        else:
            idpins.set_mask(0b100)

        time.sleep(SETTLE_DELAY_S)

        for pin in PINS_TO_TEST:
            expected_val = EXPECTED_AFTER_CLEAR.get(pin)

            print(f"\n[ID] Turning OFF GPB{pin}")
            idpins.clear_pin(pin)
            time.sleep(SETTLE_DELAY_S)

            flush_rx()
            read_id_pins_request()
            val = wait_for_idpins(TIMEOUT_S)

            if val is None:
                print(f"❌  GATE 5 FAIL: no CAN response after clearing GPB{pin}")
                return False

            print(f"🔎 ID report = 0x{val:02X}")

            if expected_val is not None and val != expected_val:
                print(
                    f"❌  GATE 5 FAIL: GPB{pin} → expected 0x{expected_val:02X}, "
                    f"got 0x{val:02X}"
                )
                return False

            print(f"✅ GPB{pin} verified")

            # restore pin HIGH
            idpins.set_pin(pin)
            time.sleep(SETTLE_DELAY_S)

        print("\n✅  GATE 5 PASS")
        return True

    finally:
        try:
            # restore Slot4 state (100)
            if hasattr(idpins, "set_100"):
                idpins.set_100()
            else:
                idpins.set_mask(0b100)
        except Exception:
            pass
        idpins.close()

if __name__ == "__main__":
    res = run_gate5_id_check()
    print("\nRESULT:", "PASS" if res else "FAIL")
