from gpiozero import LED
from time import sleep

relay = LED(26)
#relay_CANH = LED(27)
#relay_CANL = LED(17)

print("Testing relay on GPIO 26 (CTRL+C to stop)")
print("Testing relay on GPIO 17 and 27 (CTRL+C to stop)")


while True:
    relay.off()  # relay On
    print("On RUP")

    #relay_CANH.off()  # relay Off
    #relay_CANL.off()  # relay Off
    #print("Off CAN BUS")


