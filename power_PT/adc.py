import time
import board, busio, digitalio
from adafruit_mcp3xxx.mcp3008 import MCP3008
from adafruit_mcp3xxx.analog_in import AnalogIn

spi = busio.SPI(clock=board.SCK, MISO=board.MISO, MOSI=board.MOSI)
cs = digitalio.DigitalInOut(board.CE0)
mcp = MCP3008(spi, cs)

ch0 = AnalogIn(mcp, 0)

while True:
    print("RAW:", ch0.value, "  V:", ch0.voltage)
    
    time.sleep(0.5)
