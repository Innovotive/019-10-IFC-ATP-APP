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
# HELPER FUNCTIONS (GPB3,4,5)
# =========================================================
ID1_PIN = 3  # GPB3
ID2_PIN = 4  # GPB4
ID3_PIN = 5  # GPB5

ID_MASK = (1 << ID1_PIN) | (1 << ID2_PIN) | (1 << ID3_PIN)  # 0b00111000

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
    """Return bits [ID3 ID2 ID1] as a string like '100'."""
    val = read_reg(OLATB)
    return f"{(val >> ID3_PIN) & 1}{(val >> ID2_PIN) & 1}{(val >> ID1_PIN) & 1}"

# =========================================================
# INIT FUNCTION — ACTIVE-HIGH (GPB3/4/5 → 100)
# =========================================================
def init_id_pins_active_high() -> bool:
    """
    Configure GPB3,4,5 as outputs and set ID pattern = 100
    ID3=1, ID2=0, ID1=0
    """

    try:
        spi.open(0, 0)                  # SPI bus 0, CE0
        spi.max_speed_hz = 10_000_000

        # GPB3,4,5 outputs (0 = output), others inputs (1)
        # B7..B0 = 1 1 0 0 0 1 1 1  -> GPB5/4/3 are outputs
        write_reg(IODIRB, 0b11000111)
        print("✔ GPB3, GPB4, GPB5 configured as outputs")

        print("\n=== ACTIVE-HIGH MODE (GPB3/4/5 → 100) ===")

        # Clear all ID bits first (only our 3 bits)
        val = read_reg(OLATB)
        write_reg(OLATB, val & ~ID_MASK)

        # Set pattern 100: ID1=0, ID2=0, ID3=1
        id1_off()   # GPB3 = 0
        id2_on()   # GPB4 = 1
        id3_on()    # GPB5 = 1

        time.sleep(0.5)
        print(f"✔ ID state set to {read_ids_bits()} (expected 100)")

        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False
