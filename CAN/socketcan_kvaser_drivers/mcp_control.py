import spidev
import time

# MCP23S17 SPI opcodes
OPCODE_WRITE = 0x40  # A2-A0 = 000
OPCODE_READ  = 0x41

# Register addresses
IODIRA = 0x00
IODIRB = 0x01
GPIOA  = 0x12
GPIOB  = 0x13
OLATA  = 0x14
OLATB  = 0x15

spi = spidev.SpiDev()
spi.open(0, 0)   # bus 0, CE0
spi.max_speed_hz = 10000000

def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    resp = spi.xfer2([OPCODE_READ, reg, 0x00])
    return resp[2]

# -------------------------------
# Setup: All pins output
# -------------------------------
print("Configuring I/O...")
write_reg(IODIRA, 0x00)  # All A outputs
write_reg(IODIRB, 0x00)  # All B outputs

time.sleep(0.1)

# -------------------------------
# Test: Toggle all pins on A/B
# -------------------------------
while True:
    print("ALL HIGH")
    write_reg(OLATA, 0xFF)
    write_reg(OLATB, 0xFF)
    print("Read A:", hex(read_reg(GPIOA)))
    print("Read B:", hex(read_reg(GPIOB)))
    time.sleep(1)

    print("ALL LOW")
    write_reg(OLATA, 0x00)
    write_reg(OLATB, 0x00)
    print("Read A:", hex(read_reg(GPIOA)))
    print("Read B:", hex(read_reg(GPIOB)))
    time.sleep(1)
