"""
import time
import spidev

from tests.CAN.can_commands import read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins

# =========================================================
# CONFIG
# =========================================================
TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5   # important for RUP firmware timing

# =========================================================
# MCP23S17 SPI CONFIG (PORT B)
# =========================================================
OPCODE_WRITE = 0x40   # A2 A1 A0 = 000
OPCODE_READ  = 0x41

IODIRB = 0x01
OLATB  = 0x15

SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED_HZ = 10_000_000

# We only want to drive GPB3, GPB4, GPB5 as outputs.
# IODIR bit: 0=output, 1=input
# 0b11000111 => B0,B1,B2 inputs, B3,B4,B5 outputs, B6,B7 inputs
IODIRB_VALUE = 0b11000111

# Mask for "all ON" on GPB3/4/5
ALL_ON_MASK_B3_B5 = 0b00111000  # bits 3,4,5 = 1

# ---------------------------------------------------------
# Expected CAN values (OPTIONAL)
# ---------------------------------------------------------
# Fill these once you confirm what the RUP reports for each cleared pin.
# Keys are MCP23S17 pin numbers on PORT B.
#
# Example (PLACEHOLDER - you must confirm):
# EXPECTED_AFTER_CLEAR_B = {
#     3: 0x??,
#     4: 0x??,
#     5: 0x??,
# }
EXPECTED_AFTER_CLEAR_B = {}


# =========================================================
# MCP23S17 HELPERS
# =========================================================
def _write_reg(spi, reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value & 0xFF])

def _read_reg(spi, reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

def set_all(spi, mask):
    _write_reg(spi, OLATB, mask)

def clear_pin(spi, pin):
    val = _read_reg(spi, OLATB)
    _write_reg(spi, OLATB, val & ~(1 << pin))

def set_pin(spi, pin):
    val = _read_reg(spi, OLATB)
    _write_reg(spi, OLATB, val | (1 << pin))


# =========================================================
# GATE 6 – ID PINS CHECK (PORT B: GPB3/4/5)
# =========================================================
def gate6_id_check() -> bool:
    print("\n========== GATE 6 (ID PINS via MCP23S17 PORT B) ==========")

    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEV)
    spi.max_speed_hz = SPI_SPEED_HZ

    try:
        # -------------------------------------------------
        # Configure GPB3/4/5 as outputs
        # -------------------------------------------------
        _write_reg(spi, IODIRB, IODIRB_VALUE)
        print("✔ GPB3, GPB4, GPB5 configured as outputs")

        # -------------------------------------------------
        # Start from ALL ON baseline
        # -------------------------------------------------
        print("[ID] Setting ALL (GPB3/4/5) ON")
        set_all(spi, ALL_ON_MASK_B3_B5)
        time.sleep(SETTLE_DELAY_S)

        # -------------------------------------------------
        # Clear each pin one by one: 3, 4, 5
        # -------------------------------------------------
        for pin in (3, 4, 5):
            print(f"\n[ID] Turning OFF GPB{pin}")
            clear_pin(spi, pin)
            time.sleep(SETTLE_DELAY_S)

            flush_rx()
            read_id_pins_request()

            val = wait_for_idpins(TIMEOUT_S)

            if val is None:
                print(f"❌ GATE 6 FAIL: no CAN response after clearing GPB{pin}")
                return False

            print(f"🔎 ID report = 0x{val:02X}")

            # Optional strict check if you provided expected values
            if pin in EXPECTED_AFTER_CLEAR_B:
                expected_val = EXPECTED_AFTER_CLEAR_B[pin]
                if val != expected_val:
                    print(
                        f"❌ GATE 6 FAIL: GPB{pin} → expected 0x{expected_val:02X}, got 0x{val:02X}"
                    )
                    return False
                print(f"✅ GPB{pin} verified (matched expected)")

            else:
                print(f"✅ GPB{pin} got a valid response (expected not set yet)")

            # Restore pin before next test
            set_pin(spi, pin)
            time.sleep(SETTLE_DELAY_S)

        print("\n✅ GATE 6 PASS")
        return True

    finally:
        # Leave outputs in known state + release SPI
        try:
            set_all(spi, ALL_ON_MASK_B3_B5)
        except Exception:
            pass
        try:
            spi.close()
        except Exception:
            pass


# =========================================================
# OLD VERSION (GPA0/1/2) — KEPT BUT COMMENTED OUT
# =========================================================
"""
import time

from tests.CAN.can_commands import read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins
from tests.ID.id_pins_mcp23s17 import IDPins

TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5

EXPECTED_AFTER_CLEAR = {
    0: 0x04,
    1: 0x02,
    2: 0x01,
}

def gate6_id_check() -> bool:
    print("\\n========== GATE 6 ==========")

    idpins = IDPins()

    try:
        print("[ID] Setting ALL ID pins ON")
        idpins.set_all_on()
        time.sleep(SETTLE_DELAY_S)

        for pin, expected_val in EXPECTED_AFTER_CLEAR.items():
            print(f"\\n[ID] Turning OFF GPA{pin}")
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

            idpins.set_pin(pin)
            time.sleep(SETTLE_DELAY_S)

        print("\\n✅ GATE 6 PASS")
        return True

    finally:
        try:
            idpins.set_all_on()
        except Exception:
            pass
        idpins.close()



if __name__ == "__main__":
    res = gate6_id_check()
    print("\nRESULT:", "PASS" if res else "FAIL")
