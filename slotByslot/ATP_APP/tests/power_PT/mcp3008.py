# tests/ADC/mcp3008.py
import time
import statistics
import spidev
import lgpio
from typing import List, Dict, Optional

VREF = 5.0
ADC_MAX = 1023

class MCP3008ManualCS:
    def __init__(self, spi_bus: int = 0, spi_dev: int = 0, spi_speed: int = 1_000_000,
                 cs_gpio: int = 5, gpio_chip: int = 0):
        self.cs_gpio = cs_gpio
        self.gpio_chip = gpio_chip

        self.h = lgpio.gpiochip_open(self.gpio_chip)
        lgpio.gpio_claim_output(self.h, self.cs_gpio, 1)  # default HIGH

        self.spi = spidev.SpiDev()
        self.spi.open(spi_bus, spi_dev)
        self.spi.max_speed_hz = spi_speed
        self.spi.mode = 0
        self.spi.no_cs = True  # manual CS

    def close(self):
        try:
            if self.h is not None:
                lgpio.gpio_write(self.h, self.cs_gpio, 1)
        except Exception:
            pass
        try:
            if self.spi is not None:
                self.spi.close()
        except Exception:
            pass
        try:
            if self.h is not None:
                lgpio.gpiochip_close(self.h)
        except Exception:
            pass

    def read(self, channel: int) -> float:
        channel &= 0x07
        tx = [1, (8 + channel) << 4, 0]

        lgpio.gpio_write(self.h, self.cs_gpio, 0)
        rx = self.spi.xfer2(tx)
        lgpio.gpio_write(self.h, self.cs_gpio, 1)

        raw = ((rx[1] & 0x03) << 8) | rx[2]
        volts = raw * VREF / ADC_MAX
        return volts

    def sample_window(self, channel: int, window_s: float, fs_hz: int) -> List[float]:
        n = max(1, int(window_s * fs_hz))
        period = 1.0 / fs_hz

        out = []
        t_next = time.perf_counter()
        for _ in range(n):
            out.append(self.read(channel))
            t_next += period
            sleep = t_next - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
        return out

def compute_high_metrics(samples_v: List[float], high_thresh_v: float, top_n: int) -> Dict:
    if not samples_v:
        return {"vmax": float("nan"), "top_mean": None, "count_above": 0, "pct_above": 0.0}

    vmax = max(samples_v)
    above = [v for v in samples_v if v >= high_thresh_v]
    if not above:
        return {"vmax": vmax, "top_mean": None, "count_above": 0, "pct_above": 0.0}

    above.sort(reverse=True)
    top = above[:min(top_n, len(above))]
    return {
        "vmax": vmax,
        "top_mean": statistics.mean(top),
        "count_above": len(above),
        "pct_above": 100.0 * len(above) / len(samples_v),
    }
