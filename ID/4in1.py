#Author: Sirine Bouhoula
#!/usr/bin/env python3
import spidev
import time

# =========================================================
# MCP23S17 SPI CONFIG
# =========================================================
OPCODE_WRITE = 0x40   # A2 A1 A0 = 000
OPCODE_READ  = 0x41

IODIRA = 0x00
IODIRB = 0x01
OLATA  = 0x14
OLATB  = 0x15

# Slot -> pins mapping (3 ID pins per slot)
# Slot1: GPA0,GPA1,GPA2
# Slot2: GPA3,GPA4,GPA5
# Slot3: GPB0,GPB1,GPB2
# Slot4: GPB3,GPB4,GPB5
SLOTS = {
    1: {"port": "A", "pins": (0, 1, 2)},
    2: {"port": "A", "pins": (3, 4, 5)},
    3: {"port": "B", "pins": (0, 1, 2)},
    4: {"port": "B", "pins": (3, 4, 5)},
}

# =========================================================
# SPI SETUP
# =========================================================
spi = spidev.SpiDev()
spi.open(0, 0)  # SPI bus 0, CE0
spi.max_speed_hz = 10_000_000

def write_reg(reg: int, value: int) -> None:
    spi.xfer2([OPCODE_WRITE, reg, value & 0xFF])

def read_reg(reg: int) -> int:
    return spi.xfer2([OPCODE_READ, reg, 0x00])[2]

# =========================================================
# INIT: configure A0..A5 and B0..B5 as outputs
# keep A6,A7 and B6,B7 as inputs
# =========================================================
write_reg(IODIRA, 0b11000000)  # 1=input (A6,A7), 0=output (A0..A5)
write_reg(IODIRB, 0b11000000)  # 1=input (B6,B7), 0=output (B0..B5)

print("✔ MCP23S17: A0..A5 and B0..B5 configured as outputs (A6,A7,B6,B7 inputs)")

# =========================================================
# Helpers for OLAT A/B
# =========================================================
def _olat_reg(port: str) -> int:
    return OLATA if port.upper() == "A" else OLATB

def port_write(port: str, value: int) -> None:
    write_reg(_olat_reg(port), value)

def port_read(port: str) -> int:
    return read_reg(_olat_reg(port))

def set_pin(port: str, pin: int) -> None:
    val = port_read(port)
    port_write(port, val | (1 << pin))

def clear_pin(port: str, pin: int) -> None:
    val = port_read(port)
    port_write(port, val & ~(1 << pin))

# =========================================================
# Slot-level API
# mask is 3 bits: bit0->first pin, bit1->second pin, bit2->third pin
# Active-high: 1 = floated/ON, 0 = shorted/OFF
# =========================================================
def set_slot_id_mask(slot: int, mask3: int) -> None:
    if slot not in SLOTS:
        raise ValueError("slot must be 1..4")
    mask3 &= 0b111

    port = SLOTS[slot]["port"]
    p0, p1, p2 = SLOTS[slot]["pins"]

    # Clear the 3 pins then apply new mask
    val = port_read(port)
    clear_mask = ~((1 << p0) | (1 << p1) | (1 << p2)) & 0xFF
    val = val & clear_mask

    # Apply mask bits to the 3 pins
    if mask3 & 0b001: val |= (1 << p0)
    if mask3 & 0b010: val |= (1 << p1)
    if mask3 & 0b100: val |= (1 << p2)

    port_write(port, val)

def set_all_slots_floated() -> None:
    """
    Default: set every ID line (A0..A5 and B0..B5) to 1 (floated/ON).
    Keeps A6,A7,B6,B7 unchanged.
    """
    a = port_read("A")
    b = port_read("B")

    # Set A0..A5 to 1
    a |= 0b00111111
    # Set B0..B5 to 1
    b |= 0b00111111

    port_write("A", a)
    port_write("B", b)
    print("✔ Default ID lines set HIGH (floated) for all 4 slots")

# =========================================================
# Demo (matches your “turn on then turn off some pins” style)
# =========================================================
if __name__ == "__main__":
    try:
        print("\n=== ACTIVE-HIGH MODE (ALL SLOTS) ===")
        set_all_slots_floated()
        time.sleep(1)

        # Set each slot mask (example defaults to 111 for all)
        # 111 = all floated, 110 means first pin shorted (bit0=0), etc.
        set_slot_id_mask(1, 0b111)
        set_slot_id_mask(2, 0b111)
        set_slot_id_mask(3, 0b111)
        set_slot_id_mask(4, 0b111)
        print("✔ Slot1..4 set to 111 (all floated)")
        time.sleep(2)

        # Now reproduce the “turn off some pins” behavior:
        # Slot1: clear ID1 (GPA0) then clear ID2 (GPA1)
        print("Slot1: OFF ID1 (GPA0) -> mask 110")
        set_slot_id_mask(1, 0b110)
        time.sleep(2)

        print("Slot1: OFF ID2 (GPA1) -> mask 100")
        set_slot_id_mask(1, 0b100)
        time.sleep(2)

        # Slot2: clear GPA3 then GPA5 (like your code #2)
        print("Slot2: OFF GPA3 -> mask 110")
        set_slot_id_mask(2, 0b110)
        time.sleep(2)

        print("Slot2: OFF GPA5 -> mask 010")
        set_slot_id_mask(2, 0b010)
        time.sleep(2)

        # Slot3: clear GPB1 then GPB2 (like your code #3)
        print("Slot3: OFF GPB1 -> mask 101")
        set_slot_id_mask(3, 0b101)
        time.sleep(2)

        print("Slot3: OFF GPB2 -> mask 001")
        set_slot_id_mask(3, 0b001)
        time.sleep(2)

        # Slot4: your code comment says "Turning OFF ID5 (GPB4)" but you clear_pin(3)
        # GPB3 is pin 3. If you meant GPB3, this is correct:
        print("Slot4: OFF GPB3 -> mask 110")
        set_slot_id_mask(4, 0b110)
        time.sleep(2)

        print("\nDone.")

    except KeyboardInterrupt:
        print("\nStopped by user.")
    finally:
        spi.close()
