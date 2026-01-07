# SPDX-FileCopyrightText: 2021 ladyada for Adafruit Industries
# SPDX-License-Identifier: MIT

import board
import busio
import digitalio
import time

import adafruit_mcp3xxx.mcp3008 as MCP
from adafruit_mcp3xxx.analog_in import AnalogIn

# ======================================================
# SPI SETUP
# ======================================================
spi = busio.SPI(
    clock=board.SCK,
    MISO=board.MISO,
    MOSI=board.MOSI
)

# Chip Select (CE0 -> GPIO5 / D5)
cs = digitalio.DigitalInOut(board.D5)
cs.direction = digitalio.Direction.OUTPUT
cs.value = True

# ======================================================
# MCP3008 SETUP
# ======================================================
mcp = MCP.MCP3008(spi, cs)

# Analog channel (CH0)
chan = AnalogIn(mcp, MCP.P0)

print("Starting MCP3008 sampling...")
print("Testing sample rates: 100 ms and 250 ms\n")

# ======================================================
# MAIN LOOP
# ======================================================
while True:

    # -------------------------
    # 100 ms sampling
    # -------------------------
    print("\n===== SAMPLING AT 100 ms =====")
    for i in range(100):
        raw = chan.value
        volt = chan.voltage

        print(f"[100 ms] Sample {i+1:02d} | Raw: {raw:6d} | Voltage: {volt:.3f} V")
        time.sleep(0.01)

    # -------------------------
    # 250 ms sampling
    # -------------------------
    print("\n===== SAMPLING AT 250 ms =====")
    for i in range(10):
        raw = chan.value
        volt = chan.voltage

        print(f"[250 ms] Sample {i+1:02d} | Raw: {raw:6d} | Voltage: {volt:.3f} V")
        time.sleep(0.25)

    print("\n---------------------------------------------")
    print("Cycle complete — repeating tests")
    print("---------------------------------------------")
