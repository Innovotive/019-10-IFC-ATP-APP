# tests/ID/id_pins_init.py
import time
import spidev
from typing import Dict

# =========================================================
# MCP23S17 REGISTERS (BANK=0)
# =========================================================
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

IODIRA = 0x00
IODIRB = 0x01

GPIOA  = 0x12
GPIOB  = 0x13

OLATA  = 0x14
OLATB  = 0x15

# Only A0..A5 and B0..B5 are used for ID straps
ID_MASK_A = 0b00111111  # A0..A5
ID_MASK_B = 0b00111111  # B0..B5

SPI_BUS = 0
SPI_DEV = 0

# ✅ Match your working script (safer/slower)
SPI_SPEED_HZ = 500_000

spi = spidev.SpiDev()
_initialized = False


# =========================================================
# SLOT -> PIN MAPPING
# Each slot uses 3 pins in this order: (ID1, ID2, ID3)
# =========================================================
SLOTS = {
    1: ("A", (0, 1, 2)),
    2: ("A", (3, 4, 5)),
    3: ("B", (0, 1, 2)),
    4: ("B", (3, 4, 5)),
}


# =========================================================
# LOW-LEVEL SPI HELPERS
# =========================================================
def _ensure_spi_open() -> None:
    global _initialized
    if not _initialized:
        spi.open(SPI_BUS, SPI_DEV)
        spi.max_speed_hz = SPI_SPEED_HZ
        _initialized = True


def write_reg(reg: int, val: int) -> None:
    _ensure_spi_open()
    spi.xfer2([OPCODE_WRITE, reg, val & 0xFF])


def read_reg(reg: int) -> int:
    _ensure_spi_open()
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]


def _olat_reg(port: str) -> int:
    return OLATA if port == "A" else OLATB


def _gpio_reg(port: str) -> int:
    return GPIOA if port == "A" else GPIOB


# =========================================================
# INIT OUTPUTS
# =========================================================
def init_id_pins_active_high() -> bool:
    """
    Configure MCP so that A0..A5 and B0..B5 are OUTPUTS.
    Active-high straps:
      1 = floated (HIGH)
      0 = shorted (LOW)
    """
    try:
        _ensure_spi_open()
        write_reg(IODIRA, 0b11000000)  # A0..A5 outputs, A6..A7 inputs
        write_reg(IODIRB, 0b11000000)  # B0..B5 outputs, B6..B7 inputs
        return True
    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False


def float_all_ids(settle_s: float = 0.02) -> bool:
    """
    Force ALL ID pins HIGH (A0..A5, B0..B5) without touching A6..A7 / B6..B7.
    """
    try:
        _ensure_spi_open()

        a = read_reg(OLATA) & 0xFF
        b = read_reg(OLATB) & 0xFF

        write_reg(OLATA, (a | ID_MASK_A) & 0xFF)
        write_reg(OLATB, (b | ID_MASK_B) & 0xFF)
        time.sleep(settle_s)
        return True
    except Exception as e:
        print(f"[ID_FLOAT][ERROR] {e}")
        return False


# =========================================================
# BIT MAPPING (MATCHES WORKING SCRIPT)
# mask3 is (ID1 ID2 ID3):
#   0b110 => ID1=1, ID2=1, ID3=0
# =========================================================
def _mask_to_bits(pins, mask3: int) -> int:
    """
    pins = (ID1_pin, ID2_pin, ID3_pin)
    mask3 bits are written as ID1 ID2 ID3 (MSB..LSB)
    """
    p0, p1, p2 = pins  # (ID1, ID2, ID3)
    out = 0
    if mask3 & 0b100:
        out |= (1 << p0)  # MSB -> ID1
    if mask3 & 0b010:
        out |= (1 << p1)  # mid -> ID2
    if mask3 & 0b001:
        out |= (1 << p2)  # LSB -> ID3
    return out & 0xFF


def _slot_bits_mask(pins) -> int:
    return (sum(1 << p for p in pins) & 0xFF)


