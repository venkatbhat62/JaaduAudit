
import os
import sys
import re
import datetime
import time
import subprocess
import signal
import platform
from collections import defaultdict
import JAGlobalLib

import JAOperationSync
import JAOperationSaveCompare
import JAOperationConn
import JAOperationCHILT
import JAOperationDownloadUpload

def JARun( 
    operation, maxWaitTime,
    baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion, logFilePath,  
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime, allowedCommands) :

    # file descriptors r, w for reading and writing
    readDescriptor, writeDescriptor = os.pipe() 
    errorMsg = ''

    if OSType != 'Windows' and debugLevel < 10 :
        ### use debugLevel 10 and above for sequential execution without forking,
        ###  useful while debugging using pdb
        startTime = time.time()
        processId = os.fork()
    else:
        ### SKIP fork
        processId = 0

    if processId > 0:
        # Closes write file descriptor 
        os.close(writeDescriptor)

        # This is the parent process 
        processPresent = True
        while ( processPresent == True ):
            pid, processStatus = os.waitpid( processId, os.WNOHANG)
            if pid == 0:
                ### child not present
                processPresent = False
            else:
                deltaTime = time.time() - startTime
                if deltaTime > maxWaitTime:
                    ### terminate the child
                    JAGlobalLib.LogLine(
			            "WARN JARun() exceeded maxWaitTime:{0}, killed the operation:{1}".format(maxWaitTime, operation), 
                	    interactiveMode,
                	    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    ### TBD - add code later

        ### read the message from child
        readDescriptor = os.fdopen(readDescriptor)
        messageFromChild = readDescriptor.readlines()
        if debugLevel > 1 :
            JAGlobalLib.LogLine(
                "DEBUG-2 JARun() operation:|{0}|, message from child:|{1}|, time:{2}".format(operation, messageFromChild, time.time()), 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        return True, messageFromChild
    
    else:
        # This is the child process
        os.close(readDescriptor)
        returnStatus = False
        if operation == 'save' or operation == 'backup':
            returnStatus, errorMsg = JAOperationSaveCompare.JAOperationSaveCompare(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation )
        elif operation == 'download':
            returnStatus, errorMsg = JAOperationDownloadUpload.JAOperationDownload(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,  
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation ) 
                            
        elif operation == 'upload':
            ### upload saved files from 'SaveDir'
            if len(defaultParameters['UploadFileNames']) > 0:
                returnStatus, errorMsg = JAOperationDownloadUpload.JAOperationUpload(
                    OSType, OSName, OSVersion,   
                    outputFileHandle, colorIndex, HTMLBRTag, myColors,
                    interactiveMode, operations, thisHostName, 
                    defaultParameters, debugLevel, 
                    defaultParameters['SaveDir'],
                    defaultParameters['UploadFileNames'] )
            ### upload reports if present from 'ReportsPath'
            if len( defaultParameters['ReportFileNames']) > 0:
                returnStatus, errorMsg = JAOperationDownloadUpload.JAOperationUpload(
                    OSType, OSName, OSVersion,   
                    outputFileHandle, colorIndex, HTMLBRTag, myColors,
                    interactiveMode, operations, thisHostName, 
                    defaultParameters, debugLevel,
                    defaultParameters['ReportsPath'],
                    defaultParameters['ReportFileNames']  )

        elif operation == 'compare':
            returnStatus, errorMsg = JAOperationSaveCompare.JAOperationSaveCompare(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation )                
        elif operation == 'sync':
            returnStatus, errorMsg = JAOperationSync.JAOperationSync(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime )
        elif operation == 'conn':
            returnStatus, errorMsg = JAOperationConn.JAOperationConn(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation )
        elif operation == 'cert' or operation == 'license' or operation == 'inventory' or operation == 'health':
            returnStatus, errorMsg = JAOperationCHILT.JAOperationCHILT(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation )
        elif operation == 'stats':
            returnStatus, errorMsg = JAOperationStats.JAOperationStats(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation )
        elif operation == 'test':
            returnStatus, errorMsg = JAOperationCHILT.JAOperationCHILT(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation )
        elif operation == 'task':
            returnStatus, errorMsg = JAOperationTask.JAOperationTask(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation )
        elif operation == 'heal':
            returnStatus, errorMsg = JAOperationHeal.JAOperationHeal(
                baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation )
        else:
            errorMsg = "ERROR JARun() Unsupported operation:{0}".format(operation)
            JAGlobalLib.LogLine(
                errorMsg, 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            returnStatus = False            

        if processId == 0 :
            ### did not fork, return
            return returnStatus, errorMsg 

        else:
            ### OS supports forking, write message to parent and exit
            try:
                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JARun() Operation:|{0}| completed with result:|{1}| time:{2}".format(operation, errorMsg, time.time()), 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                ### write the result of executing operation to descriptor so that parent can read the result
                writeDescriptor = os.fdopen(writeDescriptor, 'w')
                writeDescriptor.write(errorMsg)
                writeDescriptor.close()

            except os.error as err:
                # ignore error
                JAGlobalLib.LogLine(
                    "ERROR JARun() could not execution result to parent for the operation:{0}, error:{1}".format(operation, err), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

            # child process on non windows platform, exit child process
            sys.exit()
