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


def write_reg(reg, value: int):
    spi.xfer2([OPCODE_WRITE, reg, value & 0xFF])


def read_reg(reg) -> int:
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]


def _ensure_spi_open():
    global _initialized
    if not _initialized:
        spi.open(0, 0)                 # SPI bus 0, CE0
        spi.max_speed_hz = 10_000_000
        _initialized = True


# -----------------------------
# Slot -> pins mapping (ABSOLUTE pins on each port)
# Each slot uses 3 pins in this order: [ID1, ID2, ID3]
# -----------------------------
SLOT_PINS = {
    1: ("A", [0, 1, 2]),   # Slot1 -> GPA0,GPA1,GPA2
    2: ("A", [3, 4, 5]),   # Slot2 -> GPA3,GPA4,GPA5
    3: ("B", [0, 1, 2]),   # Slot3 -> GPB0,GPB1,GPB2
    4: ("B", [3, 4, 5]),   # Slot4 -> GPB3,GPB4,GPB5
}

# -----------------------------
# YOUR REAL WORKING PATTERNS (from manual scripts)
# These are ABSOLUTE bit positions on the port (A or B).
# -----------------------------
SLOT_TO_SHORTS_ABS = {
    1: (0, 1),   # Slot1: pull A0, A1 LOW
    2: (3, 5),   # Slot2: pull A3, A5 LOW
    3: (1, 2),   # Slot3: pull B1, B2 LOW
    4: (3,),     # Slot4: pull B3 LOW  (comma matters!)
}


def init_id_pins_active_high() -> bool:
    """
    Configure MCP so that A0..A5 and B0..B5 are OUTPUTS and default HIGH.
    (Active-high logic: HIGH = not shorted, LOW = shorted)
    """
    try:
        _ensure_spi_open()

        # A0..A5 outputs, A6..A7 inputs
        write_reg(IODIRA, 0b11000000)
        # B0..B5 outputs, B6..B7 inputs
        write_reg(IODIRB, 0b11000000)

        # Default all ID lines HIGH (only touch bits 0..5)
        write_reg(OLATA, read_reg(OLATA) | 0b00111111)
        write_reg(OLATB, read_reg(OLATB) | 0b00111111)

        time.sleep(0.05)
        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False


def _get_olat_reg(port: str) -> int:
    return OLATA if port == "A" else OLATB


def read_slot_bits(slot: int) -> str:
    """
    Return bits [ID3 ID2 ID1] for the given slot as string like '111'.
    ID1 is the first pin in SLOT_PINS[slot], ID2 second, ID3 third.
    """
    port, pins = SLOT_PINS[slot]
    reg = _get_olat_reg(port)
    v = read_reg(reg)

    id1 = (v >> pins[0]) & 1
    id2 = (v >> pins[1]) & 1
    id3 = (v >> pins[2]) & 1
    return f"{id3}{id2}{id1}"


def set_slot_id_config(slot: int, settle_s: float = 0.05) -> bool:
    """
    Apply ID-pin pattern for a slot using ABSOLUTE pin shorts per port
    (matches your manual scripts exactly).

    Behavior:
      - Ensure MCP is initialized
      - Force ALL A0..A5 and B0..B5 HIGH (safe default)
      - Then drive only the pins listed in SLOT_TO_SHORTS_ABS[slot] LOW
        on the appropriate port.
    """
    if slot not in SLOT_PINS:
        raise ValueError(f"Invalid slot: {slot}")

    try:
        _ensure_spi_open()
        init_id_pins_active_high()

        port, _slot_pins = SLOT_PINS[slot]
        shorts_abs = SLOT_TO_SHORTS_ABS.get(slot, ())

        # Validate shorts are ABS pins 0..5
        for p in shorts_abs:
            if p not in (0, 1, 2, 3, 4, 5):
                raise ValueError(f"SLOT_TO_SHORTS_ABS[{slot}] invalid pin {p} (must be 0..5)")

        reg = _get_olat_reg(port)
        v = read_reg(reg)

        # Force bits 0..5 HIGH on this port first
        v |= 0b00111111

        # Drive selected ABS pins LOW
        for p in shorts_abs:
            v &= ~(1 << p)

        write_reg(reg, v)
        time.sleep(settle_s)

        print(f"[ID_CFG] Slot{slot}: port={port} shorts_abs={list(shorts_abs)} -> now={read_slot_bits(slot)}")
        return True

    except Exception as e:
        print(f"[ID_CFG][ERROR] Slot{slot}: {e}")
        return False


def init_id_pins_full_config(settle_s: float = 0.05) -> bool:
    """
    Wrapper:
      1) init MCP outputs
      2) apply per-slot config for all slots (not just all-high)
    """
    ok = bool(init_id_pins_active_high())
    for s in (1, 2, 3, 4):
        ok &= bool(set_slot_id_config(s, settle_s=settle_s))
    return bool(ok)


def debug_dump_id_regs(tag: str = "") -> None:
    try:
        _ensure_spi_open()
        a = read_reg(OLATA)
        b = read_reg(OLATB)
        print(f"[ID_DUMP]{tag} OLATA=0b{a:08b} (0x{a:02X})  OLATB=0b{b:08b} (0x{b:02X})")
    except Exception as e:
        print(f"[ID_DUMP][ERR]{tag} {e}")
