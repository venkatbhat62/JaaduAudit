"""
This module contains the functions and main logic to compare two files

Author: havembha@gmail.com, 2022-11-21

"""
import re
import os
import JAGlobalLib

def JAOperationsCompareReadConfig( 
        baseConfigFileName, 
        subsystem, 
        myPlatform, 
        appVersion,
        OSType, OSName, OSVersion, logFilePath,  
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel, currentTime,
        saveCompareSpec ):

    
    """
    This function reads the compare config in the form:
#    <ObjectName>:  If the operaton is save, the command output or reference file will be saved with this name. 
#            If the reference file is binary type, MD5 checksum is stored with this name
#            If the operatoin is compare, object saved before will be compared with current value.
#        Command: - If the operation is save, gather environment details using this command and save the content with <ObjectName>
#            If the operation is compare, gather current environment details using this command and compare to previously 
#                saved content with <ObjectName>
#            Only commands listed in JAAllowedCommands.yml are allowed. 
#            On windows, these commands are executed via powershell, whose base path is defined in environment spec file
#               via the parameter 'CommandPowershell'
#            For a given object name, either Command or FileNames can be specified, NOT both.
#        CompareType: optional - Checksum, checksum, Text or text 
#             Specify Checksum to compare binary files or any files where text comparison is not needed.
#             If not specified, 
#                On Unix/Linux hosts, it uses 'file' command to determin the file type.
#                On Windows, file type defined in environment spec file via the parameter 'BinaryFileTypes' is used
#                For binary files, defaults to Checksum
#                For ASCII text, defaults to Text       
#        Environment: optional - match to one of the environment defined in JAEnvironment.yml file
#            if the current hostname match to the environment spec, this ObjectName will be saved or compared.
#            Default - All environment
#        FileNames: file names in CSV form or find command that returns file names in multiple lines
#            each file name is suffixed with NameSuffix.
#            If operation is save, save the contents of the files with <fileName>.<ObjectName> without the path name.
#            If operation is compare, current file is compared to saved file.
#            For a given object name, either Command or FileNames can be specified, NOT both.
#            On Linux/Unix host, if the first word is 'find', it will execute the comamnd and work all files names
#               returned in the command response
#            On Windows host, if the first word is 'get-childitem', it will execute the comamnd and work all files names
#               returned in the command response
#        SkipH2H: optional - Yes, YES, NO or No 
#            Skip this file from upload/download actions, keep the file on local host only.
#            Suggest to use this option to keep any sensitive information on local host only, not to upload to SCM.
#            Also, use this when the object or file is application to this host only like certificate        
#            Default - No
#
    """
    returnStatus = False
    errorMsg = ''
    numberOfItems = 0
    numberOfErrors = 0
    numberOfWarnings = 0

    
    return returnStatus, errorMsg

