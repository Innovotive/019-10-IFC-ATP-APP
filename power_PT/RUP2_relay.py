from gpiozero import LED
from time import sleep

# relay_22 = LED(22) 
# relay_13 = LED(13) 
relay_27 = LED(27)
# relay_6 = LED(6)



while True:
    
    
    # relay_22.off() 
    # sleep(2)

    relay_27.off()  # relay On
    sleep(2)
    # relay_6.off()  # relay On
    # sleep(2)

    # relay_13.off()  # relay On
    # sleep(2)
    # print("On RUP")
   
    #relay_CANH.off()  # relay Off
    #relay_CANL.off()  # relay Off
    #print("Off CAN BUS")


