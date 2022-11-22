"""
This module contains the functions and main logic to compare two files

Author: havembha@gmail.com, 2022-11-21

"""
import re
import JAGlobalLib

def JAOperationCompareFiles(
    currentFileName:str, previousFileName:str, binFileTypes:str, compareCommand:str,
    OSType, OSName, OSVersion,
    interactiveMode:bool, debugLevel:int):
    """
    If files passed is binary type, computes the checksum and compares the checksum
    If files passed is text type, first computes the check sum to see whethey are same.
    If not same, compares two files using diff
    """
    import hashlib
    returnStatus = True
    fileDiffer = False

    if debugLevel > 1:
        print("INFO JAOperationCompareFiles() Comparing current file:{0} to reference file{1}".format(
            currentFileName, previousFileName
        ))
  
    try:
        ### compute checksum of two files and compare
        with open(currentFileName,"rb") as f:
            md5_hash = hashlib.md5()
            # Read and update hash in chunks of 4K
            for byte_block in iter(lambda: f.read(32768),b""):
                md5_hash.update(byte_block)
            currentFileMD5Digest = md5_hash.hexdigest()

    except OSError as err:
        print("ERROR JAOperationCompareFiles() Not able to open file:{0}".format(currentFileName))
        return returnStatus, True

    try:
        with open(previousFileName,"rb") as f:
            md5_hash = hashlib.md5()
            # Read and update hash in chunks of 4K
            for byte_block in iter(lambda: f.read(32768),b""):
                md5_hash.update(byte_block)
            previousFileMD5Digest = md5_hash.hexdigest()
    except OSError as err:
        print("ERROR JAOperationCompareFiles() Not able to open file:{0}".format(previousFileName))
        return returnStatus, True

    if currentFileMD5Digest != previousFileMD5Digest:
        if debugLevel > 0:
            print("DEBUG-1 JAOperationCompareFiles() MD5 checksum differ")
        fileDiffer = True

    ### files differ, and file type is not binary, compare word by word
    if fileDiffer == True:
        if re.search(binFileTypes, currentFileName) :
            return returnStatus, True

        tempCompareCommand = "diff {0} {1} {2}".format(currentFileName, previousFileName )
        returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                tempCompareCommand, debugLevel)

    return returnStatus