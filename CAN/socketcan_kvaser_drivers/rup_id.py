import spidev
import time

OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

IODIRB = 0x01
GPIOB  = 0x13
OLATB  = 0x15

spi = spidev.SpiDev()
spi.open(0, 0)
spi.max_speed_hz = 10000000

def write_reg(reg, value):
    spi.xfer2([OPCODE_WRITE, reg, value])

def read_reg(reg):
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

# ---- Initialize: all B pins input (floating) ----
write_reg(IODIRB, 0xFF)


def set_id_bits(id2, id1, id0):
    """
    RUP ID pins:
      0 = short to GND
      1 = floating (input)

    Mapping:
      GPB0 = ID0  (bit0)
      GPB1 = ID1  (bit1)
      GPB2 = ID2  (bit2)
    """
    # Build direction mask:
    # 1 = input (float), 0 = output (drive low)
    dir_mask = 0b11111111

    if id0 == 0: dir_mask &= ~(1 << 0)
    if id1 == 0: dir_mask &= ~(1 << 1)
    if id2 == 0: dir_mask &= ~(1 << 2)

    write_reg(IODIRB, dir_mask)

    # For pins configured as outputs, drive LOW
    out_val = 0x00  # LOW everywhere
    write_reg(OLATB, out_val)

    print("IODIRB =", bin(dir_mask))
    print("GPIOB  =", bin(read_reg(GPIOB)))

