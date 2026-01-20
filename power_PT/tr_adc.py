#!/usr/bin/env python3
import time, spidev, lgpio, statistics

SPI_BUS=0; SPI_DEV=0; SPI_SPEED=1_000_000
CS_GPIO=5; GPIO_CHIP=0

CH_H = 0   # CAN_H -> CH0
CH_L = 1   # CAN_L -> CH1

VREF = 5.0
ADC_MAX = 1023.0

h = lgpio.gpiochip_open(GPIO_CHIP)
lgpio.gpio_claim_output(h, CS_GPIO, 1)

spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEV)
spi.max_speed_hz = SPI_SPEED
spi.mode = 0
spi.no_cs = True

def read_mcp3008(channel: int) -> int:
    tx = [1, (8 + (channel & 7)) << 4, 0]
    lgpio.gpio_write(h, CS_GPIO, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)
    return ((rx[1] & 0x03) << 8) | rx[2]

def read_med(channel, n=25):
    vals = [read_mcp3008(channel) for _ in range(n)]
    med = statistics.median(vals)
    return (med * VREF / ADC_MAX)

try:
    while True:
        vh = read_med(CH_H, 25)
        vl = read_med(CH_L, 25)
        vdiff = vh - vl

        print(f"Vh={vh:.3f} V  Vl={vl:.3f} V  Vdiff={vdiff:.3f} V")
        time.sleep(0.2)

except KeyboardInterrupt:
    pass
finally:
    spi.close()
    lgpio.gpiochip_close(h)
