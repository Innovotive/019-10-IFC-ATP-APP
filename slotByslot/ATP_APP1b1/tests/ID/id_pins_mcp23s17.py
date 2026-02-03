# tests/ID/id_pins_mcp23s17.py
import spidev
from slot_config import SlotConfig

# MCP23S17 SPI OPCODES (A2 A1 A0 = 000)
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

# Registers
IODIRA = 0x00
IODIRB = 0x01
OLATA  = 0x14
OLATB  = 0x15


class IDPins:
    """
    Generic MCP23S17 helper for ID pins across all slots.

    Each slot defines:
      - id_port: "A" or "B"
      - id_pins: tuple of 3 bit positions (e.g. (0,1,2) or (3,4,5))
      - id_baseline_bits: 3-bit pattern [ID3 ID2 ID1] (0..7)
    """

    def __init__(self, bus=0, cs=0, speed_hz=10_000_000):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, cs)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = 0
        self.spi.no_cs = False  # kernel CS

        # Default: all inputs. We'll set per-port bits to outputs when needed.
        self.write_reg(IODIRA, 0xFF)
        self.write_reg(IODIRB, 0xFF)

    def write_reg(self, reg, value):
        self.spi.xfer2([OPCODE_WRITE, reg, value & 0xFF])

    def read_reg(self, reg):
        return self.spi.xfer2([OPCODE_READ, reg, 0x00])[2]

    def _port_regs(self, port: str):
        p = (port or "").upper()
        if p == "A":
            return IODIRA, OLATA
        if p == "B":
            return IODIRB, OLATB
        raise ValueError(f"Invalid port '{port}', expected 'A' or 'B'")

    def _ensure_outputs(self, port: str, pin_bits: tuple):
        iodir_reg, _ = self._port_regs(port)
        cur = self.read_reg(iodir_reg)
        # Set selected pins to output (0)
        for b in pin_bits:
            cur &= ~(1 << int(b))
        self.write_reg(iodir_reg, cur)

    def _set_bits_value(self, port: str, pin_bits: tuple, bits_210: int):
        """
        Write a 3-bit value into the three pin bits.
        bits_210 is [ID3 ID2 ID1] = (ID3<<2 | ID2<<1 | ID1<<0)
        """
        bits_210 &= 0x07
        _, olat_reg = self._port_regs(port)

        cur = self.read_reg(olat_reg)

        # Clear the 3 controlled bits
        mask = 0
        for b in pin_bits:
            mask |= (1 << int(b))
        cur &= ~mask

        # Map bits_210 -> (ID1,ID2,ID3) onto the pin_bits order
        # Convention: pin_bits = (ID1_bit, ID2_bit, ID3_bit)
        id1_bit, id2_bit, id3_bit = [int(x) for x in pin_bits]

        if bits_210 & 0b001:
            cur |= (1 << id1_bit)
        if bits_210 & 0b010:
            cur |= (1 << id2_bit)
        if bits_210 & 0b100:
            cur |= (1 << id3_bit)

        self.write_reg(olat_reg, cur)

    # -------------------------
    # Slot-aware API
    # -------------------------
    def set_slot_baseline(self, slot_cfg: SlotConfig):
        self._ensure_outputs(slot_cfg.id_port, slot_cfg.id_pins)
        self._set_bits_value(slot_cfg.id_port, slot_cfg.id_pins, slot_cfg.id_baseline_bits)

    def clear_slot_pin(self, slot_cfg: SlotConfig, pin_bit: int):
        self._ensure_outputs(slot_cfg.id_port, slot_cfg.id_pins)
        _, olat_reg = self._port_regs(slot_cfg.id_port)
        cur = self.read_reg(olat_reg)
        self.write_reg(olat_reg, cur & ~(1 << int(pin_bit)))

    def set_slot_pin(self, slot_cfg: SlotConfig, pin_bit: int):
        self._ensure_outputs(slot_cfg.id_port, slot_cfg.id_pins)
        _, olat_reg = self._port_regs(slot_cfg.id_port)
        cur = self.read_reg(olat_reg)
        self.write_reg(olat_reg, cur | (1 << int(pin_bit)))

    def close(self):
        try:
            self.spi.close()
        except Exception:
            pass
