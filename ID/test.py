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
# GPA0, GPA1, GPA2 = OUTPUTS
# =========================================================
write_reg(IODIRA, 0b11111000)
print("✔ GPA0, GPA1, GPA2 configured as outputs")

# =========================================================
# LOW-LEVEL HELPERS
# =========================================================

def set_pin(pin):
    val = read_reg(OLATA)
    write_reg(OLATA, val | (1 << pin))

def clear_pin(pin):
    val = read_reg(OLATA)
    write_reg(OLATA, val & ~(1 << pin))

# =========================================================
# HIGH-LEVEL ID COMMANDS (ACTIVE-HIGH)
# =========================================================
# ON  = 1
# OFF = 0

def id1_on():   set_pin(0)
def id1_off():  clear_pin(0)

def id2_on():   set_pin(1)
def id2_off():  clear_pin(1)

def id3_on():   set_pin(2)
def id3_off():  clear_pin(2)

def all_ids_off():
    write_reg(OLATA, 0b00000000)

def all_ids_on():
    write_reg(OLATA, 0b00000111)

# =========================================================
# TEST: TURN ON ONE BY ONE
# =========================================================


all_ids_on()
time.sleep(1)

# print("ID1 ON")
# id1_on()        # 001
# time.sleep(1)

# print("ID2 ON")
# id2_on()        # 011
# time.sleep(1)

# print("ID3 ON")
# id3_on()        # 111
# time.sleep(1)

# print("ID1 OFF")
# id1_off()       # 100
# time.sleep(1)

# print("ID2 OFF")
# id2_off()       # 101
# time.sleep(1)


# print("ID3 OFF")
# id3_off()       # 000
