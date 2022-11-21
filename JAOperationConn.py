"""
This file contains the functions to handle connectivity check
Author: havembha@gmail.com, 2022-11-06

Execution Flow
    Read connectivity spec yaml file to buffer
    Extract connectivity check specific parametrs from yaml buffer
    Run connectivity check
    If interactive mode, display results
    Else, store the results to a JAAuditConn.log.YYYYMMDD file
    If upload is enabled, upload the file to SCM host

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

def JAOperationConn(
    baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion, logFilePath, auditLogFileName, 
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel ):

    returnStatus = True
    errorMsg = ''

    ### derive connectivity spec file using subsystem and application version info
        
    if debugLevel > 0:
        print("DEBUG-1 JAOperationConn() Connectivity spec:{0}, subsystem:{1}, appVersion:{2}, interactiveMode:{3}".format(
            baseConfigFileName, subsystem, appVersion, interactiveMode))
    time.sleep(10)


    return returnStatus, errorMsg