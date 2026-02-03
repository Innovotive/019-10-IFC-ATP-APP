import time

from tests.CAN.can_commands import read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins
from tests.ID.id_pins_mcp23s17 import IDPins   # <-- Slot3 GPB0/1/2 version

TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5

# Slot3: GPB0, GPB1, GPB2
PINS_TO_TEST = [0, 1, 2]

# Slot3 baseline = 011 (ID3 ID2 ID1) = 0x03
EXPECTED_AFTER_CLEAR = {
    0: 0x02,  # clear ID1 (GPB0) -> 010
    1: 0x04,  # clear ID2 (GPB1) -> 001
    2: 0x06,  # clear ID3 (GPB2) -> still 011
}

def run_gate5_id_check() -> bool:
    print("\n========== GATE 5 (ID PINS) — SLOT 3 (GPB0/1/2) ==========")

    idpins = IDPins()

    try:
        print("[ID] Setting Slot3 ID configuration (011) on GPB0/1/2")
        # Use helper if present, otherwise raw mask
        if hasattr(idpins, "set_011"):
            idpins.set_011()
        else:
            idpins.set_mask(0b011)

        time.sleep(SETTLE_DELAY_S)

        for pin in PINS_TO_TEST:
            expected_val = EXPECTED_AFTER_CLEAR[pin]

            print(f"\n[ID] Turning OFF GPB{pin}")
            idpins.clear_pin(pin)
            time.sleep(SETTLE_DELAY_S)

            flush_rx()
            read_id_pins_request()

            val = wait_for_idpins(TIMEOUT_S)

            if val is None:
                print(f"❌ GATE 5 FAIL: no CAN response after clearing GPB{pin}")
                return False

            print(f"🔎 ID report = 0x{val:02X}")

            if val != expected_val:
                print(
                    f"❌ GATE 5 FAIL: GPB{pin} → expected 0x{expected_val:02X}, "
                    f"got 0x{val:02X}"
                )
                return False

            print(f"✅ GPB{pin} verified")

            # Restore pin
            idpins.set_pin(pin)
            time.sleep(SETTLE_DELAY_S)

        print("\n✅ GATE 5 PASS (Slot 3)")
        return True

    finally:
        try:
            # Restore Slot3 baseline
            if hasattr(idpins, "set_011"):
                idpins.set_011()
            else:
                idpins.set_mask(0b011)
        except Exception:
            pass
        idpins.close()

if __name__ == "__main__":
    res = run_gate5_id_check()
    print("\nRESULT:", "PASS" if res else "FAIL")
