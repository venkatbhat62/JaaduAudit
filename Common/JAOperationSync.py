"""
This file contains the functions to read latest contents from KITS
Author: havembha@gmail.com, 2022-11-12

Execution Flow
    If sync operation is requested in interactive mode, proceed without any further check
    If not interactive mode, check whether it is time to run sync based on last sync run time.

    Check connectivity to KITS host, print error if no connectivity


"""

import os
import sys
import re
import datetime
import time
import subprocess
import signal
from collections import defaultdict
import JAGlobalLib

def JAOperationSync(baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion, logFilePath, auditLogFileName, 
     outputFileHandle, colorIndex, HTMLBRTag, myColors,
     interactiveMode, operations, thisHostName, yamlModulePresent,
     defaultParameters, debugLevel, currentTime
    ):

    returnStatus = True

    ### If not interactive mode, check whether it is time to run sync based on last sync run time.
    if interactiveMode == False:
        returnStatus = JAGlobalLib.JAIsItTimeToRunOperation(currentTime, subsystem, "sync", defaultParameters, debugLevel)
        if returnStatus == False:
            ### sync durtaion not elapsed, return 
            errorMsg = "Skipping Sync, duration not elapsed yet"
            if debugLevel > 0:
                print("DEBUG-1 JAOperationSync() {0}".format(errorMsg))

    if returnStatus == True:
        ### run sync

        ### copy code/config contents to JAAudit.PrevVersion directory so that downloaded contents can be compared
        ###   to previous contents and display the delta
        saveDirName = "JAAudit.PrevVersion"
        if os.path.exists(saveDirName) == False:
            os.mkdir(saveDirName)

        if OSType == "SunOS":
            copyCommand = "cp -p *.exp *.yml *.py *.pl *.ksh *.bash *.Rsp* *.sql *.sedCmd {0} 2>/dev/null".format(saveDirName)
        else:
            copyCommand = "cp -ua *.exp *.yml *.py *.pl *.ksh *.bash *.Rsp* *.sql *.sedCmd {0} 2>/dev/null".format(saveDirName)
        
        JAGlobalLib.JAExecuteCommand(copyCommand, OSType, OSName, OSVersion, debugLevel)

        ### derive syncCommand
        if 'CommandRsync' in defaultParameters:
            syncCommand = "{0} {1}@{2}:/{3}".format(defaultParameters['CommandRsync'],
                            defaultParameters['KITSRsyncUserName'],
                            defaultParameters['KITSHostName'],
                            defaultParameters['Platform']
                            )
        elif 'CommandWget' in defaultParameters:
            syncCommand = "{0} https://{1}:{2}/{3}/".format( 
                    defaultParameters['CommandWget'],
                    defaultParameters['KITSHostName'],
                    defaultParameters['KITSPortHTTPS'],
                    defaultParameters['Platform']
            )
        
        if debugLevel > 2:
            print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))
        
        returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(syncCommand, OSType, OSName, OSVersion, debugLevel)
        if returnResult == False:
            print("ERROR Error executing syncCommand:{0}, command output: {1}, errorMsg:{2}".format(
                returnResult, returnOutput, errorMsg    
            ))

    if errorMsg != '':
        print("ERROR JAOperationSync() Sync failed with error:{0}".format(errorMsg))
    return returnStatus, errorMsg