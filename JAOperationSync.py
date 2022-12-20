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
import JAOperationSaveCompare

def GetAllFilesFromSCMUsingRsync(
    rsyncCommand:str, 
    OSType:str, OSName:str, OSVersion:str, debugLevel:int,
    interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag,
    shell, logFilePath):

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

    rsyncOutputFileName ="{0}/JAAudit.rsync.{1}".format( logFilePath, os.getpid() )

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
        shell,
        tempRsyncCommand, debugLevel, OSType)

    if returnResult == False:
        returnStatus = False
        errorMsg = "ERROR GetAllFilesFromSCMUsingRsync() unable to get file list from SCM, rsync command:{0}, return response:{1}, error:{2}".format(
            tempRsyncCommand, returnOutput, errorMsg    )
        JAGlobalLib.LogLine(
			errorMsg, 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag)
      
        return returnStatus, fileNames, errorMsg
    
    ### process index output to extract file names
    with open( rsyncOutputFileName, "r") as file:
        headerLines = True
        while True:
            errorMsg = ''
            line = file.readline()
            if not line:
                break

            ### refreshed file and new file signature in rsync log line
            if re.search(r'>f\.st|>f\+\+\+\+', line):
                ### <date> <time> [size] >f.st..... <fileName>
                ### <date> <time> [size] >f++++++++ <fileName>
                ###   0       1     2      3           4
                logLineParts = line.split()
                if len(logLineParts) > 4:
                    ### TBD if file name has extra characters on either side, strip those
                    fileNames.append(logLineParts[4])

        file.close()
        os.remove(rsyncOutputFileName)

    if debugLevel > 0:
        print("DEBUG-1 GetAllFilesFromSCMUsingRsync() files refreshed {0}".format(fileNames))

    return returnStatus, fileNames, errorMsg

def GetAllFilesFromSCMUsingWget(
    wgetCommand:str, filesToExcludeInWget:str, filesWithExecPermission:str, fileExecPermission:int,
    OSType:str, OSName:str, OSVersion:str, debugLevel:int,
    interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag,
    shell):
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
        shell,
        tempWgetCommand, debugLevel, OSType)

    if returnResult == False:
        returnStatus = False
        errorMsg = "ERROR GetAllFilesFromSCMUsingWget() unable to get file list from SCM, wget command:{0}, return response:{1}, error:{2}".format(
            tempWgetCommand, returnOutput, errorMsg    )
        JAGlobalLib.LogLine(
            errorMsg, 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag)
        
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

                    ### if current file name match to exclude list, SKIP this file
                    if re.search(filesToExcludeInWget, fileNameToFetch) != None:
                        continue

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
                            ### get file modified time on local host, 
                            fileModifiedTime = os.path.getmtime ( fileNameToFetch )

                            ### if the local file has same time stamp as that of SCM file, DO NO NOT fetch it
                            ###  this logic accuracy is one min, since SCM time is available in min, not in seconds
                            if SCMFileTimeInSec < fileModifiedTime:
                                fetchSCMFile = False

                        ### fetch the file if needed
                        if fetchSCMFile == True:
                            tempWgetCommand = "{0}{1} {2} {3}".format(
                                    wgetCommand, fileNameToFetch, wgetOutputFileOption, fileNameToFetch )

                            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                                shell,
                                tempWgetCommand, debugLevel, OSType)

                            if returnResult == False:
                                returnStatus = False
                                errorMsg = "ERROR GetAllFilesFromSCMUsingWget() unable to get the file {0} from SCM, wget command:{1}, return response:{2}, error:{3}".format(
                                    fileNameToFetch, tempWgetCommand, returnOutput, errorMsg    )
                                JAGlobalLib.LogLine(
			                        errorMsg, 
                                    interactiveMode,
                                    myColors, colorIndex, outputFileHandle, HTMLBRTag)
                            else:
                                ### set exec permission if current file name match to spec
                                if re.search(filesWithExecPermission, fileNameToFetch) != None:
                                    os.chmod(fileNameToFetch, int(fileExecPermission))

                                ### add fetched file name to the list
                                fileNames.append(fileNameToFetch)
                                if debugLevel > 1:
                                    errorMsg = "DEBUG-2 GetAllFilesFromSCMUsingWget() Fetched file {0} from SCM using the command:{1}".format(
                                        fileNameToFetch, tempWgetCommand )
                                    print(errorMsg)
                                
                        else:
                            if debugLevel > 2:
                                print("DEBUG-3 GetAllFilesFromSCM() File {0} on SCM is older than local file, not fetching it".format(fileNameToFetch))
                
        file.close()
        os.remove(wgetOutputFileName)

    if debugLevel > 0:
        print("DEBUG-1 GetAllFilesFromSCMUsingWget() files refreshed {0}".format(fileNames))

    return returnStatus, fileNames, errorMsg

