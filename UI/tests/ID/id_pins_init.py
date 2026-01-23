# tests/ID/id_pins_init.py
import time
import spidev

# MCP23S17 opcodes (A2 A1 A0 = 000)
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

# Registers (BANK=0)
IODIRA = 0x00
IODIRB = 0x01
OLATA  = 0x14
OLATB  = 0x15

# Only A0..A5 and B0..B5 are used for ID straps
ID_MASK_A = 0b00111111
ID_MASK_B = 0b00111111

spi = spidev.SpiDev()
_initialized = False


# =========================================================
# LOW-LEVEL SPI HELPERS
# =========================================================
def write_reg(reg: int, value: int) -> None:
    spi.xfer2([OPCODE_WRITE, reg, value & 0xFF])


def read_reg(reg: int) -> int:
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]


def _ensure_spi_open() -> None:
    global _initialized
    if not _initialized:
        spi.open(0, 0)  # SPI bus 0, CE0
        spi.max_speed_hz = 10_000_000
        _initialized = True


def _olat_reg(port: str) -> int:
    return OLATA if port == "A" else OLATB


# =========================================================
# SLOT -> PIN MAPPING
# Each slot uses 3 pins in this order: [ID1, ID2, ID3]
# =========================================================
SLOT_PINS = {
    1: ("A", [0, 1, 2]),   # Slot1 -> GPA0,GPA1,GPA2
    2: ("A", [3, 4, 5]),   # Slot2 -> GPA3,GPA4,GPA5
    3: ("B", [0, 1, 2]),   # Slot3 -> GPB0,GPB1,GPB2
    4: ("B", [3, 4, 5]),   # Slot4 -> GPB3,GPB4,GPB5
}


# =========================================================
# CORE INIT
# =========================================================
def init_id_pins_active_high() -> bool:
    """
    Configure MCP so that A0..A5 and B0..B5 are OUTPUTS.
    Active-high straps:
      1 = floated (not shorted)
      0 = shorted
    """
    try:
        _ensure_spi_open()

        # A0..A5 outputs, A6..A7 inputs
        write_reg(IODIRA, 0b11000000)
        # B0..B5 outputs, B6..B7 inputs
        write_reg(IODIRB, 0b11000000)

        return True
    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False


def float_all_ids(settle_s: float = 0.02) -> bool:
    """
    Force ALL ID pins (A0..A5 and B0..B5) HIGH without touching A6..A7 / B6..B7.
    """
    try:
        _ensure_spi_open()

        a = read_reg(OLATA)
        b = read_reg(OLATB)

        a = (a | ID_MASK_A) & 0xFF
        b = (b | ID_MASK_B) & 0xFF

        write_reg(OLATA, a)
        write_reg(OLATB, b)
        time.sleep(settle_s)
        return True
    except Exception as e:
        print(f"[ID_FLOAT][ERROR] {e}")
        return False


# =========================================================
# BIT/PATTERN HELPERS
# Pattern is always a string "ID3ID2ID1", e.g. "110"
# =========================================================
def _read_slot_bits_from_port_val(port_val: int, pins) -> str:
    id1 = (port_val >> pins[0]) & 1
    id2 = (port_val >> pins[1]) & 1
    id3 = (port_val >> pins[2]) & 1
    return f"{id3}{id2}{id1}"


def read_slot_bits(slot: int) -> str:
    """
    Return bits [ID3 ID2 ID1] for the given slot as a string like '111'.
    """
    port, pins = SLOT_PINS[slot]
    v = read_reg(_olat_reg(port))
    return _read_slot_bits_from_port_val(v, pins)


def _apply_slot_pattern_to_port_val(port_val: int, pins, bits_id3_id2_id1: str) -> int:
    """
    Apply a 3-bit pattern string (ID3ID2ID1) to the 3 pins [ID1, ID2, ID3].
    Only those 3 pins are modified.
    """
    if len(bits_id3_id2_id1) != 3 or any(c not in "01" for c in bits_id3_id2_id1):
        raise ValueError(f"Invalid bits '{bits_id3_id2_id1}', expected like '110'")

    id3 = int(bits_id3_id2_id1[0])
    id2 = int(bits_id3_id2_id1[1])
    id1 = int(bits_id3_id2_id1[2])

    p_id1, p_id2, p_id3 = pins

    # Clear the 3 pins first
    port_val &= ~(1 << p_id1)
    port_val &= ~(1 << p_id2)
    port_val &= ~(1 << p_id3)

    # Set according to pattern
    if id1:
        port_val |= (1 << p_id1)
    if id2:
        port_val |= (1 << p_id2)
    if id3:
        port_val |= (1 << p_id3)

    return port_val & 0xFF


