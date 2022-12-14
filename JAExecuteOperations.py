
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

    if OSType != 'Windows':
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
            print("DEBUG-2 JARun() message from child:{0}".format(messageFromChild))

        return True, messageFromChild
    
    else:
        # This is the child process
        os.close(readDescriptor)
        
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
        else:
            errorMsg = "ERROR JARun() Unsupported operation:{0}".format(operation)
            JAGlobalLib.LogLine(
                errorMsg, 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            returnStatus = False            

        if OSType == "Windows":
            ### did not fork, return
            return returnStatus, errorMsg 

        else:
            ### OS supports forking, write message to parent and exit
            try:
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
            sys.exit(0)
