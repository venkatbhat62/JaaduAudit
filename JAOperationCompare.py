"""
This module contains the functions and main logic to compare two files

Author: havembha@gmail.com, 2022-11-21

"""
import re
import os
import JAGlobalLib

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
            # binary file, no further compare needed, return status
            return returnStatus, fileDiffer, errorMsg

        ### for host to host compare, use H2H compare specific command and sed command
        if compareH2H == True:
            # host to host compare scenario
            tempCompareCommand = "{0} {1} {2} {3}".format( compareCommandH2H, compareCommandH2HSedCommand, currentFileName, previousFileName )
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

    return returnStatus, fileDiffer, errorMsg