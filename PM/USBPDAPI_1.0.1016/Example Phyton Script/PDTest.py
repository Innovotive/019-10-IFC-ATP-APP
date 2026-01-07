#dependencies colorama >pip install colorama

import subprocess
import sys
import time
import datetime
import colorama

RED   = "\033[1;31m"  
BLUE  = "\033[1;34m"
GREEN = "\033[0;32m"
RESET = "\033[0;0m"

CurrentStep = 50        #Current step size in milliamps
FixedProfiles = [1,5]   #Index of all fixed profiles to be tested
PPSProfiles = ["6,7000", "6,3300"]  #Index,Voltage of all PPS profiles to be tested
QCProfiles = ["1,5000", "2,9000"]   #Index,Voltage of all QC profiles to be tested

PDTESTER_SERIAL_USBC = "PMPD111111" #Serial number of the PD Tester used for USB-C port testing
PDTESTER_SERIAL_USBA = "PMPD111111" #Serial number of the PD Tester used for USB-A port testing. 

colorama.init()

overal_pass = 1

print(RESET + 'USBPDTester Python script version 1.1')
SerialNo = str(input('Charger Serial Number:'))

out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBC, '-c'], 
           stdout=subprocess.PIPE, 
           stderr=subprocess.STDOUT)

stdout,stderr = out.communicate()
out.kill()
time.sleep(0.1)

result = str(stdout).find('STATUS:CONNECTED') 
if result == -1:
    sys.exit ('DUT is not connected.') 
    
f = open(SerialNo + ".txt", "w")
f.write("USBPDTester log file\n")
f.write("--------------------\n") 
f.write("Serial No:" + SerialNo + '\n')
now = datetime.datetime.now()
f.write('Date & Time:' + now.strftime("%Y-%m-%d %H:%M:%S") + '\n')

print(RESET + 'Testing USBC port')
f.write('Testing USBC port...\n')     
    
for profile in FixedProfiles:
    test_pass = 1
    out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBC, '-v', str(profile)],
       stdout=subprocess.PIPE, 
       stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    out.kill()
    time.sleep(0.1)

    out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBC, '-c'],
       stdout=subprocess.PIPE, 
       stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    out.kill()
    time.sleep(0.1)

    index_start = str(stdout).find('SET VOLTAGE:')
    if index_start == -1:
        print(stdout)
        sys.exit ('Failed to read set voltage.') 
    index_start += 12
    index_end = str(stdout).find('mV') 
    set_voltage_str = str(stdout)[index_start:index_end]
    set_voltage = int(set_voltage_str)

    index_start = str(stdout).find('MAX CURRENT:')
    if index_start == -1:
        sys.exit ('Failed to read max current.') 
    index_start += 12
    index_end = str(stdout)[index_start:].find('mA') 
    max_current_str = str(stdout)[index_start:index_start+index_end]
    max_current = int(max_current_str)

    print_str = 'Testing profile #' + str(profile) + ' Voltage:' + set_voltage_str + 'mV Max Current:' + max_current_str + 'mA'
    print(RESET + print_str)
    f.write(print_str + '\n')  

    for load in range(0, max_current + CurrentStep, CurrentStep):  
        load_str = str(load)
        out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBC, '-l', str(load)],
           stdout=subprocess.PIPE, 
           stderr=subprocess.STDOUT)
        stdout,stderr = out.communicate()
        out.kill()
        time.sleep(0.1)
        
        out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBC, '-s'],
           stdout=subprocess.PIPE, 
           stderr=subprocess.STDOUT)
        stdout,stderr = out.communicate()
        out.kill()
        time.sleep(0.1)
        index_start = str(stdout).find('VOLTAGE')
        if index_start == -1:
            sys.exit ('Failed to read voltage.') 
        index_start += 8
        index_end = str(stdout).find('mV') 
        voltage_str = str(stdout)[index_start:index_end]
        voltage = int(voltage_str)
        
        index_start = str(stdout).find('MEASURED CURRENT:')
        if index_start == -1:
            sys.exit ('Failed to read current.') 
        index_start += 17
        index_end = str(stdout)[index_start:].find('mA') 
        current_str = str(stdout)[index_start:index_start+index_end]
        
        if voltage > set_voltage*1.05:
            print_str = 'Over voltage detected! Voltage:' + voltage_str + 'mV, Set Current:' + load_str + 'mA, Measured Current:' + current_str + 'mA'
            print(RED + print_str)
            test_pass = 0
            overal_pass = 0;
        elif voltage < set_voltage*0.95:
            print_str = 'Under voltage detected! Voltage:' + voltage_str + 'mV, Set Current:' + load_str + 'mA, Measured Current:' + current_str + 'mA'
            print(RED + print_str)
            test_pass = 0
            overal_pass = 0;
        else:
            print_str = 'Voltage:' + voltage_str + 'mV, Set Current:' +  load_str + 'mA, Measured Current:' + current_str + 'mA'
            print(RESET + print_str, '\r', end='')
    
        f.write(print_str + '\n')
        
    out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBC, '-l', '0'],
       stdout=subprocess.PIPE, 
       stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    out.kill()
    time.sleep(2)
    if test_pass == 1:
        print_str = '*Test Passed*                                                                     '
        print(GREEN + print_str)       
    else:
        print_str = '*Test Failed*                                                                     '
        print(RED + print_str)       
    
    f.write(print_str + '\n')
    

