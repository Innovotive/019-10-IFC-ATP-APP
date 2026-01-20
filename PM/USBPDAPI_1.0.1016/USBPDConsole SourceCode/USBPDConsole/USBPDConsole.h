//Passmark USBPD console program
//USBPDConsole.h
//Copyright PassMark Software 2019
//http://www.passmark.com

#ifndef _USB3_CONSOLE_H
#define _USB3_CONSOLE_H


#include <windows.h>
#include "FTD2XX.H"
#include "PDTesterAPI.h"

// Application
#define PROGRAM_NAME	"USBPDConsole"	// Name of the application
#define PROGRAM_VERSION	"V1.0"			// Version of application
#define PROGRAM_BUILD	"1016"			// Build number within this version

typedef enum _TEST_STATUS
{
	STATUS_SUCCEED = 0,
	STATUS_INVALID_COMMAND_LINE,
	STATUS_NO_DEVICE_DETECTED,
	STATUS_FAILED_TO_CONNECT,
	STATUS_INAVLID_PROFILE,
	STATUS_CMD_NOT_SUPPORTED,
	STATUS_FIRMWARE_OUTDATED,
} TEST_STATUS;


#if defined (MAIN_MODULE) 
int			DeviceCount;
wchar_t		PDTesters[MAX_NUM_TESTERS][MAX_SERIAL_LENGTH];			
//CCyUSBDevice		*CurUSBDevice = NULL;						
#else
extern int		DeviceCount;
extern wchar_t	PDTesters[MAX_NUM_TESTERS][MAX_SERIAL_LENGTH];		
//extern CCyUSBDevice			*CurUSBDevice;							
#endif

#endif
