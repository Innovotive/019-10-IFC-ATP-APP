import lgpio
import time

GPIO = 21

# Open gpio chip
h = lgpio.gpiochip_open(0)

# Claim GPIO21 as input
lgpio.gpio_claim_input(h, GPIO)

while True:
    state = lgpio.gpio_read(h, GPIO)

    if state == 1:
        print("LED is OFF (GPIO = HIGH)")
    else:
        print("LED is ON (GPIO = LOW)")

    time.sleep(0.5)
