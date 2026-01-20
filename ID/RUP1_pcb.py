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
spi.open(0, 0)                  # SPI bus 0, CE0
spi.max_speed_hz = 10_000_000

def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

# =========================================================
# GPIO SETUP
# GPA0, GPA1, GPA2 = ID PINS (OUTPUT)
# =========================================================
# 0 = output, 1 = input
write_reg(IODIRA, 0b11111000)

print("✔ GPA0, GPA1, GPA2 configured as outputs")

# =========================================================
# HELPER FUNCTIONS
# =========================================================

def set_all(mask):
    write_reg(OLATA, mask)

def clear_pin(pin):
    val = read_reg(OLATA)
    write_reg(OLATA, val & ~(1 << pin))

def set_pin(pin):
    val = read_reg(OLATA)
    write_reg(OLATA, val | (1 << pin))

# =========================================================
# =================== CHOOSE ONE OPTION ===================
# =========================================================


# =========================================================
# OPTION A — ACTIVE-HIGH ID PINS
# ON  = 1
# OFF = 0
# =========================================================

print("\n=== ACTIVE-HIGH MODE ===")

# Turn ALL IDs ON
set_all(0b00000111) #floated 1.

time.sleep(2)

# print("Turning OFF ID1 (GPA0)") #case3: 011 doesnt work only ID1 shorted 
# clear_pin(0)
# time.sleep(2)


# print("Turning OFF ID2 (GPA1)")#shorted 0 =>101: case5, ID2 only shorted/turned off
# clear_pin(1)
# time.sleep(2)

print("Turning OFF ID3 (GPA2)") #shorted 0 =>110: case6, ID3 only shorted/turned off
clear_pin(2)
time.sleep(1)

