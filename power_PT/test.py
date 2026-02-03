#!/usr/bin/env python3
import time
import statistics
import spidev
import lgpio

# ==============================
# MCP3008 (SPI) CONFIG
# ==============================
SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED = 1_000_000
SPI_MODE = 0

# Manual chip-select (because spi.no_cs=True)
GPIO_CHIP = 0
CS_GPIO = 5

# ADC + scaling
VREF = 5.0
ADC_MAX = 1023
ADC_CH = 0  # MCP3008 channel (0..7)

# Sampling
WINDOW_S = 3.0
FS_HZ = 500
TOP_N = 20

# ==============================
# ADC helpers
# ==============================
def read_mcp3008_volts(spi, h, channel: int) -> float:
    """Read MCP3008 channel and return volts."""
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    lgpio.gpio_write(h, CS_GPIO, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)

    raw = ((rx[1] & 0x03) << 8) | rx[2]
    volts = raw * VREF / ADC_MAX
    return volts


def sample_window(spi, h, channel: int, window_s: float, fs_hz: int):
    """Sample at ~fs_hz for window_s seconds; return list of volts."""
    n = max(1, int(window_s * fs_hz))
    period = 1.0 / fs_hz

    samples = []
    t_next = time.perf_counter()

    for _ in range(n):
        samples.append(read_mcp3008_volts(spi, h, channel))

        t_next += period
        sleep = t_next - time.perf_counter()
        if sleep > 0:
            time.sleep(sleep)

    return samples


def top_n_mean(values, top_n: int):
    """Mean of the top N values (or fewer if not enough samples)."""
    if not values:
        return None
    top_n = min(top_n, len(values))
    top = sorted(values, reverse=True)[:top_n]
    return statistics.mean(top)


# ==============================
# Main
# ==============================
def main():
    h = None
    spi = None

    try:
        # GPIO for manual CS
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_output(h, CS_GPIO, 1)  # CS idle HIGH

        # SPI
        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEV)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = SPI_MODE
        spi.no_cs = True  # IMPORTANT: we toggle CS via lgpio

        print(f"Sampling CH{ADC_CH} for {WINDOW_S}s @ {FS_HZ}Hz ...")
        samples = sample_window(spi, h, ADC_CH, WINDOW_S, FS_HZ)

        vmax = max(samples)
        vmean = statistics.mean(samples)
        tmean = top_n_mean(samples, TOP_N)

        print(f"Samples: {len(samples)}")
        print(f"Mean voltage: {vmean:.4f} V")
        print(f"Max voltage : {vmax:.4f} V")
        print(f"Top {min(TOP_N, len(samples))} mean: {tmean:.4f} V")

    finally:
        # cleanup
        try:
            if h is not None:
                lgpio.gpio_write(h, CS_GPIO, 1)
        except Exception:
            pass
        try:
            if spi is not None:
                spi.close()
        except Exception:
            pass
        try:
            if h is not None:
                lgpio.gpiochip_close(h)
        except Exception:
            pass


if __name__ == "__main__":
    main()

