import time
import spidev
import lgpio

from tests.CAN.can_commands import termination_on
from tests.CAN.can_utils import flush_rx, bus

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
POST_TERM_DELAY_S = 0.3
ACK_TIMEOUT_S = 1.0

# Voltage thresholds (ON only)
TERM_ON_MIN = 2.4
TERM_ON_MAX = 2.6


# ==============================
# ADC HELPERS
# ==============================
def read_mcp3008(spi, h, channel):
    channel &= 0x07
    tx = [1, (8 + channel) << 4, 0]

    lgpio.gpio_write(h, CS_GPIO, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)

    raw = ((rx[1] & 0x03) << 8) | rx[2]
    volts = raw * VREF / ADC_MAX
    return raw, volts


# =========================================================
# GATE 4 (UI COMPATIBLE)
# =========================================================
def run_gate4_termination_check(log_cb=None) -> bool:
    """
    Gate 4 (SAFE MODE):
    - Send TERMINATION_ON
    - Wait briefly
    - Wait for ACK byte 0x83
    - Verify ADC voltage (ON state)
    - TERMINATION_OFF disabled
    """

    def log(msg):
        if log_cb:
            log_cb(msg)
        else:
            print(msg)

    log("\n========== GATE 4 ==========")
    log("ℹ️  TERMINATION_OFF disabled")

    # ------------------------------
    # CAN: clear RX + send command
    # ------------------------------
    flush_rx()
    termination_on()

    time.sleep(POST_TERM_DELAY_S)

    # ------------------------------
    # Wait for ACK (DATA == 0x83)
    # ------------------------------
    ack_seen = False
    deadline = time.time() + ACK_TIMEOUT_S

    while time.time() < deadline:
        msg = bus.recv(timeout=0.1)
        if not msg or not msg.data:
            continue

        log(f"📥 RX | DATA={[hex(b) for b in msg.data]}")

        if msg.data[0] == 0x83:
            ack_seen = True
            break

    if not ack_seen:
        log("❌ GATE 4 FAIL: no TERMINATION_ON ACK (0x83)")
        return False

    log("✅ TERMINATION_ON ACK received")

    # ------------------------------
    # ADC verification (ON state)
    # ------------------------------
    h = None
    spi = None

    try:
        h = lgpio.gpiochip_open(GPIO_CHIP)
        lgpio.gpio_claim_output(h, CS_GPIO, 1)

        spi = spidev.SpiDev()
        spi.open(SPI_BUS, SPI_DEV)
        spi.max_speed_hz = SPI_SPEED
        spi.mode = 0
        spi.no_cs = True

        samples = []
        for i in range(8):
            raw, volts = read_mcp3008(spi, h, ADC_CH)
            samples.append(volts)
            log(f"[GATE4] ADC ON sample {i+1}: RAW={raw} V={volts:.3f}")
            time.sleep(0.05)

        avg_v = sum(samples) / len(samples)
        log(f"[GATE4] ADC ON average: {avg_v:.3f} V")

        if not (TERM_ON_MIN <= avg_v <= TERM_ON_MAX):
            log("❌ GATE 4 FAIL: termination ON voltage out of range")
            return False

    finally:
        try:
            if spi:
                spi.close()
        except Exception:
            pass

        try:
            if h:
                lgpio.gpiochip_close(h)
        except Exception:
            pass

    log("✅ GATE 4 PASS")
    return True


