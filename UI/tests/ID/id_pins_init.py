import spidev
import time

# =========================================================
# MCP23S17 SPI CONFIG
# =========================================================

OPCODE_WRITE = 0x40   # A2 A1 A0 = 000
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
# INIT FUNCTION — EXACT SEQUENCE
# =========================================================

def init_id_pins_active_high() -> bool:
    """
    EXACT behavior:
    1) GPA0,1,2 outputs
    2) Set ALL ID pins ON
    3) Delay
    4) Turn OFF ID3 (GPA2)
    5) Delay
    """

    try:
        spi.open(0, 0)                  # SPI bus 0, CE0
        spi.max_speed_hz = 10_000_000

        # GPA0, GPA1, GPA2 outputs (0 = output)
        write_reg(IODIRA, 0b11111000)
        print("✔ GPA0, GPA1, GPA2 configured as outputs")

        # -------------------------------------------------
        # ACTIVE-HIGH MODE
        # -------------------------------------------------
        print("=== ACTIVE-HIGH MODE ===")

        # Turn ALL IDs ON
        write_reg(OLATA, 0b00000111)
        print("✔ ID1, ID2, ID3 = ON")
        time.sleep(1)

        # Turn OFF ID3 (GPA2)
        val = read_reg(OLATA)
        write_reg(OLATA, val & ~(1 << 2))
        print("✔ ID3 (GPA2) turned OFF")
        time.sleep(1)

        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False