# =========================================================
# SET ONE SLOT (ONLY CHANGES THAT SLOT'S 3 PINS)
# =========================================================
def set_slot_bits(slot: int, mask3: int, settle_s: float = 0.02, verify: bool = True) -> bool:
    """
    Set one slot to mask3 (ID1 ID2 ID3), e.g. 0b110.

    This matches your working script:
      - only updates those 3 pins
      - keeps other pins unchanged
      - verify using OLAT; if mismatch, also show GPIO read
    """
    try:
        _ensure_spi_open()
        if slot not in SLOTS:
            raise ValueError(f"Invalid slot: {slot}")

        port, pins = SLOTS[slot]
        allowed = ID_MASK_A if port == "A" else ID_MASK_B

        slot_bits = _slot_bits_mask(pins)
        want_on = _mask_to_bits(pins, int(mask3)) & slot_bits

        current = read_reg(_olat_reg(port)) & 0xFF

        # only change those 3 pins
        new_val = (current & ~slot_bits) | want_on
        new_val &= 0xFF

        # safety: keep non-allowed bits unchanged
        new_val = (current & ~allowed) | (new_val & allowed)
        new_val &= 0xFF

        write_reg(_olat_reg(port), new_val)
        time.sleep(settle_s)

        if verify:
            rb_olat = read_reg(_olat_reg(port)) & slot_bits
            if rb_olat != want_on:
                rb_gpio = read_reg(_gpio_reg(port)) & slot_bits
                raise RuntimeError(
                    f"Slot {slot} verify failed: want={want_on:08b} "
                    f"got_olat={rb_olat:08b} got_gpio={rb_gpio:08b} "
                    f"(slot_bits={slot_bits:08b}, current={current:08b}, new_val={new_val:08b})"
                )

        return True

    except Exception as e:
        print(f"[ID_SLOT][ERROR] slot={slot}: {e}")
        return False


# =========================================================
# SET ALL SLOTS (SAFE)
# =========================================================
def set_all_slots_id_configs(
    masks: Dict[int, int],
    settle_s: float = 0.02,
    verify: bool = True,
) -> bool:
    """
    Apply all 4 slots using the same safe method as your working script.

    masks format (ID1 ID2 ID3):
      {
        1: 0b110,
        2: 0b101,
        3: 0b011,
        4: 0b100,
      }
    """
    try:
        if not init_id_pins_active_high():
            return False

        # float everything first (safe baseline)
        if not float_all_ids(settle_s=0.02):
            return False

        # Apply slot-by-slot (same as your working script)
        for s in (1, 2, 3, 4):
            if s not in masks:
                raise ValueError(f"masks missing slot {s}")
            if not set_slot_bits(s, int(masks[s]), settle_s=settle_s, verify=verify):
                return False

        # debug print (optional)
        try:
            a = read_reg(OLATA) & 0xFF
            b = read_reg(OLATB) & 0xFF
            print(f"[ID_ALL] OLATA=0b{a:08b} (0x{a:02X})  OLATB=0b{b:08b} (0x{b:02X})")
        except Exception:
            pass

        return True

    except Exception as e:
        print(f"[ID_ALL][ERROR] {e}")
        return False


# =========================================================
# YOUR DEFAULT "FINAL" CONFIG WRAPPER
# =========================================================
def init_id_pins_full_config(settle_s: float = 0.02, verify: bool = True) -> bool:
    """
    One-call helper to apply your FINAL per-slot ID configuration.

    Table (ID1 ID2 ID3):
      Slot1 → 110  (ID3 shorted)
      Slot2 → 101  (ID2 shorted)
      Slot3 → 011  (ID1 shorted)
      Slot4 → 100  (ID2 + ID3 shorted)
    """
    SLOT_MASKS = {
        1: 0b110,
        2: 0b101,
        3: 0b011,
        4: 0b100,
    }
    return bool(set_all_slots_id_configs(SLOT_MASKS, settle_s=settle_s, verify=verify))


# =========================================================
# DEBUG
# =========================================================
def debug_dump_id_regs(tag: str = "") -> None:
    try:
        _ensure_spi_open()
        a_olat = read_reg(OLATA) & 0xFF
        b_olat = read_reg(OLATB) & 0xFF
        a_gpio = read_reg(GPIOA) & 0xFF
        b_gpio = read_reg(GPIOB) & 0xFF
        print(
            f"[ID_DUMP]{tag} "
            f"OLATA=0b{a_olat:08b} (0x{a_olat:02X}) GPIOA=0b{a_gpio:08b} (0x{a_gpio:02X})  "
            f"OLATB=0b{b_olat:08b} (0x{b_olat:02X}) GPIOB=0b{b_gpio:08b} (0x{b_gpio:02X})"
        )
    except Exception as e:
        print(f"[ID_DUMP][ERR]{tag} {e}")
