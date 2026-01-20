from gpiozero import LED
from time import sleep

relay_22 = LED(22) 

while True:

    relay_22.off()  # relay On