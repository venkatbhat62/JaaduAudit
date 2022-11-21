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
import JAOperationCompare

def GetAllFilesFromSCMUsingRsync(
    rsyncCommand:str, 
    OSType:str, OSName:str, OSVersion:str, debugLevel:int):

    """
    This function uses rsync to fetch files from SCM to local host.
    Using the rsync log file, it makes a list of updated files and returns it

    Parameters passed
        rsyncCommand - entire rsync command except the log file option. 

    Returned Values
        resturnStatus  - True if success, False on failure to fetch a file
        fileNames - names of the files fetched
        errorMsg - error message up on error

    """
    returnStatus= True
    fileNames = []
    errorMsg = ''

    import tempfile

    rsyncOutputFileName ="JAAudit.rsync.{0}".format( os.getpid() )

    ### compute full wget command with option to write the contents to output file
    if OSType == "Windows":
        ### TBD this is not tested yet
        rsyncOutputFileOption = "-OutFile"
    else:
        ### Redhat 5 and above support --log-file  option
        rsyncOutputFileOption = "--log-file"

    tempRsyncCommand = "{0} {1} {2}".format(
            rsyncCommand, rsyncOutputFileOption, rsyncOutputFileName )

    returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
        tempRsyncCommand, debugLevel)

    if returnResult == False:
        returnStatus = False
        errorMsg = "ERROR GetAllFilesFromSCMUsingRsync() unable to get file list from SCM, rsync command:{0}, return response:{1}, error:{2}".format(
            tempRsyncCommand, returnOutput, errorMsg    )
        print(errorMsg)
        return returnStatus, fileNames, errorMsg
    
    ### process index output to extract file names
    with open( rsyncOutputFileName, "r") as file:
        headerLines = True
        while True:
            errorMsg = ''
            line = file.readline()
            if not line:
                break

        file.close()
        os.remove(rsyncOutputFileName)

    return returnStatus, fileNames, errorMsg

