# #!/usr/bin/env python3
# import spidev, time

# IOCONA = 0x0A   # BANK=0
# IOCONB = 0x0B

# def read_reg(spi, op_r, reg):
#     return spi.xfer2([op_r, reg, 0x00])[2]

# def write_reg(spi, op_w, reg, val):
#     spi.xfer2([op_w, reg, val & 0xFF])

# spi = spidev.SpiDev()
# spi.open(0, 0)            # CE0
# spi.max_speed_hz = 500_000
# spi.mode = 0

# print("Addr | op_w op_r | IOCON before -> after (write toggling HAEN bit)")
# print("---------------------------------------------------------------")

# for addr in range(8):
#     op_w = 0x40 | (addr << 1)
#     op_r = 0x41 | (addr << 1)

#     before = read_reg(spi, op_r, IOCONA)
#     test = before ^ 0x08              # toggle HAEN bit
#     write_reg(spi, op_w, IOCONA, test)
#     time.sleep(0.01)
#     after = read_reg(spi, op_r, IOCONA)

#     # also read IOCONB just to see consistency
#     b = read_reg(spi, op_r, IOCONB)

#     print(f" {addr}   | 0x{op_w:02X} 0x{op_r:02X} | 0x{before:02X} -> 0x{after:02X}   (IOCONB=0x{b:02X})")

#     # restore
#     write_reg(spi, op_w, IOCONA, before)
#     time.sleep(0.005)

# spi.close()

import spidev, time

OP_W, OP_R = 0x40, 0x41
IODIRA, OLATA, GPIOA = 0x00, 0x14, 0x12

spi = spidev.SpiDev()
spi.open(0,0)
spi.max_speed_hz = 500_000
spi.mode = 0

def r(reg): return spi.xfer2([OP_R, reg, 0])[2]
def w(reg, val): spi.xfer2([OP_W, reg, val & 0xFF])

w(IODIRA, 0x00)       # outputs
w(OLATA, 0xFB)        # 11111011 (clear bit2)
time.sleep(0.01)

print("OLATA:", hex(r(OLATA)), "GPIOA:", hex(r(GPIOA)))

spi.close()
