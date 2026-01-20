# tests/ID/id_pins_init.py
import time
import spidev

# MCP23S17 opcodes (A2 A1 A0 = 000)
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

IODIRA = 0x00
IODIRB = 0x01
OLATA  = 0x14
OLATB  = 0x15

spi = spidev.SpiDev()
_initialized = False


def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value & 0xFF])


def read_reg(reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]


def _ensure_spi_open():
    global _initialized
    if not _initialized:
        spi.open(0, 0)                  # SPI bus 0, CE0
        spi.max_speed_hz = 10_000_000
        _initialized = True


# =========================================================
# INIT — INVERTED (TRANSISTOR LOGIC)
# =========================================================
def init_id_pins_active_low() -> bool:
    """
    TRANSISTOR-INVERTED LOGIC:

    GPIO LOW  = floating / NOT shorted
    GPIO HIGH = shorted

    Default state: ALL FLOATING (LOW)
    """
    try:
        _ensure_spi_open()

        # A0..A5 and B0..B5 outputs
        write_reg(IODIRA, 0b11000000)
        write_reg(IODIRB, 0b11000000)
        print("✔ MCP23S17: A0..A5 and B0..B5 configured as outputs")

        # Default ALL FLOATING → drive LOW
        write_reg(OLATA, 0b00000000)
        write_reg(OLATB, 0b00000000)
        print("✔ MCP23S17: Default ID lines set LOW (floating)")

        time.sleep(0.1)
        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False


# =========================================================
# SLOT PIN MAP
# =========================================================
SLOT_PINS = {
    1: ("A", [0, 1, 2]),   # RUP1: GPA0,GPA1,GPA2
    3: ("A", [3, 4, 5]),   # RUP3: GPA3,GPA4,GPA5
    2: ("B", [0, 1, 2]),   # RUP2: GPB0,GPB1,GPB2
    4: ("B", [3, 4, 5]),   # RUP4: GPB3,GPB4,GPB5
}

# Pins to SHORT per slot (logical intent)
SLOT_SHORT = {
    1: [0,1],
    3: [4],
    2: [0],
    4: [4, 5],
}


# =========================================================
# APPLY SLOT ID CONFIG — INVERTED
# =========================================================
def set_slot_id_config(slot: int, settle_s: float = 0.05) -> bool:
    """
    Apply ID-pin pattern for a given slot.

    INVERTED LOGIC:
      - GPIO LOW  = floating
      - GPIO HIGH = shorted
    """
    if slot not in SLOT_PINS:
        raise ValueError(f"Invalid slot: {slot}")

    try:
        _ensure_spi_open()
        init_id_pins_active_low()

        port, pins = SLOT_PINS[slot]
        shorts = SLOT_SHORT.get(slot, [])

        reg = OLATA if port == "A" else OLATB

        # Start from ALL FLOATING (LOW)
        current = read_reg(reg)
        new_val = current & ~0b00111111   # force A0..A5 or B0..B5 LOW

        # Drive SHORTED pins HIGH
        for p in shorts:
            new_val |= (1 << p)

        write_reg(reg, new_val)

        print(
            f"[ID_CFG] Slot{slot}: Port {port} | "
            f"floating={set(pins) - set(shorts)} | shorted={shorts}"
        )

        time.sleep(settle_s)
        return True

    except Exception as e:
        print(f"[ID_CFG][ERROR] Slot{slot}: {e}")
        return False
