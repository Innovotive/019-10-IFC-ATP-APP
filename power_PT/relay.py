# ATP/power_PT/python3/relay.py
from gpiozero import LED
import time

relay = LED(26)

def relay_on():
    relay.off()    #relay active low
    time.sleep(10)

def relay_off():
    relay.on()  
