import spidev
import time

# =========================================================
# MCP23S17 SPI CONFIG
# =========================================================

OPCODE_WRITE = 0x40   # A2 A1 A0 = 000
OPCODE_READ  = 0x41

IODIRB = 0x01
OLATB  = 0x15

# =========================================================
# SPI SETUP
# =========================================================

spi = spidev.SpiDev()
spi.open(0, 0)                  # SPI bus 0, CE0
spi.max_speed_hz = 10_000_000

def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

# =========================================================
# GPIO SETUP
# GPB3, GPB4, GPB5 = OUTPUTS
# =========================================================
# 0 = output, 1 = input
write_reg(IODIRB, 0b11000111)

print("✔ GPB3, GPB4, GPB5 configured as outputs")

# =========================================================
# HELPER FUNCTIONS (SAME PRINCIPLE)
# =========================================================

def set_all(mask):
    write_reg(OLATB, mask)

def clear_pin(pin):
    val = read_reg(OLATB)
    write_reg(OLATB, val & ~(1 << pin))

def set_pin(pin):
    val = read_reg(OLATB)
    write_reg(OLATB, val | (1 << pin))

# =========================================================
# OPTION A — ACTIVE-HIGH ID PINS
# =========================================================

print("\n=== ACTIVE-HIGH MODE (PORT B) ===")

# Turn ALL B3, B4, B5 ON
set_all(0b00111000)
time.sleep(2)

# print("Turning OFF ID5 (GPB4)")
# clear_pin(3)

print("Turning OFF ID5 (GPB4)")
clear_pin(4)
time.sleep(2)

print("Turning OFF ID6 (GPB5)") 
clear_pin(5)
time.sleep(2)