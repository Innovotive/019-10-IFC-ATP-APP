import spidev
import time

# =========================================================
# MCP23S17 SPI CONFIG
# =========================================================
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

IODIRA = 0x00
OLATA  = 0x14

# =========================================================
# SPI SETUP
# =========================================================
spi = spidev.SpiDev()

def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

# =========================================================
# HELPER FUNCTIONS (GPA3,4,5)
# =========================================================
ID1_PIN = 3  # GPA3
ID2_PIN = 4  # GPA4
ID3_PIN = 5  # GPA5

def set_pin(pin: int):
    val = read_reg(OLATA)
    write_reg(OLATA, val | (1 << pin))

def clear_pin(pin: int):
    val = read_reg(OLATA)
    write_reg(OLATA, val & ~(1 << pin))

def id1_on():  set_pin(ID1_PIN)
def id1_off(): clear_pin(ID1_PIN)

def id2_on():  set_pin(ID2_PIN)
def id2_off(): clear_pin(ID2_PIN)

def id3_on():  set_pin(ID3_PIN)
def id3_off(): clear_pin(ID3_PIN)

def read_ids_bits() -> str:
    """Return bits [ID3 ID2 ID1] as a string like '101'."""
    val = read_reg(OLATA)
    return f"{(val >> ID3_PIN) & 1}{(val >> ID2_PIN) & 1}{(val >> ID1_PIN) & 1}"

# =========================================================
# INIT FUNCTION — ACTIVE-HIGH (GPA3/4/5)
# =========================================================
def init_id_pins_active_high() -> bool:
    """
    Configure GPA3,4,5 as outputs and set ID pattern = 101
    ID3=1, ID2=0, ID1=1
    """

    try:
        spi.open(0, 0)                  # SPI bus 0, CE0
        spi.max_speed_hz = 10_000_000

        # GPA3,4,5 outputs (0 = output)
        # Bits 3,4,5 → 0 ; others untouched
        write_reg(IODIRA, 0b11000111)
        print("✔ GPA3, GPA4, GPA5 configured as outputs")

        print("\n=== ACTIVE-HIGH MODE (GPA3/4/5 → 101) ===")

        # Clear all ID bits first
        clear_pin(ID1_PIN)
        clear_pin(ID2_PIN)
        clear_pin(ID3_PIN)

        # Set pattern 101
        id1_on()   # GPA3 = 1
        id2_off()  # GPA4 = 0
        id3_on()   # GPA5 = 1

        time.sleep(0.5)
        print(f"✔ ID state set to {read_ids_bits()} (expected 101)")

        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False
