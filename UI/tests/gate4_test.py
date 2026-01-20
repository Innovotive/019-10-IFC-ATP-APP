"""
=========================================================
GATE 4 – TERMINATION RESISTOR TEST (peak-based, addressed per slot)
=========================================================

Shared CAN bus + per-RUP CAN IDs:
Phase A (baseline):
- Force TERMINATION_OFF on ALL slots (addressed), retry if needed
- Measure BASELINE OFF (peak metrics)

Phase B (per slot):
- For the requested slot:
    - TERMINATION_ON (addressed) -> measure ON
    - TERMINATION_OFF (addressed) -> measure OFF-return
- PASS if BASELINE_OFF has higher peaks than ON by required deltas
  and OFF-return looks like baseline again.

Returns:
- True  → PASS (for this slot)
- False → FAIL (for this slot)
"""

import time
import statistics
import spidev
import lgpio

from tests.CAN.can_commands import set_target_slot, termination_on, termination_off

# ==============================
# ADC + GPIO CONFIG (MCP3008)
# ==============================
SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED = 1_000_000

CS_GPIO = 5
GPIO_CHIP = 0

VREF = 5.0
ADC_MAX = 1023
ADC_CH = 0   # CAN_H on CH0

# ==============================
# TIMING / METRICS
# ==============================
SETTLE_AFTER_CMD_S = 2.5
WINDOW_S = 3.0
FS_HZ = 500
HIGH_THRESH_V = 2.8
TOP_N = 20

# PASS thresholds (relative; BASELINE_OFF should be higher than ON)
MIN_VMAX_DELTA = 0.12
MIN_TOPMEAN_DELTA = 0.08

# Baseline retries
BASELINE_MAX_RETRIES = 2  # in addition to the first attempt


# ==============================
# ADC HELPERS
# ==============================
def read_mcp3008(spi, h, channel: int):
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    lgpio.gpio_write(h, CS_GPIO, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)

    raw = ((rx[1] & 0x03) << 8) | rx[2]
    volts = raw * VREF / ADC_MAX
    return raw, volts


def sample_can_h_window(spi, h, channel: int, window_s: float, fs_hz: int):
    n = max(1, int(window_s * fs_hz))
    period = 1.0 / fs_hz

    samples = []
    t_next = time.perf_counter()

    for _ in range(n):
        _, v = read_mcp3008(spi, h, channel)
        samples.append(v)

        t_next += period
        sleep = t_next - time.perf_counter()
        if sleep > 0:
            time.sleep(sleep)

    return samples


def compute_high_metrics(samples_v, high_thresh_v: float, top_n: int):
    """
    Returns dict: vmax, top_mean, count_above, pct_above
    top_mean = mean(top N samples among those >= high_thresh_v)
    """
    if not samples_v:
        return {"vmax": float("nan"), "top_mean": None, "count_above": 0, "pct_above": 0.0}

    vmax = max(samples_v)
    above = [v for v in samples_v if v >= high_thresh_v]

    if not above:
        return {"vmax": vmax, "top_mean": None, "count_above": 0, "pct_above": 0.0}

    above.sort(reverse=True)
    top = above[:min(top_n, len(above))]
    top_mean = statistics.mean(top)

    return {
        "vmax": vmax,
        "top_mean": top_mean,
        "count_above": len(above),
        "pct_above": 100.0 * len(above) / len(samples_v),
    }


# ==============================
# CAN HELPERS
# ==============================
def _termination_off_all(log):
    """Send TERMINATION_OFF to all 4 slots (addressed)."""
    for s in (1, 2, 3, 4):
        set_target_slot(s)
        termination_off()
        time.sleep(0.05)


