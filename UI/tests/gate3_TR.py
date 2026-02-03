# tests/gate3_TR.py
#!/usr/bin/env python3
"""
GATE3 — TR test in ONE global sequence (ordered, timing-stable)

What changed vs your version (timing fixes):
- Adds TRANSIENT_DISCARD_S: we sample a window but IGNORE the first part (switching transient)
- Separates timing into:
    CMD_QUIET_S   : small pause right after CAN command (firmware/apply jitter)
    SETTLE_S      : stabilize time BEFORE sampling
    WINDOW_S      : total sampling window
- Uses a single "measure_state" helper that always does: set TR -> quiet -> settle -> sample -> discard -> metric
- Keeps keeper logic:
    - Slots 1..3 tested with Slot4 as keeper ON
    - Slot4 tested with Slot2 as keeper2 ON while Slot4 toggles

Returns dict {1: bool, 2: bool, 3: bool, 4: bool}
Does NOT abort if one slot fails.
"""

import time
import statistics
import spidev
import lgpio

from tests.CAN.can_commands import set_target_slot, termination_on, termination_off

# ==============================
# ADC (MCP3008)
# ==============================
SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED = 1_000_000

CS_GPIO = 5
GPIO_CHIP = 0

VREF = 5.0
ADC_MAX = 1023
ADC_CH = 0

# ==============================
# TIMING (tuned for stability)
# ==============================
CMD_QUIET_S = 0.20          # let RUP apply TR command / reduce immediate transient
SETTLE_S = 1.20             # settle BEFORE sampling (shorter than your 2.5s)
WINDOW_S = 3.00             # total sampling window
FS_HZ = 500

TRANSIENT_DISCARD_S = 0.50  # ignore first 0.5s of WINDOW (switching transient)

# Metric: mean of samples above threshold (same as you, but on stable samples)
PEAK_THRESH_V = 3.0

# expected ranges (adjust if needed)
LOW_EXPECT  = (2.45, 3.75)   # ~3.6V
HIGH_EXPECT = (3.75, 4.05)   # ~3.8-3.9V

KEEPER_SLOT = 4
KEEPER2_SLOT = 2


def log_default(msg: str):
    print(msg)


def _read_mcp3008(spi, h, channel: int) -> float:
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    lgpio.gpio_write(h, CS_GPIO, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)

    raw = ((rx[1] & 0x03) << 8) | rx[2]
    return raw * VREF / ADC_MAX


def _sample_window(spi, h, channel: int, window_s: float, fs_hz: int):
    n = max(1, int(window_s * fs_hz))
    period = 1.0 / fs_hz
    out = []
    t_next = time.perf_counter()
    for _ in range(n):
        out.append(_read_mcp3008(spi, h, channel))
        t_next += period
        dt = t_next - time.perf_counter()
        if dt > 0:
            time.sleep(dt)
    return out


def _peak_mean(samples, thresh: float):
    if not samples:
        return None, 0, float("nan")
    peaks = [v for v in samples if v >= thresh]
    vmax = max(samples)
    if not peaks:
        return None, 0, vmax
    return statistics.mean(peaks), len(peaks), vmax


def _in_range(x, lo, hi):
    return x is not None and lo <= x <= hi


def _tr_on(slot: int):
    set_target_slot(slot)
    termination_on()
    time.sleep(CMD_QUIET_S)


def _tr_off(slot: int):
    set_target_slot(slot)
    termination_off()
    time.sleep(CMD_QUIET_S)


def _normalize_keeper_only(log):
    # TR ON Slot4, OFF Slot1/2/3
    log("[GATE3] Normalize: TR ON Slot4, TR OFF Slot1/2/3")
    _tr_on(KEEPER_SLOT)
    _tr_off(1)
    _tr_off(2)
    _tr_off(3)


def _measure_stable(spi, h, name: str, log):
    samples = _sample_window(spi, h, ADC_CH, WINDOW_S, FS_HZ)

    discard_n = int(TRANSIENT_DISCARD_S * FS_HZ)
    stable = samples[discard_n:] if len(samples) > discard_n else samples

    pm, n, vmax = _peak_mean(stable, PEAK_THRESH_V)
    log(
        f"[GATE3] {name}: peak_mean={pm}, peaks={n}, vmax={vmax:.3f}V "
        f"(stable={WINDOW_S-TRANSIENT_DISCARD_S:.2f}s, discard={TRANSIENT_DISCARD_S:.2f}s)"
    )
    return pm, n, vmax


def _set_tr_and_measure(spi, h, slot: int, tr_on: bool, label: str, log):
    """
    Timing-stable measurement:
      set TR -> settle -> sample -> discard transient -> metric
    """
    if tr_on:
        _tr_on(slot)
    else:
        _tr_off(slot)

    log(f"[GATE3] Waiting settle {SETTLE_S:.2f}s before sampling...")
    time.sleep(SETTLE_S)

    return _measure_stable(spi, h, label, log)