def GetAllFilesFromSCMUsingWget(
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

    ### compute full wget command with option to write the contents to output file
    if OSType == "Windows":
        ### iwr options used 
        wgetOutputFileOption = "-OutFile"
    else:
        ### all unix/linux flavors support -o <outputFile> option
        wgetOutputFileOption = "-o"

    tempWgetCommand = "{0} {1} {2}".format(
            wgetCommand, wgetOutputFileOption, wgetOutputFileName )

    returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
        tempWgetCommand, debugLevel)

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
                ###     <------------- 0 -------------------------------------------><------ 1 ---------------------------------><---------------- 2 --------------------><------------------ 3 --->
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
                            tempWgetCommand = "{0}{1} {2} {3}".format(
                                    wgetCommand, fileNameToFetch, wgetOutputFileOption, fileNameToFetch )

                            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                                tempWgetCommand, debugLevel)

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

    downloadedFileInfo = {}

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
        if 'LocalRepositoryHome' in defaultParameters:
            localRepositoryHome = defaultParameters['LocalRepositoryHome']
            try:
                localRepositoryHome = os.path.expandvars(localRepositoryHome)
                os.chdir(localRepositoryHome)
            except OSError as err:
                errorMessage = ("ERROR JAOperationSync() Not able to change directory to {0}, OS Error:{1}".format(
                     localRepositoryHome, err   ))
                print(errorMessage)
                return False, errorMessage 
        else:
            localRepositoryHome = os.getcwd()

        if 'LocalRepositoryCommon' in defaultParameters:
            localRepositoryCommon = defaultParameters['LocalRepositoryCommon']
            if os.path.exists(localRepositoryCommon) == False:
                try:
                    os.mkdir(localRepositoryCommon)
                except OSError as err:
                    errorMessage = ("ERROR JAOperationSync() Not able to create directory to {0}, OS Error:{1}".format(
                        localRepositoryCommon, err   ))
                    print(errorMessage)
                    return False, errorMessage 
        else:
            localRepositoryCommon = ''

        if 'LocalRepositoryCustom' in defaultParameters:
            localRepositoryCustom = defaultParameters['LocalRepositoryCustom']
            if os.path.exists(localRepositoryCustom) == False:
                try:
                    os.mkdir(localRepositoryCustom)
                except OSError as err:
                    errorMessage = ("ERROR JAOperationSync() Not able to create directory to {0}, OS Error:{1}".format(
                        localRepositoryCustom, err   ))
                    print(errorMessage)
                    return False, errorMessage 
        else:
            localRepositoryCustom = ''

        ### make a list of files to copy to save directory 
        if 'FilesToCompareAfterSync' in defaultParameters:
            filesToCompareAfterSync = defaultParameters['FilesToCompareAfterSync']
        else:
            ### no custom definition in environment definition, use default list
            filesToCompareAfterSync = "*.exp *.yml *.py *.pl *.ksh *.bash *.Rsp* *.sql *.sedCmd"

        ### create Common and Custom directories if not present yet
        prevVersionFolder = "{0}/{1}.PrevVersion".format(localRepositoryHome, localRepositoryCommon)
        if os.path.exists(prevVersionFolder) == False:
            os.mkdir(prevVersionFolder)
        prevVersionFolder = "{0}/{1}.PrevVersion".format(localRepositoryHome, localRepositoryCustom)
        if os.path.exists(prevVersionFolder) == False:
            os.mkdir(prevVersionFolder)
            

        ### copy code/config contents to Common.PrevVersion, Custom.PrevVersion directories
        ###    so that downloaded contents can be compared to previous contents and display the delta
        if OSType == "Windows":
            import glob
            import shutil
            sourceDirCommon = "{0}/{1}".format(localRepositoryHome, localRepositoryCommon)
            destinationDirCommon = "{0}/{1}.PrevVersion".format(localRepositoryHome, localRepositoryCommon)
            sourceDirCustom = "{0}/{1}".format(localRepositoryHome, localRepositoryCustom)
            destinationDirCustom = "{0}/{1}.PrevVersion".format(localRepositoryHome, localRepositoryCustom)
            ### copy files one type at a time
            fileNames = filesToCompareAfterSync.split(' ')
            for fileName in fileNames:
                globString = r"{0}/{1}".format(sourceDirCommon, fileName)
                ### copy files from Common to .PrevVersion
                for file in glob.glob(globString):
                    print(file)
                    shutil.copy(file, destinationDirCommon)

                if localRepositoryCustom != '':
                    globString = r"{0}/{1}".format(sourceDirCustom, fileName)
                    ### copy files from Custom to .PrevVersion
                    for file in glob.glob(globString):
                        print(file)
                        shutil.copy(file, destinationDirCustom)

        else:    
            ### firt copy contents under Common
            if OSType == "SunOS":
                copyCommand = "cp -p {0}/{1}/{2} {3}/{4}.PrevVersion 2>/dev/null".format(
                        localRepositoryHome, localRepositoryCommon,filesToCompareAfterSync, 
                        localRepositoryHome, localRepositoryCommon)

            elif OSType == 'Linux':
                copyCommand = "cp -ua {0}/{1}/{2} {3}/{4}.PrevVersion 2>/dev/null".format(
                        localRepositoryHome, localRepositoryCommon,filesToCompareAfterSync, 
                        localRepositoryHome, localRepositoryCommon)
                
            JAGlobalLib.JAExecuteCommand(copyCommand, debugLevel)

            ### next copy contents under Custom
            if OSType == "SunOS":
                copyCommand = "cp -p {0}/{1}/{2} {3}/{4}.PrevVersion 2>/dev/null".format(
                        localRepositoryHome, localRepositoryCustom,filesToCompareAfterSync, 
                        localRepositoryHome, localRepositoryCustom)

            elif OSType == 'Linux':
                copyCommand = "cp -ua {0}/{1}/{2} {3}/{4}.PrevVersion 2>/dev/null".format(
                        localRepositoryHome, localRepositoryCustom,filesToCompareAfterSync, 
                        localRepositoryHome, localRepositoryCustom)
                
            JAGlobalLib.JAExecuteCommand(copyCommand, debugLevel)

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
        if localRepositoryCommon != '':
            if OSType == "Windows":
                tempDirectory = "{0}\{1}".format(localRepositoryHome,localRepositoryCommon)
            else:
                tempDirectory = "{0}/{1}".format(localRepositoryHome,localRepositoryCommon)

            os.chdir(tempDirectory)
            if debugLevel > 1:
                errorMsg = "DEBUG-2 JAOperationSync() common directory:{0}, pwd:{1}".format(tempDirectory, os.getcwd())
                print(errorMsg)
        if commandRsync != '':
            syncCommand = "{0} {1}@{2}:/{3}".format(defaultParameters['CommandRsync'],
                            defaultParameters['SCMRsyncUserName'],
                            defaultParameters['SCMHostName'],
                            defaultParameters['SCMRepositoryCommon']
                            )
            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))

            ### can't get all files in one go, have to get those one by one
            returnResult, fileNames, errorMsg = GetAllFilesFromSCMUsingRsync(
                syncCommand, OSType, OSName, OSVersion, debugLevel)

        elif commandWget != '':
            syncCommand = "{0} https://{1}:{2}/{3}/".format( 
                    defaultParameters['CommandWget'],
                    defaultParameters['SCMHostName'],
                    defaultParameters['SCMPortHTTPS'],
                    defaultParameters['SCMRepositoryCommon']
            )

            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))

            ### can't get all files in one go, have to get those one by one
            returnResult, fileNames, errorMsg = GetAllFilesFromSCMUsingWget(
                syncCommand, OSType, OSName, OSVersion, debugLevel)

        if returnResult == True:
            ### If file is NEW, print that file name as NEW file.
            ### If existing file, print differences between PrevVersion and current version of the file
            for fileName in fileNames:
                currentFileName = '{0}/{1}/{2}'.format(localRepositoryHome,localRepositoryCommon, fileName)
                previousFileName = '{0}/{1}.PrevVersion/{2}'.format(localRepositoryHome,localRepositoryCommon, fileName)
                if os.path.exists(previousFileName ):
                    JAOperationCompare.JAOperationCompareFiles( 
                            currentFileName, previousFileName, 
                            defaultParameters['BinaryFileTypes'],
                            interactiveMode, debugLevel)
                else:
                    print("INFO  downloaded new file from SCM:{0}".format( currentFileName))

        ### use rsync or wget, derive command to sync custom contents, and execute command
        if localRepositoryCustom != '':
            if OSType == "Windows":
                tempDirectory = "{0}\{1}".format(localRepositoryHome,localRepositoryCustom)
            else:
                tempDirectory = "{0}/{1}".format(localRepositoryHome,localRepositoryCustom)

            os.chdir(tempDirectory)
            if debugLevel > 1:
                errorMsg = "DEBUG-2 JAOperationSync() custom directory:{0}, pwd:{1}".format(tempDirectory, os.getcwd())
                print(errorMsg)

        if commandRsync != '':
            syncCommand = "{0} {1}@{2}:/{3}".format(defaultParameters['CommandRsync'],
                            defaultParameters['SCMRsyncUserName'],
                            defaultParameters['SCMHostName'],
                            defaultParameters['SCMRepositoryCustom']
                            )
            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))
            
            ### can't get all files in one go, have to get those one by one
            returnResult, fileNames, errorMsg = GetAllFilesFromSCMUsingRsync(
                syncCommand, OSType, OSName, OSVersion, debugLevel)

        elif commandWget != '':
            syncCommand = "{0} https://{1}:{2}/{3}/".format( 
                    defaultParameters['CommandWget'],
                    defaultParameters['SCMHostName'],
                    defaultParameters['SCMPortHTTPS'],
                    defaultParameters['SCMRepositoryCustom']
            )
        
            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))
            
            ### can't get all files in one go, have to get those one by one
            returnResult, fileNames, errorMsg = GetAllFilesFromSCMUsingWget(
                syncCommand, OSType, OSName, OSVersion, debugLevel )

        if returnResult == True:
            ### If file is NEW, print that file name as NEW file.
            ### If existing file, print differences between PrevVersion and current version of the file
            for fileName in fileNames:
                currentFileName = '{0}{/1}/{2}'.format(localRepositoryHome,localRepositoryCommon, fileName)
                previousFileName = '{0}/{1}.PrevVersion/{2}'.format(localRepositoryHome,localRepositoryCommon, fileName)
                if os.path.exists(previousFileName ):
                    JAOperationCompare.JAOperationCompareFiles( 
                            currentFileName, previousFileName, 
                            defaultParameters['BinaryFileTypes'],
                            interactiveMode, debugLevel)
                else:
                    print("INFO  downloaded new file from SCM:{0}", currentFileName)


    if errorMsg != '':
        print("ERROR JAOperationSync() Sync failed with error:{0}".format(errorMsg))
    return returnStatus, errorMsg