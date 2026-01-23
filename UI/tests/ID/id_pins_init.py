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

ID_MASK_A = 0b00111111  # A0..A5
ID_MASK_B = 0b00111111  # B0..B5

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


def _olat_reg(port: str) -> int:
    return OLATA if port == "A" else OLATB


# -----------------------------
# Slot -> pins mapping
# Each slot uses 3 pins in this order: [ID1, ID2, ID3]
# -----------------------------
SLOT_PINS = {
    1: ("A", [0, 1, 2]),   # Slot1 -> GPA0,GPA1,GPA2
    2: ("A", [3, 4, 5]),   # Slot2 -> GPA3,GPA4,GPA5
    3: ("B", [0, 1, 2]),   # Slot3 -> GPB0,GPB1,GPB2
    4: ("B", [3, 4, 5]),   # Slot4 -> GPB3,GPB4,GPB5
}


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


def _read_slot_bits_from_port_val(port_val: int, pins) -> str:
    id1 = (port_val >> pins[0]) & 1
    id2 = (port_val >> pins[1]) & 1
    id3 = (port_val >> pins[2]) & 1
    return f"{id3}{id2}{id1}"


def read_slot_bits(slot: int) -> str:
    """
    Return bits [ID3 ID2 ID1] for the given slot as string like '111'.
    """
    port, pins = SLOT_PINS[slot]
    v = read_reg(_olat_reg(port))
    return _read_slot_bits_from_port_val(v, pins)


def _apply_slot_pattern_to_port_val(port_val: int, pins, bits_id3_id2_id1: str) -> int:
    """
    Apply a 3-bit pattern (string 'ID3ID2ID1') to the 3 pins [ID1, ID2, ID3].
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
    if id1: port_val |= (1 << p_id1)
    if id2: port_val |= (1 << p_id2)
    if id3: port_val |= (1 << p_id3)

    return port_val & 0xFF


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

    This matches your working manual approach:
      - float everything HIGH first
      - then apply each slot pattern
      - write once per port
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

        # Write once per port (the “same time” behavior you want)
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


def init_id_pins_full_config(settle_s: float = 0.05) -> bool:
    """
    Your "full config" wrapper (all 4 slots).
    Put your final desired patterns here.
    """
    # Put YOUR FINAL TABLE here as bits "ID3ID2ID1"
    # Example from your comment/table:
    # Slot1 → 110 (ID3 shorted)
    # Slot2 → 101 (ID2 shorted)
    # Slot3 → 011 (ID1 shorted)
    # Slot4 → 100 (ID2 + ID3 shorted)
    slot_bits_map = {
        1: "110",
        2: "101",
        3: "011",
        4: "100",
    }
    return bool(set_all_slots_id_configs(slot_bits_map, settle_s=settle_s, verify=True))


def debug_dump_id_regs(tag: str = "") -> None:
    try:
        _ensure_spi_open()
        a = read_reg(OLATA)
        b = read_reg(OLATB)
        print(f"[ID_DUMP]{tag} OLATA=0b{a:08b} (0x{a:02X})  OLATB=0b{b:08b} (0x{b:02X})")
    except Exception as e:
        print(f"[ID_DUMP][ERR]{tag} {e}")
