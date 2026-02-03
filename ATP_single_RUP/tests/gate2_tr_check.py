# tests/gates/gate2_tr_check.py
import time
import statistics
import spidev
import lgpio

from tests.CAN.can_commands import termination_on, termination_off

SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED = 1_000_000

CS_ADC = 5
GPIO_CHIP = 0

VREF = 5.0
ADC_MAX = 1023
ADC_CH = 0  # CAN_H on CH0

SETTLE_AFTER_CMD_S = 0.5
WINDOW_S = 2.0
FS_HZ = 500
HIGH_THRESH_V = 2.5
TOP_N = 10

MIN_VMAX_DELTA = 0.12
MIN_TOPMEAN_DELTA = 0.08


def read_mcp3008(spi, h, channel: int):
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    lgpio.gpio_write(h, CS_ADC, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_ADC, 1)

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


def run_gate2_termination_check(log_cb=None) -> bool:
    def log(msg: str):
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    h = None
    spi = None

    log("=" * 60)
    log("[ GATE2] Termination test (peak-based via can_commands)")
    log(f"[ GATE2] settle={SETTLE_AFTER_CMD_S:.1f}s window={WINDOW_S}s fs={FS_HZ}Hz thresh={HIGH_THRESH_V}V topN={TOP_N}")
    log(f"[ GATE2] PASS needs OFF>ON: dvmax≥{MIN_VMAX_DELTA:.2f}V and dtopMean≥{MIN_TOPMEAN_DELTA:.2f}V")

    try:
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_output(h, CS_ADC, 1)  # HIGH inactive

        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEV)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0
        spi.no_cs = True

        log("[ GATE2] SPI + GPIO initialized")

        log("[ GATE2] → Sending TERMINATION_ON")
        termination_on()

        log(f"[ GATE2] Waiting {SETTLE_AFTER_CMD_S:.1f}s before measuring ON...")
        time.sleep(SETTLE_AFTER_CMD_S)

        log("[ GATE2] Measuring ON window...")
        samples_on = sample_can_h_window(spi, h, ADC_CH, WINDOW_S, FS_HZ)
        m_on = compute_high_metrics(samples_on, HIGH_THRESH_V, TOP_N)

        log(f"[ GATE2] ON : vmax={m_on['vmax']:.3f}V, top{TOP_N}_mean={m_on['top_mean']}, "
            f"above={m_on['count_above']} ({m_on['pct_above']:.1f}%)")

        log("[ GATE2] → Sending TERMINATION_OFF")
        termination_off()

        log(f"[ GATE2] Waiting {SETTLE_AFTER_CMD_S:.1f}s before measuring OFF...")
        time.sleep(SETTLE_AFTER_CMD_S)

        log("[ GATE2] Measuring OFF window...")
        samples_off = sample_can_h_window(spi, h, ADC_CH, WINDOW_S, FS_HZ)
        m_off = compute_high_metrics(samples_off, HIGH_THRESH_V, TOP_N)

        log(f"[ GATE2] OFF: vmax={m_off['vmax']:.3f}V, top{TOP_N}_mean={m_off['top_mean']}, "
            f"above={m_off['count_above']} ({m_off['pct_above']:.1f}%)")

        if m_on["top_mean"] is None or m_off["top_mean"] is None:
            log("[ GATE2][FAIL] Not enough 'high' samples for top-mean.")
            return False

        dvmax = m_off["vmax"] - m_on["vmax"]
        dtop = m_off["top_mean"] - m_on["top_mean"]

        log(f"[ GATE2] Δ metrics: dvmax={dvmax:.3f}V, dtopMean={dtop:.3f}V")

        if dvmax < MIN_VMAX_DELTA:
            log("[ GATE2][FAIL] OFF-ON vmax delta too small")
            return False

        if dtop < MIN_TOPMEAN_DELTA:
            log("[ GATE2][FAIL] OFF-ON top-mean delta too small")
            return False

        log("[ GATE2] PASS — termination change detected")
        return True

    except Exception as e:
        log(f"[ GATE2][ERROR] Unexpected failure: {e}")
        return False

    finally:
        try:
            if h is not None:
                lgpio.gpio_write(h, CS_ADC, 1)
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

        log("[ GATE2] SPI + GPIO released")
