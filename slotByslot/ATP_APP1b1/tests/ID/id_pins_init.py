# tests/ID/id_pins_init.py
import time
import spidev

# =========================================================
# MCP23S17 CONFIG
# =========================================================
SPI_BUS = 0
SPI_CS  = 0
SPI_HZ  = 10_000_000
HW_ADDR = 0  # MCP23S17 A2/A1/A0 = 000

def _op_write():
    return 0x40 | ((HW_ADDR & 0x07) << 1)

def _op_read():
    return 0x41 | ((HW_ADDR & 0x07) << 1)

# =========================================================
# REGISTERS (BANK=0)
# =========================================================
IODIRA = 0x00
IODIRB = 0x01
GPIOA  = 0x12
GPIOB  = 0x13
OLATA  = 0x14
OLATB  = 0x15
IOCONA = 0x0A
IOCONB = 0x0B

# =========================================================
# SLOT → PIN MAP (ID1, ID2, ID3)
# =========================================================
SLOTS = {
    1: ("A", (0, 1, 2)),
    2: ("A", (3, 4, 5)),
    3: ("B", (0, 1, 2)),
    4: ("B", (3, 4, 5)),
}

ID_MASK_A = 0b00111111
ID_MASK_B = 0b00111111

# =========================================================
# SLOT ID PATTERNS (normal ON state)
# =========================================================
SLOT_MASKS = {
    1: 0b110,
    2: 0b101,
    3: 0b011,
    4: 0b100,
}

# =========================================================
# SPI helpers
# =========================================================
def _write(spi, reg, val):
    spi.xfer2([_op_write(), reg & 0xFF, val & 0xFF])

def _read(spi, reg):
    return spi.xfer2([_op_read(), reg & 0xFF, 0x00])[2]

def _olat(port):
    return OLATA if port == "A" else OLATB

def _read_olat(spi, port):
    return _read(spi, _olat(port))

def _write_olat(spi, port, val):
    _write(spi, _olat(port), val)

# =========================================================
# INIT helpers
# =========================================================
def _init_outputs(spi):
    _write(spi, IOCONA, 0x08)  # HAEN=1, BANK=0
    _write(spi, IOCONB, 0x08)
    _write(spi, IODIRA, 0b11000000)
    _write(spi, IODIRB, 0b11000000)
    time.sleep(0.01)

def _mask_to_bits(pins, mask3):
    p0, p1, p2 = pins
    out = 0
    if mask3 & 0b100: out |= (1 << p0)
    if mask3 & 0b010: out |= (1 << p1)
    if mask3 & 0b001: out |= (1 << p2)
    return out & 0xFF

# =========================================================
# PUBLIC API
# =========================================================
def init_id_pins_for_slot(slot: int) -> bool:
    """Normal ON config for a slot"""
    spi = spidev.SpiDev()
    try:
        spi.open(SPI_BUS, SPI_CS)
        spi.max_speed_hz = SPI_HZ
        spi.mode = 0

        _init_outputs(spi)

        port, pins = SLOTS[slot]
        slot_bits = sum(1 << p for p in pins)
        want = _mask_to_bits(pins, SLOT_MASKS[slot])

        cur = _read_olat(spi, port)
        new = (cur & ~slot_bits) | want
        _write_olat(spi, port, new)
        time.sleep(0.02)

        print(f"[ID_INIT] Slot {slot} ID set to {SLOT_MASKS[slot]:03b}")
        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] slot={slot}: {e}")
        return False
    finally:
        spi.close()


def force_id_pins_off_for_slot(slot: int) -> bool:
    """
    HARD-OFF:
    Forces ID1/ID2/ID3 = 0 for this slot
    This is required to fully power down the RUP.
    """
    spi = spidev.SpiDev()
    try:
        spi.open(SPI_BUS, SPI_CS)
        spi.max_speed_hz = SPI_HZ
        spi.mode = 0

        _init_outputs(spi)

        port, pins = SLOTS[slot]
        slot_bits = sum(1 << p for p in pins)

        cur = _read_olat(spi, port)
        new = cur & ~slot_bits   # FORCE ALL 3 PINS LOW
        _write_olat(spi, port, new)
        time.sleep(0.02)

        print(f"[ID_INIT] Slot {slot} ID pins FORCED LOW (000)")
        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] force_off slot={slot}: {e}")
        return False
    finally:
        spi.close()
