import RPi.GPIO as GPIO
import time

GPIO.setmode(GPIO.BCM)
GPIO.setup(20, GPIO.IN)

try:
    while True:
        state = GPIO.input(20)
        print("State:", state)   # 1 = HIGH, 0 = LOW
        time.sleep(0.2)

except KeyboardInterrupt:
    GPIO.cleanup()
