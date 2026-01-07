#!/usr/bin/env python3
import time
import spidev
import lgpio

# ==============================
# CONFIG
# ==============================
SPI_BUS = 0
SPI_DEV = 0              # still SPI0, but CE is unused
SPI_SPEED = 1_000_000

CS_GPIO = 5              # <-- your GPIO5
GPIO_CHIP = 0

VREF = 5.0
ADC_MAX = 1023
CH = 0

# ==============================
# GPIO + SPI SETUP
# ==============================
h = lgpio.gpiochip_open(GPIO_CHIP)
lgpio.gpio_claim_output(h, CS_GPIO, 1)  # idle HIGH

spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEV)
spi.max_speed_hz = SPI_SPEED
spi.mode = 0
spi.no_cs = True         # IMPORTANT: we control CS manually

def read_mcp3008(channel: int) -> int:
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    lgpio.gpio_write(h, CS_GPIO, 0)     # CS LOW
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)     # CS HIGH

    return ((rx[1] & 0x03) << 8) | rx[2]

try:
    while True:
        raw = read_mcp3008(CH)
        volts = raw * VREF / ADC_MAX
        print(f"RAW={raw:4d}  V={volts:.3f}")
        time.sleep(0.2)

except KeyboardInterrupt:
    pass
finally:
    spi.close()
    lgpio.gpiochip_close(h)
