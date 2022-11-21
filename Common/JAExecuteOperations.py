
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
import JAOperationConn


def JARun( operation, maxWaitTime,
            baseConfigFileName, subsystem, myPlatform, appVersion,
            OSType, OSName, OSVersion, logFilePath, auditLogFileName, 
            outputFileHandle, colorIndex, HTMLBRTag, myColors,
            interactiveMode, operations, thisHostName, yamlModulePresent,
            defaultParameters, debugLevel, currentTime) :

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
                    print("WARN JARun() exceeded maxWaitTime:{0}, killed the operation:{1}".format(
                        maxWaitTime, operation
                    ))
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
        time.sleep(5)

        if operation == 'sync':
            returnStatus, errorMsg = JAOperationSync.JAOperationSync(baseConfigFileName, subsystem, myPlatform, appVersion,
                    OSType, OSName, OSVersion, logFilePath, auditLogFileName, 
                        outputFileHandle, colorIndex, HTMLBRTag, myColors,
                        interactiveMode, operations, thisHostName, yamlModulePresent,
                        defaultParameters, debugLevel, currentTime
                    )
        elif operation == 'conn':
            returnStatus, errorMsg = JAOperationSync.JAOperationConn(baseConfigFileName, subsystem, myPlatform, appVersion,
                    OSType, OSName, OSVersion, logFilePath, auditLogFileName, 
                        outputFileHandle, colorIndex, HTMLBRTag, myColors,
                        interactiveMode, operations, thisHostName, yamlModulePresent,
                        defaultParameters, debugLevel, currentTime
                    )
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
                print("ERROR JARun() could not execution result to parent for the operation:{0}, error:{1}".format(
                        operation, err))

            # child process on non windows platform, exit child process
            sys.exit(0)