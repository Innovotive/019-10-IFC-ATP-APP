import time

from tests.CAN.can_commands import read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins
from tests.ID.id_pins_mcp23s17 import IDPins

# =========================================================
# CONFIG
# =========================================================
TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5   # important for RUP firmware timing

# Expected CAN values after clearing ONE pin from ALL ON (111)
EXPECTED_AFTER_CLEAR = {
    0: 0x04,  # GPA0 OFF → ID3 open → ID2+ID1 shorted
    1: 0x02,  # GPA1 OFF → ID2 open → ID3+ID1 shorted
    2: 0x01,  # GPA2 OFF → ID1 open → ID3+ID2 shorted
}

def gate6_id_check() -> bool:
    print("\n========== GATE 6 ==========")

    idpins = IDPins()

    try:
        # -------------------------------------------------
        # Start from ALL ON (known baseline)
        # -------------------------------------------------
        print("[ID] Setting ALL ID pins ON")
        idpins.set_all_on()
        time.sleep(SETTLE_DELAY_S)

        # -------------------------------------------------
        # Clear each pin one by one
        # -------------------------------------------------
        for pin, expected_val in EXPECTED_AFTER_CLEAR.items():
            print(f"\n[ID] Turning OFF GPA{pin}")
            idpins.clear_pin(pin)
            time.sleep(SETTLE_DELAY_S)

            flush_rx()
            read_id_pins_request()

            val = wait_for_idpins(TIMEOUT_S)

            if val is None:
                print(f"❌ GATE 6 FAIL: no CAN response after clearing GPA{pin}")
                return False

            print(f"🔎 ID report = 0x{val:02X}")

            if val != expected_val:
                print(
                    f"❌ GATE 6 FAIL: GPA{pin} → expected 0x{expected_val:02X}, "
                    f"got 0x{val:02X}"
                )
                return False

            print(f"✅ GPA{pin} verified")

            # Restore pin before next test
            idpins.set_pin(pin)
            time.sleep(SETTLE_DELAY_S)

        print("\n✅ GATE 6 PASS")
        return True

    finally:
        # Leave system in known state + release SPI
        try:
            idpins.set_all_on()
        except Exception:
            pass
        idpins.close()


if __name__ == "__main__":
    res = gate6_id_check()
    print("\nRESULT:", "PASS" if res else "FAIL")