def JAOperationSync(
    baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion,   
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
            errorMsg = "INFO JAOperationSync() Skipping Sync, duration not elapsed yet"
            JAGlobalLib.LogLine(
                        errorMsg, 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag)

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
                JAGlobalLib.LogLine(
			        errorMessage, 
                	interactiveMode,
                	myColors, colorIndex, outputFileHandle, HTMLBRTag)
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
                    JAGlobalLib.LogLine(
                        errorMessage, 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag)
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
                    JAGlobalLib.LogLine(
                        errorMessage, 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag)
                    return False, errorMessage 
        else:
            localRepositoryCustom = ''

        ### make a list of files to copy to save directory 
        if 'FilesToCompareAfterSync' in defaultParameters:
            filesToCompareAfterSync = defaultParameters['FilesToCompareAfterSync']

        ### create Common and Custom directories if not present yet
        prevVersionFolder = "{0}/{1}.PrevVersion".format(localRepositoryHome, localRepositoryCommon)
        if os.path.exists(prevVersionFolder) == False:
            os.mkdir(prevVersionFolder)
        prevVersionFolder = "{0}/{1}.PrevVersion".format(localRepositoryHome, localRepositoryCustom)
        if os.path.exists(prevVersionFolder) == False:
            os.mkdir(prevVersionFolder)
            
        ### delete files in *.PrevVersion directory
        import glob
        import shutil
        sourceDirCommon = "{0}/{1}".format(localRepositoryHome, localRepositoryCommon)
        destinationDirCommon = "{0}/{1}.PrevVersion".format(localRepositoryHome, localRepositoryCommon)
        sourceDirCustom = "{0}/{1}".format(localRepositoryHome, localRepositoryCustom)
        destinationDirCustom = "{0}/{1}.PrevVersion".format(localRepositoryHome, localRepositoryCustom)

        ### delete files in destination directory Common
        filesInDestinationDir = glob.glob("{0}/*".format(destinationDirCommon))
        for file in filesInDestinationDir:
            try:
                os.remove(file)
            except OSError as err:
                JAGlobalLib.LogLine(
			        "ERROR JAOperationSync() Error deleting file:{0}, OSError:{1}".format(file, OSError), 
                	interactiveMode,
                	myColors, colorIndex, outputFileHandle, HTMLBRTag)

        ### delete files in destination directory Custom
        filesInDestinationDir = glob.glob("{0}/*".format(destinationDirCustom))
        for file in filesInDestinationDir:
            try:
                os.remove(file)
            except OSError as err:
                JAGlobalLib.LogLine(
			        "ERROR JAOperationSync() Error deleting file:{0}, OSError:{1}".format(file, OSError), 
                	interactiveMode,
                	myColors, colorIndex, outputFileHandle, HTMLBRTag)

        ### copy code/config contents to Common.PrevVersion, Custom.PrevVersion directories
        ###    so that downloaded contents can be compared to previous contents and display the delta
        
        ### copy files one type at a time
        fileNames = filesToCompareAfterSync.split(' ')
        for fileName in fileNames:
            globString = r"{0}/{1}".format(sourceDirCommon, fileName)
            ### copy files from Common to .PrevVersion
            for file in glob.glob(globString):
                if debugLevel > 2:
                    print("DEBUG-3 JAOperationSync() copying file:{0} to {1}".format(file, destinationDirCommon))
                shutil.copy(file, destinationDirCommon)

            if localRepositoryCustom != '':
                globString = r"{0}/{1}".format(sourceDirCustom, fileName)
                ### copy files from Custom to .PrevVersion
                for file in glob.glob(globString):
                    if debugLevel > 2:
                        print("DEBUG-3 JAOperationSync() copying file:{0} to {1}".format(file, destinationDirCustom))
                    shutil.copy(file, destinationDirCustom)

        if 'CommandRsync' in defaultParameters:
            commandRsync = defaultParameters['CommandRsync']
        else:
            commandRsync = ''

        if 'CommandWget' in defaultParameters:
            commandWget = defaultParameters['CommandWget']
        else:
            commandWget = ''
        
        if commandRsync == '' and commandWget == '':
            errorMsg = ("ERROR JAOperationSync() Both rsync and wget commands not present, can't complete sync operation")
            JAGlobalLib.LogLine(
                errorMsg, 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag)

            return False, errorMessage

        ### counters to keep track of new files, changed files
        countNewFiles = countChangedFiles = 0

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
            syncCommand = "{0} {1}@{2}:/{3}/{4} {5}/{6}".format(
                            defaultParameters['CommandRsync'],
                            defaultParameters['SCMRsyncUserName'],
                            defaultParameters['SCMHostName'],
                            defaultParameters['SCMRepositoryBasePath'],
                            defaultParameters['SCMRepositoryCommon'],
                            localRepositoryHome, 
                            localRepositoryCommon
                            )
            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))

            ### can't get all files in one go, have to get those one by one
            returnResult, fileNames, errorMsg = GetAllFilesFromSCMUsingRsync(
                syncCommand, OSType, OSName, OSVersion, debugLevel,
                interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag,
                defaultParameters['CommandShell'],
                defaultParameters['LogFilePath'])

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
                syncCommand, 
                r'{0}'.format(defaultParameters['FilesToExcludeInWget']),
                r'{0}'.format(defaultParameters['FilesWithExecPermission']),
                defaultParameters['FileExecPermission'],
                OSType, OSName, OSVersion, debugLevel,
                interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag,
                defaultParameters['CommandShell'])

        if returnResult == True:
            ### If file is NEW, print that file name as NEW file.
            ### If existing file, print differences between PrevVersion and current version of the file
            for fileName in fileNames:
                currentFileName = '{0}/{1}/{2}'.format(localRepositoryHome,localRepositoryCommon, fileName)
                previousFileName = '{0}/{1}.PrevVersion/{2}'.format(localRepositoryHome,localRepositoryCommon, fileName)
                if os.path.exists(previousFileName ):
                    returnStatus, fileDiffer, errorMsg = JAOperationSaveCompare.JAOperationCompareFiles( 
                            currentFileName, previousFileName,
                            defaultParameters['BinaryFileTypes'],
                            '', # compare type, find out compare type for binary files automatically
                            defaultParameters['CompareCommand'],
                            False,"","", # not a host to host compare scenario
                            "", # no additional info to log
                            interactiveMode, debugLevel,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag,
                            OSType,
                            defaultParameters['CommandShell'],
                            defaultParameters['LogFilePath'])

                    if fileDiffer == True:
                        countChangedFiles += 1
                else:
                    JAGlobalLib.LogLine(
                        "INFO  JAOperationSync() downloaded new file from SCM:{0}".format( currentFileName), 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag)

                    countNewFiles += 1

            errorMsg = "INFO JAOperationSync() Repository:{0}, Number of new files fetched:{1}, number of updated files fetched:{2}".format(
                    localRepositoryCommon, countNewFiles, countChangedFiles)
            JAGlobalLib.LogLine(
                errorMsg, 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag)
        
        countChangedFiles = countNewFiles = 0

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
            syncCommand = "{0} {1}@{2}:/{3}/{4} {5}/{6}".format(
                            defaultParameters['CommandRsync'],
                            defaultParameters['SCMRsyncUserName'],
                            defaultParameters['SCMHostName'],
                            defaultParameters['SCMRepositoryBasePath'],
                            defaultParameters['SCMRepositoryCustom'],
                            localRepositoryHome, 
                            localRepositoryCustom
                            )
            if debugLevel > 2:
                print("DEBUG-2 JAOperationSync() syncCommand:{0}".format(syncCommand))
            
            ### can't get all files in one go, have to get those one by one
            returnResult, fileNames, errorMsg = GetAllFilesFromSCMUsingRsync(
                syncCommand, OSType, OSName, OSVersion, debugLevel,
                interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag,
                defaultParameters['CommandShell'],
                defaultParameters['LogFilePath'])

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
                syncCommand, 
                r'{0}'.format(defaultParameters['FilesToExcludeInWget']),
                r'{0}'.format(defaultParameters['FilesWithExecPermission']),
                defaultParameters['FileExecPermission'],
                OSType, OSName, OSVersion, debugLevel,
                interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag,
                defaultParameters['CommandShell'] )

        if returnResult == True:
            ### If file is NEW, print that file name as NEW file.
            ### If existing file, print differences between PrevVersion and current version of the file
            for fileName in fileNames:
                currentFileName = '{0}/{1}/{2}'.format(localRepositoryHome,localRepositoryCustom, fileName)
                previousFileName = '{0}/{1}.PrevVersion/{2}'.format(localRepositoryHome,localRepositoryCustom, fileName)
                if os.path.exists(previousFileName ):
                    returnStatus, fileDiffer, errorMsg = JAOperationSaveCompare.JAOperationCompareFiles( 
                            currentFileName, previousFileName, 
                            False,  # prevHasCheckSum = False
                            defaultParameters['BinaryFileTypes'],
                            defaultParameters['CompareCommand'],
                            False,"","", # not a host to host compare scenario
                            "", # no additional info to log
                            interactiveMode, debugLevel,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag,
                            OSType,
                            defaultParameters['CommandShell'],
                            defaultParameters['LogFilePath'])
                    if fileDiffer == True:
                        countChangedFiles += 1
                else:
                    JAGlobalLib.LogLine(
			            "INFO  JAOperationSync() downloaded new file from SCM:{0}".format( currentFileName), 
                	    interactiveMode,
                	    myColors, colorIndex, outputFileHandle, HTMLBRTag)
                    countNewFiles += 1

            errorMsg = ("INFO  JAOperationSync() Repository:{0}, Number of new files fetched:{1}, number of updated files fetched:{2}".format(
                    localRepositoryCustom, countNewFiles, countChangedFiles))
            JAGlobalLib.LogLine(
                errorMsg, 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag)

            ### if file is to be operated on post fetch, execute those commands
            ### TBD add later

    ### operation completed, update the history file to track the last time when it is completed
    JAGlobalLib.JAUpdateHistoryFileName(subsystem, "sync", defaultParameters)

    return returnStatus, errorMsg