for profile in PPSProfiles:    
    test_pass = 1    
    print_str = 'Testing PPS profile #' + profile
    print(RESET + print_str)
    f.write(print_str + '\n')
    
    out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBC, '-v', profile],
       stdout=subprocess.PIPE, 
       stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    out.kill()
    time.sleep(1)

    out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBC, '-s'],
       stdout=subprocess.PIPE, 
       stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    out.kill()
    time.sleep(0.1)
    index_start = str(stdout).find('VOLTAGE')
    if index_start == -1:
        sys.exit ('Failed to read voltage.') 
    index_start += 8
    index_end = str(stdout).find('mV') 
    voltage_str = str(stdout)[index_start:index_end]
    voltage = int(voltage_str)

    set_voltage = int(profile[2:])
        
    if voltage > set_voltage*1.05:
        print_str = 'Over voltage detected! Voltage:' + voltage_str + 'mV'
        print(RED + print_str)
        test_pass = 0
        overal_pass = 0
    elif voltage < set_voltage*0.95:
        print_str = 'Under voltage detected! Voltage:' + voltage_str + 'mV'
        print(RED + print_str)
        test_pass = 0
        overal_pass = 0
    else:
        print_str = 'Voltage:' + voltage_str + 'mV'
        print(print_str, '\r', end='')
    
        f.write(print_str + '\n')
        
    if test_pass == 1:
        print_str = '*Test Passed*                                                                     '
        print(GREEN + print_str)       
    else:
        print_str = '*Test Failed*                                                                     '
        print(RED + print_str)       
    
    f.write(print_str + '\n')

if PDTESTER_SERIAL_USBC == PDTESTER_SERIAL_USBA:
    print(RESET, end='')    
    input('Testing USBA port, connect charger and press a key to continue...')
else:
    print(RESET + 'Testing USBA port')

f.write('Testing USBA port...\n')   

out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBA, '-c'], 
           stdout=subprocess.PIPE, 
           stderr=subprocess.STDOUT)

stdout,stderr = out.communicate()
out.kill()
time.sleep(0.1)

result = str(stdout).find('STATUS:CONNECTED') 
if result == -1:
    sys.exit ('DUT is not connected.') 
    
