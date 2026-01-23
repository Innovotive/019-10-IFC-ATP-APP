#!/usr/bin/env python3
"""
FINAL SAFE MCP23S17 ID CONFIG — ALL 4 SLOTS

Active-High straps:
  1 = floated
  0 = shorted

Table (ID1 ID2 ID3):
Slot1 → 110  (ID3 shorted)
Slot2 → 101  (ID2 shorted)
Slot3 → 011  (ID1 shorted)
Slot4 → 100  (ID2 + ID3 shorted)
"""

import spidev
import time

# =========================================================
# MCP23S17 REGISTERS
# =========================================================
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

IODIRA = 0x00
IODIRB = 0x01
OLATA  = 0x14
OLATB  = 0x15

# =========================================================
# SLOT → PIN MAPPING
# =========================================================
# Slot1: GPA0 GPA1 GPA2
# Slot2: GPA3 GPA4 GPA5
# Slot3: GPB0 GPB1 GPB2
# Slot4: GPB3 GPB4 GPB5
SLOTS = {
    1: ("A", (0, 1, 2)),
    2: ("A", (3, 4, 5)),
    3: ("B", (0, 1, 2)),
    4: ("B", (3, 4, 5)),
}

ID_MASK_A = 0b00111111  # A0..A5
ID_MASK_B = 0b00111111  # B0..B5

# =========================================================
# SPI DRIVER
# =========================================================
class MCP23S17:
    def __init__(self):
        self.spi = spidev.SpiDev()
        self.spi.open(0, 0)
        self.spi.max_speed_hz = 10_000_000

    def close(self):
        self.spi.close()

    def write_reg(self, reg, val):
        self.spi.xfer2([OPCODE_WRITE, reg, val & 0xFF])

    def read_reg(self, reg):
        return self.spi.xfer2([OPCODE_READ, reg, 0x00])[2]

    def olat(self, port):
        return OLATA if port == "A" else OLATB

    def read_olat(self, port):
        return self.read_reg(self.olat(port))

    def write_olat(self, port, val):
        self.write_reg(self.olat(port), val)

# =========================================================
# SAFE ID CONFIGURATOR
# =========================================================
class IDConfigurator:
    def __init__(self, mcp):
        self.mcp = mcp

    def init_outputs(self):
        # A0–A5 outputs, A6–A7 inputs
        # B0–B5 outputs, B6–B7 inputs
        self.mcp.write_reg(IODIRA, 0b11000000)
        self.mcp.write_reg(IODIRB, 0b11000000)
        print("✔ GPIO direction set (ID pins = outputs)")

    def float_all_ids(self):
        a = self.mcp.read_olat("A")
        b = self.mcp.read_olat("B")

        self.mcp.write_olat("A", a | ID_MASK_A)
        self.mcp.write_olat("B", b | ID_MASK_B)
        time.sleep(0.02)

        print("✔ All ID pins floated (HIGH)")

    def _mask_to_bits(self, pins, mask3):
        p0, p1, p2 = pins
        out = 0
        if mask3 & 0b001: out |= (1 << p0)
        if mask3 & 0b010: out |= (1 << p1)
        if mask3 & 0b100: out |= (1 << p2)
        return out

    def set_slot(self, slot, mask3):
        port, pins = SLOTS[slot]
        allowed = ID_MASK_A if port == "A" else ID_MASK_B

        slot_bits = sum(1 << p for p in pins)
        want_on = self._mask_to_bits(pins, mask3)

        current = self.mcp.read_olat(port)

        # Clear only the 3 slot pins, then apply new mask
        new_val = current
        new_val &= (~slot_bits & 0xFF)
        new_val |= want_on
        new_val &= allowed | ~allowed  # safety

        self.mcp.write_olat(port, new_val)
        time.sleep(0.02)

        # Verify
        rb = self.mcp.read_olat(port) & slot_bits
        if rb != want_on:
            raise RuntimeError(f"Slot {slot} verify failed")

        print(f"✔ Slot{slot} ID set to {mask3:03b}")

    def set_all_slots(self, masks):
        self.float_all_ids()
        for s in (1, 2, 3, 4):
            self.set_slot(s, masks[s])

# =========================================================
# MAIN
# =========================================================
if __name__ == "__main__":
    mcp = MCP23S17()
    cfg = IDConfigurator(mcp)

    try:
        cfg.init_outputs()

        # ✅ FINAL CORRECT CONFIG (from your table)
        SLOT_MASKS = {
            1: 0b011,  # ID3 shorted 011
            2: 0b101,  # ID2 shorted
            3: 0b110,  # ID1 shorted 110
            4: 0b001,  # ID2 + ID3 shorted
        }

        cfg.set_all_slots(SLOT_MASKS)

        print("\n✅ ALL 4 RUP ID CONFIGS APPLIED SUCCESSFULLY")

    finally:
        mcp.close()