def _test_slot_1to3(slot: int, spi, h, log):
    """
    SlotX ON => LOW, SlotX OFF => HIGH (keeper Slot4 stays ON)
    """
    # Ensure keeper-only before starting this slot test
    _normalize_keeper_only(log)
    log(f"[GATE3] Waiting settle {SETTLE_S:.2f}s (post-normalize)...")
    time.sleep(SETTLE_S)

    log(f"[GATE3] → Slot{slot}: TR ON (expect LOW)")
    pm_on, n_on, vmax_on = _set_tr_and_measure(
        spi, h, slot, True, f"Slot{slot} ON", log
    )

    log(f"[GATE3] → Slot{slot}: TR OFF (expect HIGH)")
    pm_off, n_off, vmax_off = _set_tr_and_measure(
        spi, h, slot, False, f"Slot{slot} OFF", log
    )

    ok_low = _in_range(pm_on, *LOW_EXPECT)
    ok_high = _in_range(pm_off, *HIGH_EXPECT)

    if ok_low and ok_high:
        log(f"[GATE3] Slot{slot} PASS ✅")
        return True

    log(f"[GATE3][FAIL] Slot{slot}: ok_low={ok_low}, ok_high={ok_high}")
    # extra debug hints
    log(f"[GATE3][DBG] Slot{slot} ON:  pm={pm_on} peaks={n_on} vmax={vmax_on:.3f}V")
    log(f"[GATE3][DBG] Slot{slot} OFF: pm={pm_off} peaks={n_off} vmax={vmax_off:.3f}V")
    return False


def _test_slot4(spi, h, log):
    """
    Slot4 OFF => HIGH, Slot4 ON => LOW, safely:
    keep Slot2 ON while toggling Slot4
    """
    # Start from keeper-only
    _normalize_keeper_only(log)
    log(f"[GATE3] Waiting settle {SETTLE_S:.2f}s (post-normalize)...")
    time.sleep(SETTLE_S)

    log("[GATE3] → Slot4 test: ensure Slot2 TR ON (keeper2)")
    _tr_on(KEEPER2_SLOT)
    log(f"[GATE3] Waiting settle {SETTLE_S:.2f}s (keeper2)...")
    time.sleep(SETTLE_S)

    log("[GATE3] → Slot4: TR OFF (expect HIGH)")
    pm_high, n_high, vmax_high = _set_tr_and_measure(
        spi, h, 4, False, "Slot4 OFF", log
    )

    log("[GATE3] → Slot4: TR ON (expect LOW)")
    pm_low, n_low, vmax_low = _set_tr_and_measure(
        spi, h, 4, True, "Slot4 ON", log
    )

    ok_high = _in_range(pm_high, *HIGH_EXPECT)
    ok_low = _in_range(pm_low, *LOW_EXPECT)

    if ok_high and ok_low:
        log("[GATE3] Slot4 PASS ✅")
        return True

    log(f"[GATE3][FAIL] Slot4: ok_high={ok_high}, ok_low={ok_low}")
    log(f"[GATE3][DBG] Slot4 OFF: pm={pm_high} peaks={n_high} vmax={vmax_high:.3f}V")
    log(f"[GATE3][DBG] Slot4 ON:  pm={pm_low} peaks={n_low} vmax={vmax_low:.3f}V")
    return False


def run_gate3_all_ordered(log_cb=None):
    log = log_cb or log_default

    results = {1: False, 2: False, 3: False, 4: False}
    h = None
    spi = None

    log("============================================================")
    log("[GATE3] ONE-SHOT ordered run across Slot1..Slot4")
    log(
        f"[GATE3] cmd_quiet={CMD_QUIET_S}s settle={SETTLE_S}s "
        f"window={WINDOW_S}s discard={TRANSIENT_DISCARD_S}s fs={FS_HZ}Hz "
        f"peak_thresh={PEAK_THRESH_V}V"
    )
    log(f"[GATE3] LOW={LOW_EXPECT}, HIGH={HIGH_EXPECT}")

    try:
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_output(h, CS_GPIO, 1)

        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEV)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0
        spi.no_cs = True

        log("[GATE3] SPI + GPIO initialized")

        # Slots 1..3
        for s in (1, 2, 3):
            results[s] = _test_slot_1to3(s, spi, h, log)

        # Slot 4 special
        results[4] = _test_slot4(spi, h, log)

        return results

    finally:
        # End state you want: Slot2 ON + Slot4 ON, Slot1/3 OFF
        try:
            log("[GATE3] Finish: keep TR ON Slot2 + Slot4 (2 terminations), others OFF")
            _tr_off(1)
            _tr_off(3)
            _tr_on(2)
            _tr_on(4)
        except Exception:
            pass

        try:
            if spi:
                spi.close()
        except Exception:
            pass
        try:
            if h is not None:
                lgpio.gpiochip_close(h)
        except Exception:
            pass

        log("[GATE3] SPI + GPIO released")


# Compatibility per-slot API (still runs the global ordered test)
def run_gate3_termination_check(slot: int, log_cb=None) -> bool:
    res = run_gate3_all_ordered(log_cb=log_cb)
    return bool(res.get(slot, False))


if __name__ == "__main__":
    r = run_gate3_all_ordered()
    print("\nRESULTS:", r)
