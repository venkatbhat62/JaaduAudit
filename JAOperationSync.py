"""
This file contains the functions to read latest contents from SCM
Author: havembha@gmail.com, 2022-11-12

Execution Flow
    If sync operation is requested in interactive mode, proceed without any further check
    If not interactive mode, check whether it is time to run sync based on last sync run time.

    Check connectivity to SCM host, print error if no connectivity


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

def GetAllFilesFromSCM(
    wgetCommand:str,
    OSType:str, OSName:str, OSVersion:str, debugLevel:int):
    """
    This function first executes given wget command to get index dump from SCM (source code management) server
    Parses the index file, extracts the file name and last updated date
    If the file is present at local directory, it checks the last update date.
    If the file on SCM is later date, it will fetch that file.

    Parameters passed
        wgetCommand - entire command up to the directory. Individual file name will be appended to this
            command to get individual file
    Returned Values
        resturnStatus  - True if success, False on failure to fetch a file
        fileNames - names of the files fetched
        errorMsg - error message up on error

    """
    returnStatus= True
    fileNames = []
    errorMsg = ''

    import tempfile

    wgetOutputFileName ="JAAudit.wget.{0}".format( os.getpid() )

    
    ### iwr options used 
    ###   | Select-Object -ExpandProperty Content | Out-File JAAudit.wget.

    tempWgetCommand = "{0} -OutFile {1}".format(
            wgetCommand, wgetOutputFileName )
    returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
        tempWgetCommand, OSType, OSName, OSVersion, debugLevel)

    if returnResult == False:
        returnStatus = False
        errorMsg = "ERROR GetAllFilesFromSCM() unable to get file list from SCM, wget command:{0}, return response:{1}, error:{2}".format(
            tempWgetCommand, returnOutput, errorMsg    )
        print(errorMsg)
        return returnStatus, fileNames, errorMsg
    
    ### process index output to extract file names
    with open( wgetOutputFileName, "r") as file:
        headerLines = True
        while True:
            errorMsg = ''
            line = file.readline()
            if not line:
                break
            if headerLines == True:
                if re.search(r'Parent Directory', line) != None:
                    ### line is of the form:
                    ### <tr><td valign="top"><img src="/icons/back.gif" alt="[PARENTDIR]"></td><td><a href="/">Parent Directory</a></td><td>&nbsp;</td><td align="right">  - </td><td>&nbsp;</td></tr>
                    headerLines = False
            else:
                ### each line has separate file name
                ### <tr><td valign="top"><img src="/icons/text.gif" alt="[TXT]"></td><td><a href="JAAudit.py">JAAudit.py</a></td><td align="right">2022-11-19 15:23  </td><td align="right"> 34K</td><td>&nbsp;</td></tr>
                ###                                                                            ^^^^^^^^^^ <-- name                              ^^^^^^^^^^^^^^^^ <-- time stamp                          
                ###     <------------- 0 -------------------------------------------><------ 1 ---------------------------------><---------------- 2 -------------------->
                fileInfo = line.split("</td><td")
                if len(fileInfo) < 2 :
                    continue
                ### <td><a href="JAAudit.py">JAAudit.py</a></td>
                ###              ^^^^^^^^^^ <--- extract this name
                fileNameFieldParts = re.findall(r'<a href="(.+)">', fileInfo[1])
                patternMatchCount =  len(fileNameFieldParts)
                if fileNameFieldParts != None and patternMatchCount > 0 :
                    fileNameToFetch= fileNameFieldParts[0]

                    ### extract timestamp string
                    ###  align="right">2022-11-19 15:23  
                    ###                ^^^^^^^^^^^^^^^^^
                    fileNameFieldParts = re.findall(r'>(.*) ', fileInfo[2])
                    patternMatchCount =  len(fileNameFieldParts)
                    if fileNameFieldParts != None and patternMatchCount > 0 :
                        dateTimeString= fileNameFieldParts[0]
                        dateTimeString = dateTimeString.strip()
                        SCMFileTimeInSec = int(JAGlobalLib.JAConvertStringTimeToTimeInMicrosec(dateTimeString, "%Y-%m-%d %H:%M" ) \
                            / 1000000)

                        fetchSCMFile = True
                        if os.path.exists(fileNameToFetch):
                            ### get file modified time on local host
                            fileModifiedTime = os.path.getmtime ( fileNameToFetch )

                            ### if the local file has same time stamp as that of SCM file, DO NO NOT fetch it
                            if abs(SCMFileTimeInSec - fileModifiedTime) > 0 :
                                fetchSCMFile = False

                        ### fetch the file if needed
                        if fetchSCMFile == True:
                            tempWgetCommand = "{0}{1} -OutFile {2}".format(
                                    wgetCommand, fileNameToFetch, fileNameToFetch )
                            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                                tempWgetCommand, OSType, OSName, OSVersion, debugLevel)

                            if returnResult == False:
                                returnStatus = False
                                errorMsg = "ERROR GetAllFilesFromSCM() unable to get the file {0} from SCM, wget command:{1}, return response:{2}, error:{3}".format(
                                    fileNameToFetch, tempWgetCommand, returnOutput, errorMsg    )
                                print(errorMsg)
                            else:
                                ### add fetched file name to the list
                                fileNames.append(fileNameToFetch)
                                if debugLevel > 1:
                                    errorMsg = "DEBUG-2 GetAllFilesFromSCM() Fetched file {0} from SCM using the command:{1}".format(
                                        fileNameToFetch, tempWgetCommand )
                                    print(errorMsg)
                        else:
                            if debugLevel > 2:
                                print("DEBUG-3 GetAllFilesFromSCM() File {0} on SCM is older than local file, not fetching it".format(fileNameToFetch))
                
        file.close()
        os.remove(wgetOutputFileName)

    return returnStatus, fileNames, errorMsg

def JAOperationSync(
    baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion, logFilePath, auditLogFileName, 
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime ):

    returnStatus = True

    ### If not interactive mode, check whether it is time to run sync based on last sync run time.
    if interactiveMode == False:
        returnStatus = JAGlobalLib.JAIsItTimeToRunOperation(
            currentTime, subsystem, "sync", defaultParameters, debugLevel)
        if returnStatus == False:
            ### sync durtaion not elapsed, return 
            errorMsg = "Skipping Sync, duration not elapsed yet"
            if debugLevel > 0:
                print("DEBUG-1 JAOperationSync() {0}".format(errorMsg))

    if returnStatus == True:
        ### run sync

        ### prepare save directories for Common, Custom files
        if 'LocalRespositoryHome' in defaultParameters:
            localRespositoryHome = defaultParameters['LocalRespositoryHome']
            try:
                localRespositoryHome = os.path.expandvars(localRespositoryHome)
                os.chdir(localRespositoryHome)
            except OSError as err:
                errorMessage = ("ERROR JAOperationSync() Not able to change directory to {0}, OS Error:{1}".format(
                     localRespositoryHome, err   ))
                print(errorMessage)
                return False, errorMessage 
        else:
            localRespositoryHome = os.getcwd()

        if 'LocalRespositoryCommon' in defaultParameters:
            localRespositoryCommon = defaultParameters['LocalRespositoryCommon']
            if os.path.exists(localRespositoryCommon) == False:
                try:
                    os.mkdir(localRespositoryCommon)
                except OSError as err:
                    errorMessage = ("ERROR JAOperationSync() Not able to create directory to {0}, OS Error:{1}".format(
                        localRespositoryCommon, err   ))
                    print(errorMessage)
                    return False, errorMessage 
        else:
            localRespositoryCommon = ''

        if 'LocalRespositoryCustom' in defaultParameters:
            localRespositoryCustom = defaultParameters['LocalRespositoryCustom']
            if os.path.exists(localRespositoryCustom) == False:
                try:
                    os.mkdir(localRespositoryCustom)
                except OSError as err:
                    errorMessage = ("ERROR JAOperationSync() Not able to create directory to {0}, OS Error:{1}".format(
                        localRespositoryCustom, err   ))
                    print(errorMessage)
                    return False, errorMessage 
        else:
            localRespositoryCustom = ''

        ### make a list of files to copy to save directory 
        if 'FilesToCompareAfterSync' in defaultParameters:
            filesToCompareAfterSync = defaultParameters['FilesToCompareAfterSync']
        else:
            ### no custom definition in environment definition, use default list
            filesToCompareAfterSync = "*.exp *.yml *.py *.pl *.ksh *.bash *.Rsp* *.sql *.sedCmd"

        ### copy code/config contents to Common.PrevVersion, Custom.PrevVersion directories
        ###    so that downloaded contents can be compared to previous contents and display the delta
        if OSType == "Windows":
            ### copy files one type at a time
            fileNames = filesToCompareAfterSync.split(' ')
            for fileName in fileNames:
                ### copy files from Common to .PrevVersion
                copyCommand = "cp {0}/{1}/{2} {3}/{4}.PrevVersion".format( 
                        localRespositoryHome, localRespositoryCommon, fileName,
                        localRespositoryHome, localRespositoryCommon)
                JAGlobalLib.JAExecuteCommand(copyCommand, OSType, OSName, OSVersion, debugLevel)

                if localRespositoryCustom != '':
                    ### copy files from Custom to .PrevVersion
                    copyCommand = "cp {0}/{1}/{2} {3}/{4}.PrevVersion".format( 
                        localRespositoryHome, localRespositoryCustom, fileName,
                        localRespositoryHome, localRespositoryCustom)
                    JAGlobalLib.JAExecuteCommand(copyCommand, OSType, OSName, OSVersion, debugLevel)

        else:    
            ### firt copy contents under Common
            if OSType == "SunOS":
                copyCommand = "cp -p {0}/{1}/{2} {3}/{4}.PrevVersion 2>/dev/null".format(
                        localRespositoryHome, localRespositoryCommon,filesToCompareAfterSync, 
                        localRespositoryHome, localRespositoryCommon)

            elif OSType == 'Linux':
                copyCommand = "cp -ua {0}/{1}/{2} {3}/{4}.PrevVersion 2>/dev/null".format(
                        localRespositoryHome, localRespositoryCommon,filesToCompareAfterSync, 
                        localRespositoryHome, localRespositoryCommon)
                
            JAGlobalLib.JAExecuteCommand(copyCommand, OSType, OSName, OSVersion, debugLevel)

            ### next copy contents under Custom
            if OSType == "SunOS":
                copyCommand = "cp -p {0}/{1}/{2} {3}/{4}.PrevVersion 2>/dev/null".format(
                        localRespositoryHome, localRespositoryCustom,filesToCompareAfterSync, 
                        localRespositoryHome, localRespositoryCustom)

            elif OSType == 'Linux':
                copyCommand = "cp -ua {0}/{1}/{2} {3}/{4}.PrevVersion 2>/dev/null".format(
                        localRespositoryHome, localRespositoryCustom,filesToCompareAfterSync, 
                        localRespositoryHome, localRespositoryCustom)
                
            JAGlobalLib.JAExecuteCommand(copyCommand, OSType, OSName, OSVersion, debugLevel)

        if 'CommandRsync' in defaultParameters:
            commandRsync = defaultParameters['CommandRsync']
        else:
            commandRsync = ''

        if 'CommandWget' in defaultParameters:
            commandWget = defaultParameters['CommandWget']
        else:
            commandWget = ''
        
        if commandRsync == '' and commandWget == '':
            errorMessage = ("ERROR JAOperationSync() Both rsync and wget commands not present, can't complete sync operation")
            print(errorMessage)
            return False, errorMessage

        ### use rsync or wget, derive command to sync common contents, and execute command
        if localRespositoryCommon != '':
            os.chdir("{0}/{1}".format(localRespositoryHome,localRespositoryCommon))
        if commandRsync != '':
            syncCommand = "{0} {1}@{2}:/{3}".format(defaultParameters['CommandRsync'],
                            defaultParameters['SCMRsyncUserName'],
                            defaultParameters['SCMHostName'],
                            defaultParameters['SCMRepositoryCommon']
                            )
            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))
            
            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                syncCommand, OSType, OSName, OSVersion, debugLevel)
            if returnResult == False:
                print("ERROR Error executing syncCommand:{0}, command output: {1}, errorMsg:{2}".format(
                    returnResult, returnOutput, errorMsg  ))

        elif commandWget != '':
            syncCommand = "{0} https://{1}:{2}/{3}/".format( 
                    defaultParameters['CommandWget'],
                    defaultParameters['SCMHostName'],
                    defaultParameters['SCMPortHTTPS'],
                    defaultParameters['SCMRepositoryCommon']
            )

            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))

            if OSType == "Windows":
                ### can't get all files in one go, have to get those one by one
                returnResult, returnOutput, errorMsg = GetAllFilesFromSCM(
                    syncCommand, OSType, OSName, OSVersion, debugLevel)
            else:
                returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(syncCommand, OSType, OSName, OSVersion, debugLevel)
                if returnResult == False:
                    print("ERROR Error executing syncCommand:{0}, command output: {1}, errorMsg:{2}".format(
                        returnResult, returnOutput, errorMsg  ))

        ### use rsync or wget, derive command to sync custom contents, and execute command
        if localRespositoryCommon != '':
            os.chdir("{0}/{1}".format(localRespositoryHome,localRespositoryCustom))

        if commandRsync != '':
            syncCommand = "{0} {1}@{2}:/{3}".format(defaultParameters['CommandRsync'],
                            defaultParameters['SCMRsyncUserName'],
                            defaultParameters['SCMHostName'],
                            defaultParameters['SCMRepositoryCustom']
                            )
            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))
            
            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                syncCommand, OSType, OSName, OSVersion, debugLevel)
            if returnResult == False:
                print("ERROR Error executing syncCommand:{0}, command output: {1}, errorMsg:{2}".format(
                    returnResult, returnOutput, errorMsg  ))
        elif commandWget != '':
            syncCommand = "{0} https://{1}:{2}/{3}/".format( 
                    defaultParameters['CommandWget'],
                    defaultParameters['SCMHostName'],
                    defaultParameters['SCMPortHTTPS'],
                    defaultParameters['SCMRepositoryCustom']
            )
        
            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))
            
            if OSType == "Windows":
                ### can't get all files in one go, have to get those one by one
                returnResult, fileNames, errorMsg = GetAllFilesFromSCM(
                    syncCommand, OSType, OSName, OSVersion, debugLevel )
            else:
                returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                    syncCommand, OSType, OSName, OSVersion, debugLevel)
                if returnResult == False:
                    print("ERROR Error executing syncCommand:{0}, command output: {1}, errorMsg:{2}".format(
                        returnResult, returnOutput, errorMsg ))

    if errorMsg != '':
        print("ERROR JAOperationSync() Sync failed with error:{0}".format(errorMsg))
    return returnStatus, errorMsg