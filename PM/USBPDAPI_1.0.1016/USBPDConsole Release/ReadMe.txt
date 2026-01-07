PassMark USBPDConsole
Copyright (C) 2018-2024 PassMark Software
All Rights Reserved
http://www.passmark.com

Overview
========
USBPDConsole is an easy to use Windows console based 
application that allows users to quickly check that 
a USB port on their PC is capable of delivering its 
maximum specified wattage without failing. 
USBPDConsole is designed for use in conjunction with 
Passmark’s USB Power Delivery tester device.

Installation
============
1) Uninstall any previous version of USBPDConsole
2) Unzip the files from the downloaded ".zip" file
3) Run the ".exe" file from the Command Prompt 

UnInstallation
==============
Just delete the installation directory.

Requirements
============
CPU:
80486 200Mhz or faster.

Operating System: 
Windows 7, 8, 10.

128Meg RAM
1 Meg of free hard disk space to install the software
USB 3 or 2 ports

PassMark Software USBPDConsole V1.0.1016
Usage: USBPDConsole.exe [-f] [-d] [-i] [-c] [-p] [-s] [-r] [-v] [-l] [-q] [-n] [-m] [-o] [-u] [-w] [-k] [-b] [-x] [-y]
Options:
        -h,--help               Shows this help message
        -f,--find               Finds all the PD tester devices and their indexes.
        -d,--device             Specifies the PD tester by serial number. Device ID or "Any"
                                If the ID, "Any" is used then the first device detected is selected.
                                Default value if empty: The first detected device will be used.
        -i,--index              Specifies the PD tester by index.
        -c,--connection         Returns the connection status.
        -p,--profiles           Returns all the profiles supported by DUT.
        -s,--stats              Returns DUT status.
        -r,--config             Returns the configuration of the PD tester.
        -v,--setprofile         Sets a profile. Index starts from 1.
                                For fixed profile use -v index. For variable voltage profile use: -v index,voltage (mV)
        -l,--load               Sets the current (mA).
        -q,--quickload          Sets the current (mA) quickly, optionally set the slope of the current.
                                For default quick load: -q load (ma). For setting slope: -q load,slope (mA/ms).
        -m,--defload            Sets default load (mA) or "Max" for maximum available current.
        -n,--defvolt            Sets default voltage (mV).
        -o,--maxload            Sets maximum allowed current (mA). Set to 0 to enable enforce automatic limits.
        -u,--defprofile         Sets default profile by index. Set to 0 to enable auto selection.
                                For variable voltage profile default voltage should also be set.
        -w,--oprcurrent         Sets the operating current in RDO or "Max" for max available current.
        -k,--sinkcap            Sets the capabiltity advertised by the sink. Use: -k voltage(mV),current(mA).
                                Or for no additional capability, use: -k "None".
        -b,--usbconnection      Simulates a physical disconnection or connection of the DUT.
                                For disconnection use: -b 0. For connection: -b 1.
        -x,--setHoldLoad        Sets if the the load is held during voltage changes. Use -x 0 to disable, -x 1 to enable.
        -y,--stepresponse       Performs a step load test. Use: -y initial current,final current (mA)

Return Codes:
         Succeed = 0
         Invalid command line = 1
         No device detected = 2
         Failed to connect = 3
         Invalid profile = 4
         Command is not supported by PD tester model = 5
         Device firmare update required = 6

Example:
        USBPDConsole.exe -d pmpd4vlh7y -v 3,6000
