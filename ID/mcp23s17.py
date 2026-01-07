import spidev
import time

# MCP23S17 opcodes (A2 A1 A0 = 000)
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

# Registers
IODIRA = 0x00
GPIOA  = 0x12
OLATA  = 0x14

# SPI setup
spi = spidev.SpiDev()
spi.open(0, 0)          # SPI bus 0, CE0
spi.max_speed_hz = 10000000

def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

# -----------------------------
# SETUP: GPA0,1,2 as OUTPUT
# -----------------------------
# 0 = output, 1 = input
# 11111000 -> GPA0-2 outputs, GPA3-7 inputs (safe)
write_reg(IODIRA, 0b11111000)

print("Configured GPA0, GPA1, GPA2 as outputs")

print("ID3 (GPA2) ON")
write_reg(OLATA, 0b00000100)
time.sleep(1)

# -----------------------------
# TEST LOOP
# -----------------------------
#while True:
   # print("ID1 (GPA0) ON")
    #write_reg(OLATA, 0b00000001)
    #time.sleep(1)

    #print("ID2 (GPA1) ON")
    # write_reg(OLATA, 0b00000010)
    # time.sleep(1)

    #print("ID3 (GPA2) ON")
    #write_reg(OLATA, 0b00000100)
    #time.sleep(1)

   # print("ALL OFF")
    #write_reg(OLATA, 0b00000000)
    #time.sleep(2)
