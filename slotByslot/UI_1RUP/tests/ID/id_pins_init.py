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
# HELPER FUNCTIONS (NEW STYLE)
# =========================================================
def set_all(mask: int):
    write_reg(OLATA, mask)

def set_pin(pin: int):
    val = read_reg(OLATA)
    write_reg(OLATA, val | (1 << pin))

def clear_pin(pin: int):
    val = read_reg(OLATA)
    write_reg(OLATA, val & ~(1 << pin))

def id1_on():  set_pin(0)
def id1_off(): clear_pin(0)

def id2_on():  set_pin(1)
def id2_off(): clear_pin(1)

def id3_on():  set_pin(2)
def id3_off(): clear_pin(2)

def read_ids_bits() -> str:
    """Return bits [ID3 ID2 ID1] as a string like '111'."""
    val = read_reg(OLATA) & 0b00000111
    return f"{(val >> 2) & 1}{(val >> 1) & 1}{val & 1}"

# =========================================================
# INIT FUNCTION — OLD STYLE SEQUENCE (ACTIVE-HIGH)
# =========================================================
def init_id_pins_active_high() -> bool:
    """
    OLD STYLE behavior:
    1) GPA0,1,2 outputs
    2) Set ALL ID pins ON (111)
    3) Delay
    4) Turn OFF ID1 (GPA0) -> 110
    5) Delay
    6) Turn OFF ID2 (GPA1) -> 100
    7) Delay
    (Optional) Turn OFF ID3 -> 000
    """

    try:
        spi.open(0, 0)                  # SPI bus 0, CE0
        spi.max_speed_hz = 10_000_000

        # GPA0, GPA1, GPA2 outputs (0 = output)
        write_reg(IODIRA, 0b11111000)
        print("✔ GPA0, GPA1, GPA2 configured as outputs")

        print("\n=== ACTIVE-HIGH MODE (OLD STYLE SEQUENCE) ===")

        # Turn ALL IDs ON
        set_all(0b00000111)
        print(f"✔ ID1, ID2, ID3 = ON  (state={read_ids_bits()})")
        time.sleep(1)

        # # Turn OFF ID1 (GPA0)
        # id1_off()
        # print(f"✔ ID1 (GPA0) turned OFF (state={read_ids_bits()})")
        # time.sleep(1)

        # # Turn OFF ID2 (GPA1)
        # id2_off()
        # print(f"✔ ID2 (GPA1) turned OFF (state={read_ids_bits()})")
        # time.sleep(1)

        # OPTIONAL: Turn OFF ID3 (GPA2)
        id3_off()
        print(f"✔ ID3 (GPA2) turned OFF (state={read_ids_bits()})")
        time.sleep(1)

        return True

    except Exception as e:
        print(f"[ID_INIT][ERROR] {e}")
        return False
