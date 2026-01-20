#!/usr/bin/env python3
import time
import threading
import can
import spidev
import lgpio

# ==============================
# CAN CONFIG (socketcan)
# ==============================
CAN_CHANNEL = "can0"
CAN_ID = 0x100
CAN_DATA = [0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07, 0x08]

# Control how hard you load the bus:
CAN_SEND_HZ = 1500          # try 200, 500, 1000, 1500...
CAN_BACKOFF_S = 0.0005      # when TX buffer is full

# ==============================
# ADC CONFIG (MCP3008)
# ==============================
SPI_BUS = 0
SPI_DEV = 0
SPI_SPEED = 1_000_000       # start 1MHz. You can try 2-10MHz later.
SPI_MODE = 0

CS_GPIO = 5
GPIO_CHIP = 0

CH_H = 0  # CAN_H -> CH0
CH_L = 1  # CAN_L -> CH1

VREF = 5.0
ADC_MAX = 1023.0

# Dominant detection threshold:
# On a real CAN bus, dominant Vdiff is often ~1.5–2.5V.
VDIFF_DOM_THRESHOLD = 1.0   # safe starting point

# Reporting window
REPORT_EVERY_S = 1.0

# ==============================
# Shared stop flag
# ==============================
stop_event = threading.Event()


# ==============================
# MCP3008 Read (manual CS)
# ==============================
def setup_adc():
    h = lgpio.gpiochip_open(GPIO_CHIP)
    lgpio.gpio_claim_output(h, CS_GPIO, 1)  # CS idle HIGH

    spi = spidev.SpiDev()
    spi.open(SPI_BUS, SPI_DEV)
    spi.max_speed_hz = SPI_SPEED
    spi.mode = SPI_MODE
    spi.no_cs = True
    return h, spi

def read_mcp3008(h, spi, channel: int) -> int:
    tx = [1, (8 + (channel & 7)) << 4, 0]
    lgpio.gpio_write(h, CS_GPIO, 0)
    rx = spi.xfer2(tx)
    lgpio.gpio_write(h, CS_GPIO, 1)
    return ((rx[1] & 0x03) << 8) | rx[2]

def raw_to_v(raw: int) -> float:
    return (raw * VREF) / ADC_MAX


# ==============================
# CAN Sender Thread
# ==============================
def can_sender():
    bus = can.interface.Bus(channel=CAN_CHANNEL, interface="socketcan")
    msg = can.Message(arbitration_id=CAN_ID, data=CAN_DATA, is_extended_id=False)

    period = 1.0 / CAN_SEND_HZ
    next_t = time.perf_counter()

    try:
        while not stop_event.is_set():
            # pace the sender (keeps load high but avoids instant ENOBUFS spam)
            next_t += period
            try:
                bus.send(msg)
            except can.CanOperationError:
                time.sleep(CAN_BACKOFF_S)

            # sleep to the next tick (if we are ahead)
            sleep = next_t - time.perf_counter()
            if sleep > 0:
                time.sleep(sleep)
    finally:
        bus.shutdown()


# ==============================
# ADC Dominant Detector (main)
# ==============================
def adc_dominant_loop():
    h, spi = setup_adc()

    # Stats
    total = 0
    dominant = 0
    vh_min, vh_max = 9e9, -9e9
    vl_min, vl_max = 9e9, -9e9
    vdiff_min, vdiff_max = 9e9, -9e9

    t_report = time.perf_counter()

    try:
        while not stop_event.is_set():
            # Read both lines (single-ended), compute differential
            rh = read_mcp3008(h, spi, CH_H)
            rl = read_mcp3008(h, spi, CH_L)

            vh = raw_to_v(rh)
            vl = raw_to_v(rl)
            vdiff = vh - vl

            total += 1
            if vdiff >= VDIFF_DOM_THRESHOLD:
                dominant += 1

            # Track min/max
            vh_min = min(vh_min, vh); vh_max = max(vh_max, vh)
            vl_min = min(vl_min, vl); vl_max = max(vl_max, vl)
            vdiff_min = min(vdiff_min, vdiff); vdiff_max = max(vdiff_max, vdiff)

            # Periodic report
            now = time.perf_counter()
            if now - t_report >= REPORT_EVERY_S:
                dom_pct = (dominant / total) * 100.0 if total else 0.0
                samp_rate = total / (now - t_report)

                print(
                    f"sps={samp_rate:7.0f} | dominant={dom_pct:5.1f}% (Vdiff>{VDIFF_DOM_THRESHOLD:.1f}V) | "
                    f"Vh[{vh_min:.2f},{vh_max:.2f}] Vl[{vl_min:.2f},{vl_max:.2f}] Vdiff[{vdiff_min:.2f},{vdiff_max:.2f}]"
                )

                # reset window stats
                total = 0
                dominant = 0
                vh_min, vh_max = 9e9, -9e9
                vl_min, vl_max = 9e9, -9e9
                vdiff_min, vdiff_max = 9e9, -9e9
                t_report = now

    finally:
        spi.close()
        lgpio.gpiochip_close(h)


# ==============================
# MAIN
# ==============================
if __name__ == "__main__":
    print("Starting CAN TX load + ADC dominant detector (Ctrl+C to stop)")
    print(f"CAN_SEND_HZ={CAN_SEND_HZ}, SPI_SPEED={SPI_SPEED}, VDIFF_DOM_THRESHOLD={VDIFF_DOM_THRESHOLD}")

    t = threading.Thread(target=can_sender, daemon=True)
    t.start()

    try:
        adc_dominant_loop()
    except KeyboardInterrupt:
        print("\nStopping...")
    finally:
        stop_event.set()
        t.join(timeout=1.0)
