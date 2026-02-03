# tests/gate3_termination_check.py
"""
=========================================================
GATE 3 – CAN TERMINATION RESISTOR TEST (peak-based)
=========================================================

- Uses slot_cfg.cs_gpio and slot_cfg.adc_ch from slot_config.SlotConfig
- Sends TERMINATION_ON / TERMINATION_OFF to the selected slot
- Samples CAN_H (MCP3008) for ON and OFF windows
- Computes robust metrics: vmax and mean(top N samples above threshold)
- PASS if OFF has higher peaks than ON by required deltas

Returns:
- True  → PASS
- False → FAIL
"""

import time
import statistics
import spidev
import lgpio

from slot_config import SlotConfig
from tests.CAN.can_commands import termination_on, termination_off

# ==============================
# MCP3008 SPI CONFIG
# ==============================
SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED = 1_000_000
GPIO_CHIP = 0

VREF = 5.0
ADC_MAX = 1023

# ==============================
# TIMING / METRICS
# ==============================
SETTLE_AFTER_CMD_S = 0.5
WINDOW_S = 2.0
FS_HZ = 500
HIGH_THRESH_V = 2.5
TOP_N = 10

# PASS thresholds (relative)
MIN_VMAX_DELTA = 0.12
MIN_TOPMEAN_DELTA = 0.08


# ==============================
# ADC HELPERS (manual CS via lgpio)
# ==============================
def read_mcp3008(spi: spidev.SpiDev, h: int, cs_gpio: int, channel: int):
    """
    Read MCP3008 channel (0..7) using manual CS.
    Returns (raw, volts).
    """
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    lgpio.gpio_write(h, cs_gpio, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, cs_gpio, 1)

    raw = ((rx[1] & 0x03) << 8) | rx[2]
    volts = (raw * VREF) / ADC_MAX
    return raw, volts


def sample_can_h_window(spi: spidev.SpiDev, h: int, cs_gpio: int, channel: int,
                        window_s: float, fs_hz: int):
    """
    Sample ADC at ~fs_hz for window_s. Returns list of volts.
    """
    n = max(1, int(window_s * fs_hz))
    period = 1.0 / fs_hz

    samples = []
    t_next = time.perf_counter()

    for _ in range(n):
        _, v = read_mcp3008(spi, h, cs_gpio, channel)
        samples.append(v)

        t_next += period
        sleep = t_next - time.perf_counter()
        if sleep > 0:
            time.sleep(sleep)

    return samples


def compute_high_metrics(samples_v, high_thresh_v: float, top_n: int):
    """
    Returns dict:
      vmax, top_mean, count_above, pct_above
    top_mean = mean of top N samples among those >= high_thresh_v
    """
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


# =========================================================
# PUBLIC API
# =========================================================
def run_gate3_termination_check(slot_cfg: SlotConfig, log_cb=None) -> bool:
    def log(msg: str):
        (log_cb or print)(msg)

    h = None
    spi = None

    # Pull from config (works even if they are shared defaults)
    cs_gpio = int(getattr(slot_cfg, "cs_gpio", 5))
    adc_ch = int(getattr(slot_cfg, "adc_ch", 0))

    log("=" * 60)
    log(f"[GATE3] Termination test | slot={slot_cfg.slot}")
    log(f"[GATE3] cs_gpio={cs_gpio} adc_ch={adc_ch}")
    log(f"[GATE3] settle={SETTLE_AFTER_CMD_S:.1f}s window={WINDOW_S}s fs={FS_HZ}Hz "
        f"thresh={HIGH_THRESH_V}V topN={TOP_N}")
    log(f"[GATE3] PASS needs OFF>ON: dvmax≥{MIN_VMAX_DELTA:.2f}V and dtopMean≥{MIN_TOPMEAN_DELTA:.2f}V")

    try:
        # ------------------------------
        # INIT GPIO (manual CS) + SPI
        # ------------------------------
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_output(h, cs_gpio, 1)  # default HIGH (inactive)

        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEV)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0
        spi.no_cs = True  # manual CS

        log("[GATE3] SPI + GPIO initialized")

        # ==================================================
        # ON window
        # ==================================================
        log("[GATE3] → TERMINATION_ON")
        termination_on(slot_cfg)
        time.sleep(SETTLE_AFTER_CMD_S)

        samples_on = sample_can_h_window(spi, h, cs_gpio, adc_ch, WINDOW_S, FS_HZ)
        m_on = compute_high_metrics(samples_on, HIGH_THRESH_V, TOP_N)
        log(f"[GATE3] ON : vmax={m_on['vmax']:.3f}V, top{TOP_N}_mean={m_on['top_mean']}, "
            f"above={m_on['count_above']} ({m_on['pct_above']:.1f}%)")

        # ==================================================
        # OFF window
        # ==================================================
        log("[GATE3] → TERMINATION_OFF")
        termination_off(slot_cfg)
        time.sleep(SETTLE_AFTER_CMD_S)

        samples_off = sample_can_h_window(spi, h, cs_gpio, adc_ch, WINDOW_S, FS_HZ)
        m_off = compute_high_metrics(samples_off, HIGH_THRESH_V, TOP_N)
        log(f"[GATE3] OFF: vmax={m_off['vmax']:.3f}V, top{TOP_N}_mean={m_off['top_mean']}, "
            f"above={m_off['count_above']} ({m_off['pct_above']:.1f}%)")

        # ==================================================
        # Decide PASS/FAIL
        # ==================================================
        if m_on["top_mean"] is None or m_off["top_mean"] is None:
            log("[GATE3][FAIL] Not enough 'high' samples to compute top-mean. "
                "Lower HIGH_THRESH_V or ensure bus traffic exists.")
            return False

        dvmax = m_off["vmax"] - m_on["vmax"]
        dtop = m_off["top_mean"] - m_on["top_mean"]

        log(f"[GATE3] Δ metrics: dvmax={dvmax:.3f}V, dtopMean={dtop:.3f}V")

        if dvmax < MIN_VMAX_DELTA:
            log("[GATE3][FAIL] OFF-ON vmax delta too small")
            return False

        if dtop < MIN_TOPMEAN_DELTA:
            log("[GATE3][FAIL] OFF-ON top-mean delta too small")
            return False

        log("[GATE3] PASS — termination change detected")
        return True

    except Exception as e:
        log(f"[GATE3][ERROR] {e}")
        return False

    finally:
        # ------------------------------
        # CLEANUP
        # ------------------------------
        try:
            if h is not None:
                lgpio.gpio_write(h, cs_gpio, 1)
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

        log("[GATE3] SPI + GPIO released")


if __name__ == "__main__":
    # Quick manual smoke test (SlotConfig must exist in your project)
    from slot_config import get_slot_config
    sc = get_slot_config(1)
    ok = run_gate3_termination_check(sc)
    print("\nRESULT:", "PASS ✅" if ok else "FAIL ❌")
