import spidev

# MCP23S17 SPI OPCODES (A2 A1 A0 = 000)
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

# Port B registers
IODIRB = 0x01
OLATB  = 0x15

class IDPins:
    # Use GPB3, GPB4, GPB5
    ID1_PIN = 3  # GPB3
    ID2_PIN = 4  # GPB4
    ID3_PIN = 5  # GPB5

    # Mask of the 3 bits we control (bits 3..5)
    ID_MASK = (1 << ID1_PIN) | (1 << ID2_PIN) | (1 << ID3_PIN)  # 0b00111000

    def __init__(self, bus=0, cs=0):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, cs)
        self.spi.max_speed_hz = 10_000_000

        # IMPORTANT: always set these explicitly
        self.spi.mode = 0
        self.spi.no_cs = False  # kernel-controlled CS (using /dev/spidevX.Y CS)

        # GPB3–5 outputs, others inputs
        # bit=1 input, bit=0 output
        # B7..B0 = 1 1 0 0 0 1 1 1  -> GPB5/4/3 are outputs
        self.write_reg(IODIRB, 0b11000111)

        # Start from safe state
        self.set_all_off()

    def write_reg(self, reg, value):
        self.spi.xfer2([OPCODE_WRITE, reg, value])

    def read_reg(self, reg):
        return self.spi.xfer2([OPCODE_READ, reg, 0x00])[2]

    def set_mask(self, bits_543: int):
        """
        bits_543 is a 3-bit value representing [ID3 ID2 ID1]:
          bits_543 = (ID3<<2) | (ID2<<1) | (ID1<<0)

        It will be placed into GPB5..GPB3 (bits 5..3).
        Example: 100 => ID3=1, ID2=0, ID1=0 => 0b100
        """
        bits_543 &= 0x07
        val = self.read_reg(OLATB)
        val &= ~self.ID_MASK                      # clear GPB3/4/5
        val |= (bits_543 << self.ID1_PIN)         # shift into bits 3..5
        self.write_reg(OLATB, val)

    def set_all_on(self):
        # ID3 ID2 ID1 = 111
        self.set_mask(0b111)

    def set_all_off(self):
        # ID3 ID2 ID1 = 000
        self.set_mask(0b000)

    def clear_pin(self, pin: int):
        """Drive one GPB pin LOW."""
        val = self.read_reg(OLATB)
        self.write_reg(OLATB, val & ~(1 << pin))

    def set_pin(self, pin: int):
        """Drive one GPB pin HIGH."""
        val = self.read_reg(OLATB)
        self.write_reg(OLATB, val | (1 << pin))

    def set_only_pin_on(self, pin: int):
        self.set_all_off()
        self.set_pin(pin)

    def set_100(self):
        """Convenience: set ID pattern to 100 (ID3=1, ID2=0, ID1=0)."""
        self.set_mask(0b100)

    def close(self):
        try:
            self.spi.close()
        except Exception:
            pass
