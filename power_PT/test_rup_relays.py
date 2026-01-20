from gpiozero import LED
from time import sleep

# =========================================================
# RELAY GPIO PINS (BCM numbering)
# =========================================================
RELAY_PINS = [22, 27, 6, 13, 19, 26]

# Create relay objects
relays = [LED(pin) for pin in RELAY_PINS]

print("Turning ON all relays... (CTRL+C to stop)")

try:
    while True:
        # Turn ON all relays
        for relay in relays:
            relay.on()   # use .off() instead if your relay is active-low

        print("All relays ON")
        sleep(1)

except KeyboardInterrupt:
    print("\nStopping... turning OFF all relays")

    # Turn OFF all relays safely
    for relay in relays:
        relay.off()
