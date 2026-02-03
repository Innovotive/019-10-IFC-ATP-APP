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

GPIOA  = 0x12
GPIOB  = 0x13


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
        self.spi.max_speed_hz = 500_000

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

    def gpio(self, port):
        return GPIOA if port == "A" else GPIOB

    def read_gpio(self, port):
        return self.read_reg(self.gpio(port))
    
    def dump_regs(mcp, tag=""):
        iodra = mcp.read_reg(IODIRA)
        iodrb = mcp.read_reg(IODIRB)
        olata = mcp.read_reg(OLATA)
        olatb = mcp.read_reg(OLATB)
        gpioa = mcp.read_reg(GPIOA)
        gpiob = mcp.read_reg(GPIOB)
        print(
            f"[{tag}] IODIRA={iodra:08b} IODIRB={iodrb:08b} "
            f"OLATA={olata:08b} OLATB={olatb:08b} "
            f"GPIOA={gpioa:08b} GPIOB={gpiob:08b}"
        )



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
        # mask3 is written as (ID1 ID2 ID3), e.g. 110 means:
        # ID1=1 -> p0 HIGH, ID2=1 -> p1 HIGH, ID3=0 -> p2 LOW
        p0, p1, p2 = pins  # (ID1, ID2, ID3)
        out = 0
        if mask3 & 0b100: out |= (1 << p0)  # MSB -> ID1
        if mask3 & 0b010: out |= (1 << p1)  # mid -> ID2
        if mask3 & 0b001: out |= (1 << p2)  # LSB -> ID3
        return out

    def set_slot(self, slot, mask3):
        port, pins = SLOTS[slot]
        allowed = ID_MASK_A if port == "A" else ID_MASK_B

        slot_bits = sum(1 << p for p in pins) & 0xFF
        want_on = self._mask_to_bits(pins, mask3) & 0xFF
        want_on &= slot_bits

        current = self.mcp.read_olat(port) & 0xFF

        # only change those 3 pins
        new_val = (current & ~slot_bits) | want_on
        new_val &= 0xFF

        # safety: keep non-allowed bits unchanged
        new_val = (current & ~allowed) | (new_val & allowed)
        new_val &= 0xFF

        self.mcp.write_olat(port, new_val)
        time.sleep(0.02)

        rb_olat = self.mcp.read_olat(port) & slot_bits
        if rb_olat != want_on:
            rb_gpio = self.mcp.read_gpio(port) & slot_bits  # if you have it
            raise RuntimeError(
                f"Slot {slot} verify failed: want={want_on:08b} "
                f"got_olat={rb_olat:08b} got_gpio={rb_gpio:08b} "
                f"(slot_bits={slot_bits:08b}, current={current:08b}, new_val={new_val:08b})"
            )

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
        SLOT_MASKS0 = {
            1: 0b000,
            2: 0b000,
            3: 0b000,
            4: 0b000,
        }
    
        # ✅ FINAL CORRECT CONFIG (from your table)
        SLOT_MASKS = {
            1: 0b110,
            2: 0b101,
            3: 0b011,
            4: 0b100,
        }
    
        cfg.set_all_slots(SLOT_MASKS0)

        cfg.set_all_slots(SLOT_MASKS)

        print("\n✅ ALL 4 RUP ID CONFIGS APPLIED SUCCESSFULLY")

    finally:
        mcp.close()