# =========================================================
# PUBLIC API — CALLED BY RUNNER (per slot)
# =========================================================
def run_gate4_termination_check(slot: int, log_cb=None) -> bool:
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    h = None
    spi = None

    log("=" * 60)
    log(f"[GATE4] Slot={slot} — Termination test (shared bus, addressed CAN)")
    log(f"[GATE4] settle={SETTLE_AFTER_CMD_S:.1f}s window={WINDOW_S}s fs={FS_HZ}Hz thresh={HIGH_THRESH_V}V topN={TOP_N}")
    log(f"[GATE4] PASS needs BASE-ON: dvmax≥{MIN_VMAX_DELTA:.2f}V and dtopMean≥{MIN_TOPMEAN_DELTA:.2f}V")

    try:
        # ------------------------------
        # INIT GPIO (manual CS) + SPI
        # ------------------------------
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_output(h, CS_GPIO, 1)  # CS high (inactive)

        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEV)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0
        spi.no_cs = True  # manual CS

        log("[GATE4] SPI + GPIO initialized")

        # ==================================================
        # PHASE A: GLOBAL OFF BASELINE (with retries)
        # ==================================================
        m_base = None
        for attempt in range(0, BASELINE_MAX_RETRIES + 1):
            log(f"[GATE4] → Forcing TERMINATION_OFF on ALL RUPs (attempt {attempt+1}/{BASELINE_MAX_RETRIES+1})")
            _termination_off_all(log)

            log(f"[GATE4] Waiting {SETTLE_AFTER_CMD_S:.1f}s before measuring BASELINE OFF...")
            time.sleep(SETTLE_AFTER_CMD_S)

            log("[GATE4] Measuring BASELINE OFF window...")
            samples_base = sample_can_h_window(spi, h, ADC_CH, WINDOW_S, FS_HZ)
            m_base = compute_high_metrics(samples_base, HIGH_THRESH_V, TOP_N)

            log(
                f"[GATE4] BASE: vmax={m_base['vmax']:.3f}V, top{TOP_N}_mean={m_base['top_mean']}, "
                f"above={m_base['count_above']} ({m_base['pct_above']:.1f}%)"
            )

            # Baseline must have enough "high" samples to compute top_mean (or your metric can't work)
            if m_base["top_mean"] is not None:
                break

            if attempt == BASELINE_MAX_RETRIES:
                log("[GATE4][FAIL] Baseline OFF invalid: not enough 'high' samples to compute top-mean.")
                log("[GATE4][HINT] Lower HIGH_THRESH_V (2.7–2.9) or ensure bus traffic exists.")
                return False

        # ==================================================
        # PHASE B: TEST THIS SLOT (ON then OFF)
        # ==================================================
        # --- ON (addressed)
        log(f"[GATE4] → Slot {slot}: Sending TERMINATION_ON (addressed)")
        set_target_slot(slot)
        termination_on()

        log(f"[GATE4] Waiting {SETTLE_AFTER_CMD_S:.1f}s before measuring ON...")
        time.sleep(SETTLE_AFTER_CMD_S)

        log("[GATE4] Measuring ON window...")
        samples_on = sample_can_h_window(spi, h, ADC_CH, WINDOW_S, FS_HZ)
        m_on = compute_high_metrics(samples_on, HIGH_THRESH_V, TOP_N)

        log(
            f"[GATE4] ON : vmax={m_on['vmax']:.3f}V, top{TOP_N}_mean={m_on['top_mean']}, "
            f"above={m_on['count_above']} ({m_on['pct_above']:.1f}%)"
        )

        if m_on["top_mean"] is None:
            log("[GATE4][FAIL] ON invalid: not enough 'high' samples to compute top-mean.")
            return False

        # Compare BASELINE_OFF -> ON deltas (BASE should be higher than ON)
        dvmax = m_base["vmax"] - m_on["vmax"]
        dtop = m_base["top_mean"] - m_on["top_mean"]

        log(f"[GATE4] Δ (BASE - ON): dvmax={dvmax:.3f}V, dtopMean={dtop:.3f}V")

        if dvmax < MIN_VMAX_DELTA:
            log("[GATE4][FAIL] BASE-ON vmax delta too small")
            return False

        if dtop < MIN_TOPMEAN_DELTA:
            log("[GATE4][FAIL] BASE-ON top-mean delta too small")
            return False

        # --- OFF again (addressed) and verify return-to-baseline
        log(f"[GATE4] → Slot {slot}: Sending TERMINATION_OFF (addressed)")
        set_target_slot(slot)
        termination_off()

        log(f"[GATE4] Waiting {SETTLE_AFTER_CMD_S:.1f}s before measuring OFF-return...")
        time.sleep(SETTLE_AFTER_CMD_S)

        log("[GATE4] Measuring OFF-return window...")
        samples_off2 = sample_can_h_window(spi, h, ADC_CH, WINDOW_S, FS_HZ)
        m_off2 = compute_high_metrics(samples_off2, HIGH_THRESH_V, TOP_N)

        log(
            f"[GATE4] OFF2: vmax={m_off2['vmax']:.3f}V, top{TOP_N}_mean={m_off2['top_mean']}, "
            f"above={m_off2['count_above']} ({m_off2['pct_above']:.1f}%)"
        )

        # Return-to-baseline sanity: OFF2 should be closer to BASE than to ON in top_mean
        if m_off2["top_mean"] is None:
            log("[GATE4][WARN] OFF-return top_mean missing; skipping strict return-to-baseline check.")
        else:
            dist_base = abs(m_off2["top_mean"] - m_base["top_mean"])
            dist_on = abs(m_off2["top_mean"] - m_on["top_mean"])
            log(f"[GATE4] Return check: |OFF2-BASE|={dist_base:.3f}, |OFF2-ON|={dist_on:.3f}")
            if dist_base > dist_on:
                log("[GATE4][FAIL] OFF-return does not look like baseline (may still be terminating).")
                return False

        log("[GATE4] PASS — addressed termination toggled + returned to baseline")
        return True

    except Exception as e:
        log(f"[GATE4][ERROR] Unexpected failure: {e}")
        return False

    finally:
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

        log("[GATE4] SPI + GPIO released")


# if __name__ == "__main__":
#     # Manual single-slot debug run (runner will call slot 1..4 during ATP)
#     ok = run_gate4_termination_check(slot=1)
#     print("\nRESULT:", "PASS ✅" if ok else "FAIL ❌")
