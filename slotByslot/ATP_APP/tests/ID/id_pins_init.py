# tests/ID/id_pins_init.py
import time
import spidev

# =========================================================
# MCP23S17 REGISTERS
# =========================================================
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

IODIRA = 0x00
IODIRB = 0x01
GPIOA  = 0x12
GPIOB  = 0x13
OLATA  = 0x14
OLATB  = 0x15

SPI_BUS = 0
SPI_CS  = 0
SPI_HZ  = 10_000_000

# =========================================================
# SLOT → PIN MAPPING (same as your proven script)
# pins tuple = (ID1, ID2, ID3)
# =========================================================
SLOTS = {
    1: ("A", (0, 1, 2)),  # GPA0 GPA1 GPA2
    2: ("A", (3, 4, 5)),  # GPA3 GPA4 GPA5
    3: ("B", (0, 1, 2)),  # GPB0 GPB1 GPB2
    4: ("B", (3, 4, 5)),  # GPB3 GPB4 GPB5
}

ID_MASK_A = 0b00111111  # A0..A5
ID_MASK_B = 0b00111111  # B0..B5

# =========================================================
# LOW-LEVEL SPI HELPERS
# =========================================================
def _write(spi, reg, val):
    spi.xfer2([OPCODE_WRITE, reg, val & 0xFF])

def _read(spi, reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

def _olat_reg(port: str) -> int:
    return OLATA if port == "A" else OLATB

def _gpio_reg(port: str) -> int:
    return GPIOA if port == "A" else GPIOB

def _read_olat(spi, port: str) -> int:
    return _read(spi, _olat_reg(port))

def _write_olat(spi, port: str, val: int):
    _write(spi, _olat_reg(port), val)

def _read_gpio(spi, port: str) -> int:
    return _read(spi, _gpio_reg(port))

def dump_regs(spi, tag="ID_INIT"):
    iodra = _read(spi, IODIRA)
    iodrb = _read(spi, IODIRB)
    olata = _read(spi, OLATA)
    olatb = _read(spi, OLATB)
    gpioa = _read(spi, GPIOA)
    gpiob = _read(spi, GPIOB)
    print(
        f"[{tag}] IODIRA={iodra:08b} IODIRB={iodrb:08b} "
        f"OLATA={olata:08b} OLATB={olatb:08b} "
        f"GPIOA={gpioa:08b} GPIOB={gpiob:08b}"
    )

# =========================================================
# SAFE LOGIC (ported from your proven script)
# =========================================================
def _mask_to_bits(pins, mask3):
    """
    mask3 written as (ID1 ID2 ID3), e.g. 110 means:
      ID1=1 -> pin(ID1) HIGH
      ID2=1 -> pin(ID2) HIGH
      ID3=0 -> pin(ID3) LOW
    pins is (ID1_pin, ID2_pin, ID3_pin)
    """
    p0, p1, p2 = pins  # (ID1, ID2, ID3)
    out = 0
    if mask3 & 0b100: out |= (1 << p0)  # MSB -> ID1
    if mask3 & 0b010: out |= (1 << p1)  # mid -> ID2
    if mask3 & 0b001: out |= (1 << p2)  # LSB -> ID3
    return out & 0xFF

def _init_outputs(spi):
    # A0–A5 outputs, A6–A7 inputs
    # B0–B5 outputs, B6–B7 inputs
    _write(spi, IODIRA, 0b11000000)
    _write(spi, IODIRB, 0b11000000)
    print("[ID_INIT] ✔ GPIO direction set (ID pins = outputs)")

def _float_all_ids(spi):
    a = _read_olat(spi, "A")
    b = _read_olat(spi, "B")

    _write_olat(spi, "A", a | ID_MASK_A)
    _write_olat(spi, "B", b | ID_MASK_B)
    time.sleep(0.02)

    print("[ID_INIT] ✔ All ID pins floated (HIGH)")

def _set_slot(spi, slot: int, mask3: int):
    port, pins = SLOTS[slot]
    allowed = ID_MASK_A if port == "A" else ID_MASK_B

    slot_bits = sum(1 << p for p in pins) & 0xFF
    want_on = _mask_to_bits(pins, mask3) & 0xFF
    want_on &= slot_bits

    current = _read_olat(spi, port) & 0xFF

    # only change those 3 pins
    new_val = (current & ~slot_bits) | want_on
    new_val &= 0xFF

    # safety: keep non-allowed bits unchanged
    new_val = (current & ~allowed) | (new_val & allowed)
    new_val &= 0xFF

    _write_olat(spi, port, new_val)
    time.sleep(0.02)

    rb_olat = _read_olat(spi, port) & slot_bits
    if rb_olat != want_on:
        rb_gpio = _read_gpio(spi, port) & slot_bits
        raise RuntimeError(
            f"Slot {slot} verify failed: want={want_on:08b} "
            f"got_olat={rb_olat:08b} got_gpio={rb_gpio:08b} "
            f"(slot_bits={slot_bits:08b}, current={current:08b}, new_val={new_val:08b})"
        )

    print(f"[ID_INIT] ✔ Slot{slot} ID set to {mask3:03b} (ID1 ID2 ID3)")

def _set_all_slots(spi, masks: dict):
    _float_all_ids(spi)
    for s in (1, 2, 3, 4):
        _set_slot(spi, s, masks[s])

# =========================================================
# PUBLIC API (KEEP SAME NAME)
# =========================================================
def init_id_pins_all_slots() -> bool:
    """
    Keep this name so your main app can call it.

    Applies the baseline patterns for all 4 slots using the
    proven "FINAL SAFE" method (float all -> set per slot -> verify).
    """
  
    SLOT_MASKS = {
        1: 0b110,
        2: 0b101,
        3: 0b100,
        4: 0b011,
    }

    spi = spidev.SpiDev()
    try:
        spi.open(SPI_BUS, SPI_CS)
        spi.max_speed_hz = SPI_HZ
        spi.mode = 0

        _init_outputs(spi)
        _set_all_slots(spi, SLOT_MASKS)

        dump_regs(spi, tag="ID_INIT")
        print("[ID_INIT] ✅ All slot ID baselines applied")
        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False

    finally:
        try:
            spi.close()
        except Exception:
            pass


# Optional: standalone run
if __name__ == "__main__":
    ok = init_id_pins_all_slots()
    raise SystemExit(0 if ok else 1)
