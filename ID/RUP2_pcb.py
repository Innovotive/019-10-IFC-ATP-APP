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
spi.open(0, 0)
spi.max_speed_hz = 10000000

def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

# =========================================================
# GPIO SETUP
# GPA3, GPA4, GPA5 = OUTPUTS
# =========================================================
# Bit: 7 6 5 4 3 2 1 0
#      1 1 0 0 0 1 1 1
write_reg(IODIRA, 0b11000111)
print("✔ GPA3, GPA4, GPA5 configured as outputs")

# =========================================================
# HELPER FUNCTIONS
# =========================================================
def set_pin(pin):
    val = read_reg(OLATA)
    write_reg(OLATA, val | (1 << pin))

def clear_pin(pin):
    val = read_reg(OLATA)
    write_reg(OLATA, val & ~(1 << pin))

def set_a3_a5(mask):
    """
    mask: 3-bit value
    bit0 -> GPA3
    bit1 -> GPA4
    bit2 -> GPA5
    """
    val = read_reg(OLATA)
    val &= ~(0b00111000)          # clear GPA3-5
    val |= (mask << 3)            # apply new state
    write_reg(OLATA, val)

# =========================================================
# ACTIVE-HIGH MODE (GPA3–GPA5)
# =========================================================
print("\n=== ACTIVE-HIGH MODE (GPA3–GPA5) ===")

# Turn GPA3, GPA4, GPA5 ON
# Binary: 111 -> shifted to bits 3,4,5
set_a3_a5(0b111)
print("✔ GPA3, GPA4, GPA5 ON")
time.sleep(2)

# print("Turning OFF GPA3")
# clear_pin(3)


print("Turning OFF GPA4")
clear_pin(4)
time.sleep(2)

# print("Turning OFF GPA5")
# clear_pin(5)
# time.sleep(2)


