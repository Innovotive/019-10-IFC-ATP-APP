"""
=========================================================
GATE 4 – TERMINATION RESISTOR FUNCTIONAL TEST
=========================================================

Test logic:
- Send CAN TERMINATION_ON
- ADC voltage must drop to ~2.35 V
- Send CAN TERMINATION_OFF
- ADC voltage must rise to ~2.50 V

Returns:
- True  → PASS
- False → FAIL
"""

import time
import spidev
import lgpio

from tests.CAN.can_commands import termination_on, termination_off

# ==============================
# ADC + GPIO CONFIG
# ==============================
SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED = 1_000_000

CS_GPIO = 5
GPIO_CHIP = 0

VREF = 5.0
ADC_MAX = 1023
ADC_CH = 0

# Timing
SETTLE_TIME = 0.3
READ_SAMPLES = 8
READ_DELAY = 0.05

# Voltage thresholds (based on real data)
TERM_ON_MIN  = 2.25
TERM_ON_MAX  = 2.40
TERM_OFF_MIN = 2.45
TERM_OFF_MAX = 2.60


# ==============================
# ADC HELPERS
# ==============================
def read_mcp3008(spi, h, channel):
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    # Manual CS using lgpio
    lgpio.gpio_write(h, CS_GPIO, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)

    raw = ((rx[1] & 0x03) << 8) | rx[2]
    volts = raw * VREF / ADC_MAX
    return raw, volts


def read_adc_stable(spi, h, channel):
    raw, volts = 0, 0.0
    for _ in range(READ_SAMPLES):
        raw, volts = read_mcp3008(spi, h, channel)
        time.sleep(READ_DELAY)
    return raw, volts


# =========================================================
# PUBLIC API — CALLED BY UI LATER
# =========================================================
def run_gate4_termination_check(log_cb=None):

    def log(msg):
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    h = None
    spi = None

    log("=" * 50)
    log("[GATE4] Starting termination resistor test")
    log("[GATE4] Expected ranges:")
    log(f"         ON  → {TERM_ON_MIN:.2f}–{TERM_ON_MAX:.2f} V")
    log(f"         OFF → {TERM_OFF_MIN:.2f}–{TERM_OFF_MAX:.2f} V")

    try:
        # ------------------------------
        # INIT GPIO (manual CS) + SPI
        # ------------------------------
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_output(h, CS_GPIO, 1)  # default HIGH (inactive)

        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEV)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0
        spi.no_cs = True  # IMPORTANT: we are controlling CS manually via lgpio

        log("[GATE4] SPI + GPIO initialized")

        # ==================================================
        # TERMINATION ON
        # ==================================================
        log("[GATE4] → Sending TERMINATION_ON (0x81)")
        termination_on()
        log(f"[GATE4] Waiting {SETTLE_TIME}s for voltage to settle")
        time.sleep(SETTLE_TIME)

        samples = []
        for i in range(READ_SAMPLES):
            raw, volts = read_mcp3008(spi, h, ADC_CH)
            samples.append(volts)
            log(f"[GATE4] ADC ON sample {i+1}: RAW={raw} V={volts:.3f}")
            time.sleep(READ_DELAY)

        avg_v = sum(samples) / len(samples)
        log(f"[GATE4] ADC ON average: {avg_v:.3f} V")

        if not (TERM_ON_MIN <= avg_v <= TERM_ON_MAX):
            log("[GATE4][FAIL] Termination ON voltage OUT OF RANGE")
            return False

        log("[GATE4] TERMINATION_ON PASS")

        # ==================================================
        # TERMINATION OFF
        # ==================================================
        log("[GATE4] → Sending TERMINATION_OFF (0x80)")
        termination_off()
        log(f"[GATE4] Waiting {SETTLE_TIME}s for voltage to settle")
        time.sleep(SETTLE_TIME)

        samples = []
        for i in range(READ_SAMPLES):
            raw, volts = read_mcp3008(spi, h, ADC_CH)
            samples.append(volts)
            log(f"[GATE4] ADC OFF sample {i+1}: RAW={raw} V={volts:.3f}")
            time.sleep(READ_DELAY)

        avg_v = sum(samples) / len(samples)
        log(f"[GATE4] ADC OFF average: {avg_v:.3f} V")

        if not (TERM_OFF_MIN <= avg_v <= TERM_OFF_MAX):
            log("[GATE4][FAIL] Termination OFF voltage OUT OF RANGE")
            return False

        log("[GATE4] TERMINATION_OFF PASS")
        log("[GATE4] PASS — termination resistor functional")
        return True

    except Exception as e:
        log(f"[GATE4][ERROR] Unexpected failure: {e}")
        return False

    finally:
        # ------------------------------
        # GUARANTEED CLEANUP
        # ------------------------------
        try:
            if h is not None:
                # Make sure CS is inactive-high before releasing
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

