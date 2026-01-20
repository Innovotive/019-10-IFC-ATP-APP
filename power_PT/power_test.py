# ATP/power_PT/python3/power.py
import RPi.GPIO as GPIO
import time

POWER_GPIO = 21

GPIO.setmode(GPIO.BCM)
GPIO.setup(POWER_GPIO, GPIO.IN)

def read_power_state(timeout=1.0):
    """
    Returns True if power is detected HIGH within timeout
    Returns False otherwise
    """
    start = time.time()
    while time.time() - start < timeout:
        state = GPIO.input(POWER_GPIO)
        print("state:", state)
        if state == GPIO.HIGH:
            return True
        time.sleep(0.05)

    return False

while True:
    read_power_state(timeout=1.0)