for profile in QCProfiles:
    out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBA, profile],
       stdout=subprocess.PIPE, 
       stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    out.kill()
    time.sleep(0.1)

    out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBA, '-c'],
       stdout=subprocess.PIPE, 
       stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    out.kill()
    time.sleep(0.1)

    index_start = str(stdout).find('SET VOLTAGE:')
    if index_start == -1:
        print(stdout)
        sys.exit ('Failed to read set voltage.') 
    index_start += 12
    index_end = str(stdout).find('mV') 
    set_voltage_str = str(stdout)[index_start:index_end]
    set_voltage = int(set_voltage_str)

    index_start = str(stdout).find('MAX CURRENT:')
    if index_start == -1:
        sys.exit ('Failed to read max current.') 
    index_start += 12
    index_end = str(stdout)[index_start:].find('mA') 
    max_current_str = str(stdout)[index_start:index_start+index_end]
    set_voltage = int(set_voltage_str)

    test_pass = 1
    print_str = 'Testing QC profile #' + profile + ' Voltage:' + set_voltage_str + 'mV Max Current:' + max_current_str + 'mA'
    print(RESET + print_str)
    f.write(print_str + '\n')

    for load in range(0, max_current + CurrentStep, CurrentStep):  
        out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBA, '-l', str(load)],
           stdout=subprocess.PIPE, 
           stderr=subprocess.STDOUT)
        stdout,stderr = out.communicate()
        out.kill()
        time.sleep(0.1)
        
        out = subprocess.Popen(['USBPDConsole.exe', '-d', PDTESTER_SERIAL_USBA, '-s'],
           stdout=subprocess.PIPE, 
           stderr=subprocess.STDOUT)
        stdout,stderr = out.communicate()
        out.kill()
        time.sleep(0.1)
        index_start = str(stdout).find('VOLTAGE')
        if index_start == -1:
            sys.exit ('Failed to read voltage.') 
        index_start += 8
        index_end = str(stdout).find('mV') 
        voltage_str = str(stdout)[index_start:index_end]
        voltage = int(voltage_str)
        
        index_start = str(stdout).find('MEASURED CURRENT:')
        if index_start == -1:
            sys.exit ('Failed to read current.') 
        index_start += 17
        index_end = str(stdout)[index_start:].find('mA') 
        current_str = str(stdout)[index_start:index_start+index_end]
        current = int(current_str)
        
        if voltage > set_voltage*1.05:
            print_str = 'Over voltage detected! Voltage:' + voltage_str + 'mV, Set Current:' + load_str + 'mA, Measured Current:' + current_str + 'mA'
            print(RED + print_str)
            test_pass = 0
            overal_pass = 0
        elif voltage < set_voltage*0.95:
            print_str = 'Under voltage detected! Voltage:' + voltage_str + 'mV, Set Current:' + load_str + 'mA, Measured Current:' + current_str + 'mA'
            print(RED + print_str)
            test_pass = 0
            overal_pass = 0
        else:
            print_str = 'Voltage:' + voltage_str + 'mV, Set Current:' +  load_str + 'mA, Measured Current:' + current_str + 'mA'
            print(RESET + print_str, '\r', end='')
    
        f.write(print_str + '\n')
        
    out = subprocess.Popen(['USBPDConsole.exe', '-l', '0'],
       stdout=subprocess.PIPE, 
       stderr=subprocess.STDOUT)
    stdout,stderr = out.communicate()
    out.kill()
    time.sleep(2)
    if test_pass == 1:
        print_str = '*Test Passed*                                                                     '
        print(GREEN + print_str)       
    else:
        print_str = '*Test Failed*                                                                     '
        print(RED + print_str)       
    
    f.write(print_str + '\n') 
    
if overal_pass == 1:    
    print_str = 'OVERAL TESTING RESULT:PASS'
    print(GREEN + print_str)
else:
    print_str = 'OVERAL TESTING RESULT:FAIL'
    print(RED + print_str)
 
f.write(print_str + '\n')      
    
f.close()    