def JAOperationCompareFiles(
    currentFileName:str, previousFileName:str, binFileTypes:str, compareCommand:str,
    compareH2H:bool, compareCommandH2H:str, compareCommandH2HSedCommand:str,
    logAdditionalInfo:str,
    interactiveMode:bool, debugLevel:int,
    myColors, colorIndex:int, outputFileHandle, HTMLBRTag:str,
    OSType):
    """
    If files passed is binary type, computes the checksum and compares the checksum
    If files passed is text type, first computes the check sum to see whethey are same.
    If not same, compares two files using diff
    """
    import hashlib
    returnStatus = True
    fileDiffer = False

    if debugLevel > 0:
        print("DEBUG-1 JAOperationCompareFiles() Comparing current file:{0} to reference file{1}".format(
            currentFileName, previousFileName      ))
  
    errorMsg = ''

    ### return if any of the two files not present
    if os.path.exists( currentFileName) == False:
        errorMsg += "ERROR JAOperationCompareFiles() Current file not present:{0}\n".format(currentFileName)
        returnStatus = False
    if os.path.exists( previousFileName) == False:
        errorMsg += "ERROR JAOperationCompareFiles() Reference file not present:{0}\n".format(previousFileName)
        returnStatus = False

    if returnStatus == False:
        JAGlobalLib.LogLine(
			errorMsg, 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, False, errorMsg

    ### compute MD5 checksum and compare 
    try:
        ### compute checksum of two files and compare
        with open(currentFileName,"rb") as f:
            md5_hash = hashlib.md5()
            # Read and update hash in chunks of 4K
            for byte_block in iter(lambda: f.read(32768),b""):
                md5_hash.update(byte_block)
            currentFileMD5Digest = md5_hash.hexdigest()

    except OSError as err:
        JAGlobalLib.LogLine(
			"ERROR JAOperationCompareFiles() Not able to open file:{0}".format(currentFileName), 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, True, errorMsg

    try:
        with open(previousFileName,"rb") as f:
            md5_hash = hashlib.md5()
            # Read and update hash in chunks of 4K
            for byte_block in iter(lambda: f.read(32768),b""):
                md5_hash.update(byte_block)
            previousFileMD5Digest = md5_hash.hexdigest()
    except OSError as err:
        JAGlobalLib.LogLine(
			"ERROR JAOperationCompareFiles() Not able to open file:{0}".format(previousFileName), 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, True, errorMsg

    if currentFileMD5Digest != previousFileMD5Digest:
        if debugLevel > 1:
            print("DEBUG-2 JAOperationCompareFiles() MD5 checksum differ")
        fileDiffer = True

    ### files differ, and file type is not binary, compare word by word
    if fileDiffer == True:
        if re.search(binFileTypes, currentFileName) :
            JAGlobalLib.LogLine(
            "DIFF  current file:{0} differs from reference file:{1}".format(currentFileName, previousFileName ), 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

            # binary file, no further compare needed, return status
            return returnStatus, fileDiffer, errorMsg

        ### for host to host compare, use H2H compare specific command and sed command
        if compareH2H == True:
            # host to host compare scenario
            tempCompareCommand = "{0} {1} {2} {3}".format( compareCommandH2H, currentFileName, previousFileName, compareCommandH2HSedCommand )
        else:
            # regular compare scenario
            if OSType == "Windows":
                tempCompareCommand = "{0} (cat {1}) (cat {2})".format(compareCommand, currentFileName, previousFileName )
            else:
                ### Unix/Linux
                tempCompareCommand = "{0} {1} {2}".format(compareCommand, currentFileName, previousFileName )

        if debugLevel > 1:
            print("DEBUG-2 JAOperationCompareFiles() comparing files with command:{0}".format(tempCompareCommand))

        returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                tempCompareCommand, debugLevel)

        if returnResult == False:
            returnStatus = False
            errorMsg = "ERROR JAOperationCompareFiles() Unable to execute diff command:{0}, return response:{1}, error:{2}".format(
                tempCompareCommand, returnOutput, errorMsg    )
            JAGlobalLib.LogLine(
                errorMsg, 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            
        else:
            JAGlobalLib.LogLine(
                "JAAuditDiffStart++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++", 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            if logAdditionalInfo != '':
                ### print additional info passed
                JAGlobalLib.LogLine(
                    "INFO JAOperationCompareFiles() Comparing output of command:{0}\n".format(logAdditionalInfo), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            
            ### treat windows output 
            if OSType == 'Windows':
                returnOutput = returnOutput.replace(r'\r', r'\n')
                returnOutputLines =returnOutput.split(r'\n')
                ### delete first three lines and last two lines from the list
                del returnOutputLines[:3], returnOutputLines[-2:]

                ### returnOutputLines is a list, can't pass it to LogLine directly.
                for line in returnOutputLines:
                    JAGlobalLib.LogLine(
                            line,
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag,
                            True, ## output of compare operation
                            OSType)    
            else:
                JAGlobalLib.LogLine(
                        returnOutput,
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag,
                        True, ## output of compare operation
                        OSType)    

            JAGlobalLib.LogLine(
                "JAAuditDiffEnd----------------------------------------------------------------------------------", 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

            ### if SedCmd is present, apply those to see whether all differences are ignorable differences
            sedCmdFileName = '{0}.SedCmd'.format(previousFileName)
            if os.path.exists( sedCmdFileName):
                ### for host to host compare, use H2H compare specific command and sed command
                if compareH2H == True:
                    # host to host compare scenario
                    tempCompareCommand = "{0} {1} {2} {3}".format( compareCommandH2H, currentFileName, previousFileName, sedCmdFileName, compareCommandH2HSedCommand)
                else:
                    # regular compare scenario
                    if OSType == "Windows":
                        ### TBD make a wrapper script that applies series of pattern match and replace commands on each line
                        ### use (svn info filename) -match '<pattern>' -replace '<pattern>'
                        tempCompareCommand = "{0} (cat {1}) (cat {2})".format(compareCommand, currentFileName, previousFileName )
                    else:
                        ### Unix/Linux
                        tempCompareCommand = "{0} {1} {2} {3}".format( compareCommandH2H, currentFileName, previousFileName, sedCmdFileName)
 
                if debugLevel > 1:
                    print("DEBUG-2 JAOperationCompareFiles() Finding non-ignorable differences using command:{0}".format(tempCompareCommand))

                returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                        tempCompareCommand, debugLevel)

                if returnResult == False:
                    returnStatus = False
                    errorMsg = "ERROR JAOperationCompareFiles() Unable to execute diff command:{0}, return response:{1}, error:{2}".format(
                        tempCompareCommand, returnOutput, errorMsg    )
                    JAGlobalLib.LogLine(
                        errorMsg, 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    
                else:
                    ignorableDifferences = False
                    ### treat windows output 
                    if OSType == 'Windows':
                        returnOutput = returnOutput.replace(r'\r', r'\n')
                        returnOutputLines =returnOutput.split(r'\n')
                        ### delete first three lines and last two lines from the list
                        del returnOutputLines[:3], returnOutputLines[-2:]

                        if len(returnOutputLines) > 0:
                            ### returnOutputLines is a list, can't pass it to LogLine directly.
                            JAGlobalLib.LogLine(
                                "JAAuditIgnoreKnownDiffStart++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++", 
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                            for line in returnOutputLines:
                                JAGlobalLib.LogLine(
                                        line,
                                        interactiveMode,
                                        myColors, colorIndex, outputFileHandle, HTMLBRTag,
                                        True, ## output of compare operation
                                        OSType) 
                        else:
                            ignorableDifferences = True

                    else:
                        if len(returnOutput) > 0:
                            JAGlobalLib.LogLine(
                                "JAAuditIgnoreKnownDiffStart++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++", 
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                            JAGlobalLib.LogLine(
                                returnOutput,
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag,
                                True, ## output of compare operation
                                OSType)    
                        else:
                            ignorableDifferences = True

                    if ignorableDifferences == True:
                        JAGlobalLib.LogLine(
                            "PASS  seen only ignorable differences, current file:{0}, reference file:{1}".format(
                                currentFileName, previousFileName ), 
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        fileDiffer = False
                    else:
                        JAGlobalLib.LogLine(
                            "JAAuditIgnoreKnownDiffEnd----------------------------------------------------------------------------------", 
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    if fileDiffer == True:
        JAGlobalLib.LogLine(
            "DIFF  current file:{0} differs from reference file:{1}".format(currentFileName, previousFileName ), 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
    returnStatus = True

    return returnStatus, fileDiffer, errorMsg

def JAOperationsSave( 
    baseConfigFileName, 
    subsystem, 
    myPlatform, 
    appVersion,
    OSType, OSName, OSVersion, logFilePath,  
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime ):

    returnStatus = True
    numberOfItems = 0
    numberOfErrors = 0
    numberOfWarnings = 0
    errorMsg = ''

    return returnStatus, numberOfItems

def JAOperationsCompare( 
    baseConfigFileName, 
    subsystem, 
    myPlatform, 
    appVersion,
    OSType, OSName, OSVersion, logFilePath,  
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime ):