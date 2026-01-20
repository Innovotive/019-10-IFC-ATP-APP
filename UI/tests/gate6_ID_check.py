import time
import spidev

from tests.CAN.can_commands import set_target_slot, read_id_pins_request
from tests.CAN.can_utils import flush_rx, wait_for_idpins

# =========================================================
# CONFIG
# =========================================================
TIMEOUT_S = 2.0
SETTLE_DELAY_S = 0.5

# =========================================================
# MCP23S17 SPI CONFIG
# =========================================================
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

IODIRA = 0x00
IODIRB = 0x01
OLATA  = 0x14
OLATB  = 0x15

SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED_HZ = 10_000_000

# =========================================================
# SLOT → MCP23S17 PIN MAP
# =========================================================
SLOT_ID_PINS = {
    1: ("A", [0, 1, 2]),
    2: ("A", [3, 4, 5]),
    3: ("B", [0, 1, 2]),
    4: ("B", [3, 4, 5]),
}

# =========================================================
# MCP23S17 HELPERS
# =========================================================
def _write_reg(spi, reg, val):
    spi.xfer2([OPCODE_WRITE, reg, val & 0xFF])

def _read_reg(spi, reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

def _set_all(spi, reg, pins):
    val = _read_reg(spi, reg)
    for p in pins:
        val |= (1 << p)
    _write_reg(spi, reg, val)

def _clear_pin(spi, reg, pin):
    val = _read_reg(spi, reg)
    _write_reg(spi, reg, val & ~(1 << pin))

def _set_pin(spi, reg, pin):
    val = _read_reg(spi, reg)
    _write_reg(spi, reg, val | (1 << pin))


# =========================================================
# GATE 6 – ID PINS TEST (FINAL, SLOT-AWARE)
# =========================================================
def gate6_id_check(slot: int, log_cb=None) -> bool:
    def log(msg):
        log_cb(msg) if log_cb else print(msg)

    if slot not in SLOT_ID_PINS:
        raise ValueError(f"[GATE6] Invalid slot={slot}")

    port, pins = SLOT_ID_PINS[slot]
    log(f"\n========== GATE 6 — Slot {slot} (PORT {port}) ==========")

    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEV)
    spi.max_speed_hz = SPI_SPEED_HZ

    try:
        # Ensure CAN targets correct RUP
        set_target_slot(slot)

        if port == "A":
            IODIR = IODIRA
            OLAT = OLATA
            _write_reg(spi, IODIR, 0xFF & ~(sum(1 << p for p in pins)))
        else:
            IODIR = IODIRB
            OLAT = OLATB
            _write_reg(spi, IODIR, 0xFF & ~(sum(1 << p for p in pins)))

        log(f"[GATE6] Configured PORT {port} pins {pins} as outputs")

        # -------------------------------------------------
        # Baseline: ALL ON
        # -------------------------------------------------
        log("[GATE6] Setting ALL ID pins ON")
        _set_all(spi, OLAT, pins)
        time.sleep(SETTLE_DELAY_S)

        # -------------------------------------------------
        # Clear pins one by one
        # -------------------------------------------------
        for pin in pins:
            log(f"[GATE6] Clearing ID pin {port}{pin}")
            _clear_pin(spi, OLAT, pin)
            time.sleep(SETTLE_DELAY_S)

            flush_rx()
            set_target_slot(slot)
            read_id_pins_request()

            val = wait_for_idpins(TIMEOUT_S)
            if val is None:
                log(f"❌ [GATE6] No CAN response after clearing {port}{pin}")
                return False

            log(f"🔎 [GATE6] ID response = 0x{val:02X}")

            _set_pin(spi, OLAT, pin)
            time.sleep(SETTLE_DELAY_S)

        log("✅ [GATE6] PASS")
        return True

    finally:
        try:
            _set_all(spi, OLAT, pins)
        except Exception:
            pass
        spi.close()


# if __name__ == "__main__":
#     print("RESULT:", "PASS" if gate6_id_check(1) else "FAIL")
