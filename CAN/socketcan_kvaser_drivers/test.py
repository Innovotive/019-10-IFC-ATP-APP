import spidev
import time

# ===== MCP23S17 Opcodes (A2-A0 = 0) =====
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

# ===== MCP23S17 Registers =====
IODIRA = 0x00
IODIRB = 0x01
GPIOA  = 0x12
GPIOB  = 0x13
OLATA  = 0x14
OLATB  = 0x15

# ===== SPI Setup =====
spi = spidev.SpiDev()
spi.open(0, 0)     # bus 0, chip-select CE0
spi.max_speed_hz = 10000000

def write_reg(reg, value):
    """Write a value to an MCP23S17 register."""
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    """Read one MCP23S17 register."""
    resp = spi.xfer2([OPCODE_READ, reg, 0x00])
    return resp[2]

# ============================================================
#  Set GPB0, GPB1, GPB2 as outputs (rest unchanged)
# ============================================================
current_dir = read_reg(IODIRB)
current_dir &= 0b11111000   # B0,B1,B2 -> outputs (0), keep others as-is
write_reg(IODIRB, current_dir)

# ============================================================
#  Function: Set GPB0 / GPB1 / GPB2 individually without
#  touching other bits on Port B
# ============================================================
def set_gpb012(gpb0=None, gpb1=None, gpb2=None):
    # Read current state of OLATB
    current = read_reg(OLATB)

    # ---- GPB0 ----
    if gpb0 is not None:
        if gpb0: current |=  (1 << 0)
        else:    current &= ~(1 << 0)

    # ---- GPB1 ----
    if gpb1 is not None:
        if gpb1: current |=  (1 << 1)
        else:    current &= ~(1 << 1)

    # ---- GPB2 ----
    if gpb2 is not None:
        if gpb2: current |=  (1 << 2)
        else:    current &= ~(1 << 2)

    # Write updated value back
    write_reg(OLATB, current)

# ============================================================
#                       TEST LOOP
# ============================================================
if __name__ == "__main__":
    print("Starting GPB0/1/2 toggle test...")

    while True:
        print("GPB0=0, GPB1=0, GPB2=0")
        set_gpb012(gpb0=0, gpb1=0, gpb2=1)
