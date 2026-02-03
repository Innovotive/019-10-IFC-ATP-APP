import spidev

# MCP23S17 SPI OPCODES (A2 A1 A0 = 000)
OPCODE_WRITE = 0x40
OPCODE_READ  = 0x41

IODIRA = 0x00
OLATA  = 0x14

class IDPins:
    def __init__(self, bus=0, cs=0):
        self.spi = spidev.SpiDev()
        self.spi.open(bus, cs)
        self.spi.max_speed_hz = 10_000_000

        # IMPORTANT: always set these explicitly
        self.spi.mode = 0
        self.spi.no_cs = False  # kernel-controlled CS (using /dev/spidevX.Y CS)

        # GPA0–2 outputs, GPA3–7 inputs
        self.write_reg(IODIRA, 0b11111000)

        # Start from safe state
        self.set_all_off()

    def write_reg(self, reg, value):
        self.spi.xfer2([OPCODE_WRITE, reg, value])

    def read_reg(self, reg):
        return self.spi.xfer2([OPCODE_READ, reg, 0x00])[2]

    def set_mask(self, mask: int):
        """mask uses GPA0–2 bits (bit0=GPA0, bit1=GPA1, bit2=GPA2)"""
        self.write_reg(OLATA, mask & 0x07)

    def set_all_on(self):
        self.set_mask(0b111)

    def set_all_off(self):
        self.set_mask(0b000)

    def clear_pin(self, pin: int):
        """Drive one GPA pin LOW."""
        val = self.read_reg(OLATA)
        self.write_reg(OLATA, val & ~(1 << pin))

    def set_pin(self, pin: int):
        """Drive one GPA pin HIGH."""
        val = self.read_reg(OLATA)
        self.write_reg(OLATA, val | (1 << pin))

    def set_only_pin_on(self, pin: int):
        self.set_all_off()
        self.set_pin(pin)

    def close(self):
        try:
            self.spi.close()
        except Exception:
            pass
