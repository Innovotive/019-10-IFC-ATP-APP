import RPi.GPIO as GPIO
import time

POWER_GPIO = 21

GPIO.setmode(GPIO.BCM)
GPIO.setup(POWER_GPIO, GPIO.IN)



def read_power_state():

    raw = GPIO.input(POWER_GPIO)
    print(f"[HW] Power GPIO raw state = {raw}")

    # ✅ ACTIVE-HIGH power detect
    power_present = (raw == GPIO.HIGH)

    print(f"[HW] Power detected = {power_present}")
    return power_present

