from gpiozero import LED
from time import sleep

relay = LED(26)

print("Testing relay on GPIO 26 (CTRL+C to stop)")

while True:

    relay.off()  # relay On
    print("On")
