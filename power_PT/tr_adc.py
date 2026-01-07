#!/usr/bin/env python3
"""
Raspberry Pi + MCP3008
CAN_H termination detection

- Manual CS on GPIO5
- VREF = 5.0 V
- Top-20 sampling over ~120 ms
- Thresholds tuned to real measurements
"""

import time
import spidev
import lgpio

# ==============================
# CONFIG
# ==============================
SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED = 1_000_000  # 1 MHz

CS_GPIO = 5           # manual CS (your wiring)
GPIO_CHIP = 0

CAN_H_CHANNEL = 0

VREF = 5.0
ADC_MAX = 1023

# ---- Tuned thresholds (FROM YOUR DATA) ----
TERMINATION_ON_MAX_V  = 2.40   # ≤ this → termination ON
TERMINATION_OFF_MIN_V = 2.44   # ≥ this → termination OFF

# Sampling parameters
NUM_TOP = 20
WINDOW_MS = 120
SAMPLE_DELAY_US = 500

# ==============================
# GPIO + SPI SETUP
# ==============================
h = lgpio.gpiochip_open(GPIO_CHIP)
lgpio.gpio_claim_output(h, CS_GPIO, 1)   # CS idle HIGH

spi = spidev.SpiDev()
spi.open(SPI_BUS, SPI_DEV)
spi.max_speed_hz = SPI_SPEED
spi.mode = 0
spi.no_cs = True                         # we control CS manually

# ==============================
# MCP3008 READ
# ==============================
def read_mcp3008(channel: int) -> int:
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    lgpio.gpio_write(h, CS_GPIO, 0)      # CS LOW
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)      # CS HIGH

    return ((rx[1] & 0x03) << 8) | rx[2]

# ==============================
# MEASUREMENT LOGIC
# ==============================
def measure_can_h_voltage() -> tuple[float, float]:
    """
    Returns:
        voltage (V)
        avg_raw (ADC counts)
    """
    # Prime top samples
    top = [read_mcp3008(CAN_H_CHANNEL) for _ in range(NUM_TOP)]
    time.sleep(NUM_TOP * SAMPLE_DELAY_US / 1_000_000)

    start = time.time()
    while (time.time() - start) * 1000 < WINDOW_MS:
        raw = read_mcp3008(CAN_H_CHANNEL)
        time.sleep(SAMPLE_DELAY_US / 1_000_000)

        min_idx = top.index(min(top))
        if raw > top[min_idx]:
            top[min_idx] = raw

    avg_raw = sum(top) / NUM_TOP
    voltage = avg_raw * VREF / ADC_MAX
    return voltage, avg_raw

# ==============================
# TERMINATION DECISION
# ==============================
def get_termination_state(voltage: float) -> str:
    if voltage <= TERMINATION_ON_MAX_V:
        return "TERMINATION ON"
    elif voltage >= TERMINATION_OFF_MIN_V:
        return "TERMINATION OFF"
    else:
        return "UNSTABLE / TRANSITION"

# ==============================
# MAIN LOOP
# ==============================
try:
    last_state = "UNKNOWN"

    while True:
        voltage, avg_raw = measure_can_h_voltage()
        state = get_termination_state(voltage)

        print(
            f"CAN_H Voltage: {voltage:.3f} V | "
            f"RAW(avg): {avg_raw:.1f} | "
            f"State: {state}"
        )

        last_state = state
        time.sleep(0.1)

except KeyboardInterrupt:
    print("\nStopping...")

finally:
    spi.close()
    lgpio.gpiochip_close(h)