# =========================================================
# SET ONE SLOT (WITHOUT TOUCHING OTHER SLOTS)
# =========================================================
def set_slot_bits(slot: int, bits_id3_id2_id1: str, settle_s: float = 0.05, verify: bool = True) -> bool:
    """
    Set ONLY one slot's 3 pins (ID1/ID2/ID3) without touching other slots.
    bits_id3_id2_id1 is a string like "110" meaning (ID3 ID2 ID1).
    """
    try:
        _ensure_spi_open()
        if slot not in SLOT_PINS:
            raise ValueError(f"Invalid slot: {slot}")

        port, pins = SLOT_PINS[slot]
        reg = _olat_reg(port)
        v = read_reg(reg)

        # Force that slot's pins HIGH first (safe)
        for p in pins:
            v |= (1 << p)

        # Apply requested pattern to just those 3 pins
        v = _apply_slot_pattern_to_port_val(v, pins, bits_id3_id2_id1)

        write_reg(reg, v)
        time.sleep(settle_s)

        if verify:
            rb = read_reg(reg)
            got = _read_slot_bits_from_port_val(rb, pins)
            if got != bits_id3_id2_id1:
                raise RuntimeError(f"Verify failed slot{slot}: want={bits_id3_id2_id1} got={got}")

        return True

    except Exception as e:
        print(f"[ID_SLOT][ERROR] slot={slot}: {e}")
        return False


# =========================================================
# SET ALL SLOTS (ONE WRITE PER PORT)
# =========================================================
def set_all_slots_id_configs(
    slot_bits_map: dict,
    settle_s: float = 0.05,
    verify: bool = True
) -> bool:
    """
    Set ID pins for ALL 4 slots in one shot (one write to OLATA + one write to OLATB).

    slot_bits_map format:
        {
          1: "110",  # (ID3 ID2 ID1)
          2: "101",
          3: "011",
          4: "100",
        }

    Steps:
      - init outputs
      - float all IDs HIGH
      - compute final OLATA/OLATB with all 4 slot patterns
      - write once per port
      - optional verify
    """
    try:
        _ensure_spi_open()
        if not init_id_pins_active_high():
            return False

        # Start from current OLAT values, but force ID pins HIGH (safe float)
        a = read_reg(OLATA)
        b = read_reg(OLATB)
        a = (a | ID_MASK_A) & 0xFF
        b = (b | ID_MASK_B) & 0xFF

        # Apply patterns for each slot to the correct port value
        for slot in (1, 2, 3, 4):
            if slot not in slot_bits_map:
                raise ValueError(f"slot_bits_map missing slot {slot}")

            bits = slot_bits_map[slot]
            port, pins = SLOT_PINS[slot]
            if port == "A":
                a = _apply_slot_pattern_to_port_val(a, pins, bits)
            else:
                b = _apply_slot_pattern_to_port_val(b, pins, bits)

        # Write once per port
        write_reg(OLATA, a)
        write_reg(OLATB, b)
        time.sleep(settle_s)

        if verify:
            ra = read_reg(OLATA)
            rb = read_reg(OLATB)
            for slot in (1, 2, 3, 4):
                want = slot_bits_map[slot]
                port, pins = SLOT_PINS[slot]
                got = _read_slot_bits_from_port_val(ra if port == "A" else rb, pins)
                if got != want:
                    raise RuntimeError(f"Verify failed slot{slot}: want={want} got={got}")

        print(f"[ID_ALL] OLATA=0b{a:08b} (0x{a:02X})  OLATB=0b{b:08b} (0x{b:02X})")
        for s in (1, 2, 3, 4):
            print(f"[ID_ALL] Slot{s} -> {read_slot_bits(s)}")

        return True

    except Exception as e:
        print(f"[ID_ALL][ERROR] {e}")
        return False


# =========================================================
# YOUR DEFAULT "FINAL" CONFIG WRAPPER
# =========================================================
def init_id_pins_full_config(settle_s: float = 0.05) -> bool:
    """
    One-call helper:
      - init outputs
      - apply your FINAL per-slot ID configuration (all 4 slots)

    IMPORTANT: bits are "ID3ID2ID1"
    """
    slot_bits_map = {
        1: "110",
        2: "101",
        3: "011",
        4: "100",
    }
    return bool(set_all_slots_id_configs(slot_bits_map, settle_s=settle_s, verify=True))


# =========================================================
# DEBUG
# =========================================================
def debug_dump_id_regs(tag: str = "") -> None:
    try:
        _ensure_spi_open()
        a = read_reg(OLATA)
        b = read_reg(OLATB)
        print(f"[ID_DUMP]{tag} OLATA=0b{a:08b} (0x{a:02X})  OLATB=0b{b:08b} (0x{b:02X})")
    except Exception as e:
        print(f"[ID_DUMP][ERR]{tag} {e}")
