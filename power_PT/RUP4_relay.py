from gpiozero import LED
from time import sleep

relay_13 = LED(13) 

while True:
    relay_13.off()  # relay On