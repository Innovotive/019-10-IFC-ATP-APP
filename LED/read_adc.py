import RPi.GPIO as GPIO
import time

# -------------------------
# Configuration
# -------------------------
PIN = 17  # BCM pin number

GPIO.setmode(GPIO.BCM)           # Use BCM numbering
GPIO.setup(PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  
# you can also use PUD_UP depending on wiring

print("Reading digital pin", PIN)

try:
    while True:
        state = GPIO.input(PIN)
        print("Pin state:", state)
        time.sleep(0.2)

except KeyboardInterrupt:
    pass

finally:
    GPIO.cleanup()
