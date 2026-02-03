import spidev
import time

# =========================================================
# MCP23S17 SPI CONFIG
# =========================================================
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

# Port B registers
IODIRB = 0x01
OLATB  = 0x15

# =========================================================
# SPI SETUP
# =========================================================
spi = spidev.SpiDev()

def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

# =========================================================
# HELPER FUNCTIONS (GPB0,1,2)
# =========================================================
ID1_PIN = 0  # GPB0
ID2_PIN = 1  # GPB1
ID3_PIN = 2  # GPB2

def set_pin(pin: int):
    val = read_reg(OLATB)
    write_reg(OLATB, val | (1 << pin))

def clear_pin(pin: int):
    val = read_reg(OLATB)
    write_reg(OLATB, val & ~(1 << pin))

def id1_on():  set_pin(ID1_PIN)
def id1_off(): clear_pin(ID1_PIN)

def id2_on():  set_pin(ID2_PIN)
def id2_off(): clear_pin(ID2_PIN)

def id3_on():  set_pin(ID3_PIN)
def id3_off(): clear_pin(ID3_PIN)

def read_ids_bits() -> str:
    """Return bits [ID3 ID2 ID1] as a string like '011'."""
    val = read_reg(OLATB) & 0b00000111
    return f"{(val >> 2) & 1}{(val >> 1) & 1}{val & 1}"

# =========================================================
# INIT FUNCTION — ACTIVE-HIGH (GPB0/1/2 → 011)
# =========================================================
def init_id_pins_active_high() -> bool:
    """
    Configure GPB0,1,2 as outputs and set ID pattern = 011
    ID3=0, ID2=1, ID1=1
    """

    try:
        spi.open(0, 0)                  # SPI bus 0, CE0
        spi.max_speed_hz = 10_000_000

        # GPB0, GPB1, GPB2 outputs (0 = output)
        # Keep others as inputs (1)
        write_reg(IODIRB, 0b11111000)
        print("✔ GPB0, GPB1, GPB2 configured as outputs")

        print("\n=== ACTIVE-HIGH MODE (GPB0/1/2 → 011) ===")

        # Clear all ID bits first
        id1_off()
        id2_off()
        id3_off()

        # Set pattern 100: ID1=1, ID2=1, ID3=0
        id1_on()    # GPB0 = 1
        id2_off()    # GPB1 = 0
        id3_off()   # GPB2 = 0

        time.sleep(0.5)
        print(f"✔ ID state set to {read_ids_bits()} (expected 011)")

        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False
