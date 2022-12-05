"""
This module contains the functions and main logic to compare two files

Author: havembha@gmail.com, 2022-11-21

"""
import re
import os
import JAGlobalLib
from collections import defaultdict
import hashlib
import shutil

def JAOperationReadConfig( 
        baseConfigFileName, 
        subsystem, 
        version, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel,
        saveCompareParameters, allowedCommands ):

    
    """
    This function reads the compare config in the form:
#    <ObjectName>: prefix used to formulate the filename of an object being saved or compared.
#            If the operaton is save, the command output or reference file will be saved with this name as prefix. 
#            If the operatoin is compare, object saved before with this name as prefix will be compared with current value.
#            ObjectName needs to be unique across yml file. Duplicate not allowed by yml syntax.
#        Command: - If the operation is save, gather environment details using this command and save the content with <ObjectName>
#            If the operation is compare, gather current environment details using this command and compare to previously 
#                saved content with <ObjectName>
#            Only commands listed in JAAllowedCommands.yml are allowed. 
#            On windows, these commands are executed via powershell, whose base path is defined in environment spec file
#               via the parameter 'CommandPowershell'
#            For a given object name, either Command or FileNames can be specified.
#               If both are specified, Command definition takes precedence.
#        CompareType: optional - Checksum, checksum, Text or text 
#             Specify Checksum to compare binary files or any files where text comparison is not needed.
#             If not specified, 
#                On Unix/Linux hosts, it uses 'file' command to determin the file type.
#                On Windows, file type defined in environment spec file via the parameter 'BinaryFileTypes' is used
#                For binary files, defaults to Checksum
#                For ASCII text, defaults to text       
#        Environment: optional - match to one of the environment defined in JAEnvironment.yml file
#            if the current hostname match to the environment spec, this ObjectName will be saved or compared.
#            Default - all environment
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
#            Default - no
#
   Parameters passed:
        baseConfigFileName - Vaue of 'AppConfig' parameter defined in JAEnvironment.yml for that host or component for that environment
        subsystem - if not empty, it will be Prefixed to derive config file
        version - if not empty, suffixed to the baseConfigFileName to find release specific config file
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel, 
        saveCompareSpec - full details, along with default parameters assigned, are returned in this dictionary

    Returned Values:
        returnStatus - True on success, False upon file read error
        numberOfItems - number of items read

    """
    returnStatus = False
    errorMsg = ''
    numberOfItems = 0
    numberOfErrors = 0
    numberOfWarnings = 0

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAOperationReadConfig() subsystem:{0}, AppConfig:{1}, version:{2} ".format(
                subsystem, baseConfigFileName, version),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### parameter names supported in SaveCompare object definition file
    saveCompareAttributes = [
        'Command',
        'CompareType',
        'Environment',
        'FileNames',
        'SkipH2H'
        ]
    baseConfigFileNameParts = baseConfigFileName.split('.')
    if len(baseConfigFileNameParts) != 2:
        JAGlobalLib.LogLine(
            "ERROR JAOperationReadConfig() AppConfig name not in expected format, no . (dot) in filename:|{0}|".format(baseConfigFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        return returnStatus, numberOfItems

    ### derive the save compare spec file, first check under LocalRepositoryCustom, next under LocalRepositoryCommon
    returnStatus, saveCompareSpecFileName, errorMsg = JAGlobalLib.JADeriveConfigFileName( 
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCustom']),
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCommon']),
          subsystem, baseConfigFileName, version, debugLevel )
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "ERROR JAOperationReadConfig() AppConfig:|{0}| not present, error:|{1}|".format(baseConfigFileName, errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, numberOfItems
        
    if debugLevel > 1:
        JAGlobalLib.LogLine(
            "DEBUG-2 JAOperationReadConfig() Derived AppConfig file name using subsystem and version as part of file name:|{0}|".format(saveCompareSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### Now read the yml file
    # use limited yaml reader when yaml is not available
    if yamlModulePresent == True:
        try:
            import yaml
            with open(saveCompareSpecFileName, "r") as file:
                saveCompareSpec = yaml.load(file, Loader=yaml.FullLoader)
                file.close()
        except OSError as err:
            errorMsg = "ERROR JAOperationReadConfig() Can not open configFile:|{0}|, OS error:|{1}|\n".format(
                saveCompareSpecFileName, err)
            JAGlobalLib.LogLine(
                "ERROR JAOperationReadConfig() AppConfig:|{0}| not present, error:|{1}|".format(saveCompareSpecFileName, errorMsg),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    else:
        saveCompareSpec = JAGlobalLib.JAYamlLoad(saveCompareSpecFileName)

    errorMsg = ''

    tempAttributes = defaultdict(dict)

    for objectName, attributes in saveCompareSpec.items():
        saveParamValue = True
        ### default attributes
        tempAttributes['SkipH2H'] = 'no'
        tempAttributes['FileNames'] = tempAttributes['Command'] = None
        tempAttributes['CompareType'] = 'text'
        
        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-2 JAOperationReadConfig() processing objectName:|{0}|".format(objectName),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        for paramName, paramValue in attributes.items():
            ### if the value is True or False type, it is treated as boolean, can't use .strip() on that paramValue
            if paramName != "SkipH2H":
                paramValue = paramValue.strip()
            if paramName not in saveCompareAttributes:
                JAGlobalLib.LogLine(
                    "ERROR JAOperationReadConfig() Unknown parameter name:|{0}|, parameter value:|{1}| for the object:|{2}|".format(
                        paramName, paramValue, objectName),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                numberOfErrors += 1
            else:
                ### check for valid param values
                if paramName == 'Command':
                    ### separate command words in param value. commands may be separated by ; or |
                    commands = re.split(r';|\|', paramValue)
                    for command in commands:
                        ## remove leading space if any
                        command = command.lstrip()

                        ### separate words
                        commandWords = command.split()
                        if len(commandWords) > 0:
                            ### get first word from this command sentence
                            command = commandWords[0]
                        if OSType == "Windows":
                            ### convert the command to lower case
                            command = command.lower()
                        if command not in allowedCommands:
                            numberOfItems +=1
                            saveParamValue = False
                            JAGlobalLib.LogLine(
                                "WARN JAOperationReadConfig() Unsupported command:|{0}| in paramValue:|{1}|, for parameter:|{2}| and objectName:|{3}|, Skipping this object definition".format(
                                    command, paramValue, paramName, objectName),
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                            ### discard the current object spec
                            break
                elif paramName == 'Environment':
                    if paramValue != defaultParameters['Environment']:
                        saveParamValue = False
                        ### skip current object spec, current host's environment is not matching
                        break
                elif paramName == 'CompareType' :
                    paramValue = paramValue.lower()

                if saveParamValue == True:   
                    tempAttributes[paramName] = paramValue
        if saveParamValue == True:
            if tempAttributes['Command'] != None:
                ### command definition takes precedence over FileNames spec
                ### on windows host, prefix the command with powershell command
                if OSType == "Windows":
                    tempCommandToGetEnvDetails = '{0} {1}'.format(
                        defaultParameters['CommandPowershell'], tempAttributes['Command']) 
                else:
                    tempCommandToGetEnvDetails =  tempAttributes['Command']
                tempCommandToGetEnvDetails = os.path.expandvars( tempCommandToGetEnvDetails ) 

                saveCompareParameters[objectName]['Command'] = tempCommandToGetEnvDetails
                saveCompareParameters[objectName]['SkipH2H'] = tempAttributes['SkipH2H']
                saveCompareParameters[objectName]['CompareType'] = tempAttributes['CompareType']
                saveCompareParameters[objectName]['FileNames'] = None

                if tempAttributes['FileNames'] != None:
                    errorMsg = "WARN JAOperationReadConfig() Both 'Command' and 'FileNames' are specified for objectName:|{0}|, saved Command spec:|{1}|, ignored FileNames spec:|{2}|".format(
                                objectName, tempAttributes['Command'], tempAttributes['FileNames'])
                    JAGlobalLib.LogLine(
                        errorMsg,
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1      
                else:
                    numberOfItems += 1
            elif tempAttributes['FileNames'] != None:
                fileNamesHasCommand = False
                ### if the first word of FileNames is one of allowed commands, execute the command to get list of files
                ### check for valid param values
                wordsInFileNames = tempAttributes['FileNames'].split()
                if len(wordsInFileNames) > 1:
                    if wordsInFileNames[0] in allowedCommands:
                        fileNamesHasCommand = True
                        ### FileNames spec contains command to be executed to derive file names
                        ### separate command words in param value. commands may be separated by ; or || or && or | (pipe sign)
                        commands = re.split(r';|\|\||&&|\|', tempAttributes['FileNames'])
                        for command in commands:
                            ## remove leading space if any
                            command = command.lstrip()

                            ### separate words
                            commandWords = command.split()
                            if len(commandWords) > 0:
                                ### get first word from this command sentence
                                command = commandWords[0]
                            if OSType == "Windows":
                                ### convert the command to lower case
                                command = command.lower()
                            if command not in allowedCommands:
                                JAGlobalLib.LogLine(
                                    "WARN JAOperationReadConfig() Unsupported command:|{0}| in paramValue:|{1}|, for parameter:|{2}| and objectName:|{3}|, Skipping this object definition".format(
                                        command, paramValue, paramName, objectName),
                                    interactiveMode,
                                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                                numberOfWarnings += 1
                                saveParamValue = False
                                ### discard this object definition
                                break
                        
                        if saveParamValue == True:
                            ### on windows host, prefix the command with powershell command
                            if OSType == "Windows":
                                tempCommandToGetFileDetails = '{0} {1}'.format(
                                    defaultParameters['CommandPowershell'], tempAttributes['FileNames']) 
                            else:
                                 tempCommandToGetFileDetails =  tempAttributes['FileNames']
                            tempCommandToGetFileDetails = os.path.expandvars( tempCommandToGetFileDetails ) 

                            ### now execute the command to get file names
                            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                                tempCommandToGetFileDetails, debugLevel, OSType)
                            if returnResult == False:
                                if re.match(r'File not found', errorMsg) != True:
                                    JAGlobalLib.LogLine(
                                        "WARN JAOperationReadConfig() File not found, error getting file list by executing command:|{0}|, error:|{1}|".format(
                                                tempCommandToGetFileDetails, errorMsg), 
                                        interactiveMode,
                                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                                    numberOfWarnings += 1
                                    saveParamValue = False
                                    ### discard this object spec
                                    break
                            else:
                                if debugLevel > 1:
                                    JAGlobalLib.LogLine(
                                        "DEBUG-2 JAOperationReadConfig() Execution of command:|{0}|, resulted in output:|{1}|".format(
                                                tempCommandToGetFileDetails, returnOutput), 
                                        interactiveMode,
                                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                                
                                if OSType == "Windows":
                                    ### skip first 3 items and last item from the returnOutput list, those have std info from powershell
                                    returnOutput = returnOutput.replace(r'\r', r'\n')
                                    returnOutputLines =returnOutput.split(r'\n')
                                    ### delete last line (']') from the list
                                    del returnOutputLines[-1:]

                                    ### extract 2nd field value only to discoveredFileNames list

                                for line in returnOutputLines:
                                    if OSType == "Windows":
                                        ### each line is of the form: 'JAAudit.py"
                                        ###                                ^^^^^^^^^^ <--- file name 
                                        lineParts = re.findall(r"', '(.+)$", line)
                                        if len(lineParts) > 0:
                                            line = lineParts[0]
                                        else:
                                            lineParts = re.findall(r"\['(.+)$", line)
                                            if len(lineParts) > 0:
                                                line = lineParts[0]
                                        # print("line:|{0}|".format(line))
                                    ### formulate objectName as ObjectName.fileNameWitoutPath
                                    tempObjectName = '{0}.{1}'.format( objectName, os.path.basename(line)  )
                                    saveCompareParameters[tempObjectName]['FileNames'] = line
                                    saveCompareParameters[tempObjectName]['SkipH2H'] = tempAttributes['SkipH2H'] 
                                    saveCompareParameters[tempObjectName]['CompareType'] = tempAttributes['CompareType']
                                    saveCompareParameters[tempObjectName]['Command'] = None
                                    numberOfItems += 1
                    
                if fileNamesHasCommand == False:
                    ### expand environment variables
                    tempAttributes['FileNames'] = os.path.expandvars( tempAttributes['FileNames'] ) 

                    ### if fileNames is in CSV format, split each part and store them separately in saveCompareParameters
                    if re.search(r',', tempAttributes['FileNames']):
                        fileNames = tempAttributes['FileNames'].split(',')
                    else:
                        fileNames = [tempAttributes['FileNames']]

                    for fileName in fileNames:
                        fileName = fileName.strip()
                        ### formulate objectName as ObjectName.fileNameWitoutPath
                        tempObjectName = '{0}.{1}'.format( objectName, os.path.basename(fileName)  )
                        saveCompareParameters[tempObjectName]['FileNames'] = fileName
                        saveCompareParameters[tempObjectName]['SkipH2H'] = tempAttributes['SkipH2H'] 
                        saveCompareParameters[tempObjectName]['CompareType'] = tempAttributes['CompareType']
                        saveCompareParameters[tempObjectName]['Command'] = None
                        numberOfItems += 1
            else:
                errorMsg = "WARN JAOperationReadConfig() Both 'Command' and 'FileNames' spec missing for objectName:|{0}|, ignored this object spec".format(
                            objectName)
                JAGlobalLib.LogLine(
                    errorMsg,
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                numberOfWarnings += 1  
        else:
            ### DO NOT use current objectName
            saveCompareParameters[objectName]['Command'] = None
            saveCompareParameters[objectName]['FileNames'] = None

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAOperationReadConfig() Read {0} items with {1} warnings, {2} errors from AppConfig:{3}".format(
                numberOfItems, numberOfWarnings, numberOfErrors, baseConfigFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        if debugLevel > 1:
            for objectName in saveCompareParameters:
                JAGlobalLib.LogLine(
                    "DEBUG-2 JAOperationReadConfig() ObjectName:|{0}|, Command:|{1}|, FileNames:|{2}|, CompareType:|{3}|, SkipH2H:|{4}|".format(
                        objectName, 
                        saveCompareParameters[objectName]['Command'],
                        saveCompareParameters[objectName]['FileNames'],
                        saveCompareParameters[objectName]['CompareType'],
                        saveCompareParameters[objectName]['SkipH2H']
                        ),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return returnStatus, numberOfItems

def JAPrepareUploadFileList(
    baseConfigFileName, 
    subsystem, 
    OSType, 
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode,
    defaultParameters, saveCompareParameters,
    debugLevel ):

    """
    This function parses the saveCompareParameters list, and populates defaultParameters['UploadFileNames']
    Excludes object with SkipH2H flag True

    The file names in defaultParameters['UploadFileNames'] will be used to upload those files to SCM Web server
    or download those files from SCM web server

    The file name will not have full path, just the file name portion only 
        For upload operation, the file is assumed to be under saveDir
        For download operation, file file will be downloaded to saveDir

    Parameters passed:
        defaultParameters
        saveCompareParameters - this hash contains below attributes for each object. Object name itself is the filename.
            'Command',
            'CompareType',
            'Environment',
            'FileNames',
            'SkipH2H'

    Returned result
        number of files in file list

    """

    ### save file to the list, this will be used to download files later.
    fileName = "{0}{1}.save".format( subsystem, baseConfigFileName  )
    fileList = []
    fileList.append(fileName)

    for objectName in saveCompareParameters:
        attributes = saveCompareParameters[objectName]
        if attributes['SkipH2H'] == 'no' or attributes['SkipH2H'] == 'No' or attributes['SkipH2H'] == None:
            if attributes['CompareType'] == 'text' or attributes['CompareType'] == 'Text':
                ### include this file for upload/download
                fileList.append(objectName)
            else:
                ### include checksum file name
                fileList.append(objectName + ".checksum")
        else:
            if debugLevel > 1:
                JAGlobalLib.LogLine(
                    "DEBUG-2 JAPrepareUploadFileList() SkipH2H is True, skipping the object:{0}".format(objectName),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
    defaultParameters['UploadFileNames'] = fileList
    return len(defaultParameters['UploadFileNames'])
 
def JAOperationCompareFiles(
    currentFileName:str, previousFileName:str, 
    binFileTypes:str, compareType:str, compareCommand:str,
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
    returnStatus = True
    fileDiffer = False

    if debugLevel > 0:
        print("DEBUG-1 JAOperationCompareFiles() Comparing current file:{0} to reference file{1}".format(
            currentFileName, previousFileName      ))
  
    errorMsg = ''

    ### return if any of the two files not present
    if os.path.exists( currentFileName) == False:
        if logAdditionalInfo != '':
            ### this is the case of comparing the output of command
            errorMsg += "ERROR JAOperationCompareFiles() output of command:|{0}| not present\n".format(logAdditionalInfo)
        else:
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
            # Read and update hash in chunks of 8K
            for byte_block in iter(lambda: f.read(32768),b""):
                md5_hash.update(byte_block)
            currentFileMD5Digest = md5_hash.hexdigest()
            f.close()

    except OSError as err:
        JAGlobalLib.LogLine(
			"ERROR JAOperationCompareFiles() Not able to open file:{0}".format(currentFileName), 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, True, errorMsg

    try:
        ### previous file has data contents, compute checksum
        with open(previousFileName,"rb") as f:            
            md5_hash = hashlib.md5()
            # Read and update hash in chunks of 8K
            for byte_block in iter(lambda: f.read(32768),b""):
                md5_hash.update(byte_block)
            previousFileMD5Digest = md5_hash.hexdigest()
            f.close()
            
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
        if compareType == '' or compareType == None:
            if re.search(binFileTypes, currentFileName) :
                JAGlobalLib.LogLine(
                "DIFF  current file:{0} differs from reference file:{1}".format(currentFileName, previousFileName ), 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                # binary file, no further compare needed, return status
                return returnStatus, fileDiffer, errorMsg
        elif compareType == 'checksum':
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
            print("DEBUG-2 JAOperationCompareFiles() comparing files with command:|{0}|".format(tempCompareCommand))

        returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                tempCompareCommand, debugLevel, OSType)

        if returnResult == False:
            returnStatus = False
            errorMsg = "ERROR JAOperationCompareFiles() Unable to execute diff command:|{0}|, return response:{1}, error:{2}".format(
                tempCompareCommand, returnOutput, errorMsg    )
            JAGlobalLib.LogLine(
                errorMsg, 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            
        else:
            JAGlobalLib.LogLine(
                tempCompareCommand, 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            JAGlobalLib.LogLine(
                "JAAuditDiffStart++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++", 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            if logAdditionalInfo != '':
                ### print additional info passed
                JAGlobalLib.LogLine(
                    "INFO JAOperationCompareFiles() Comparing output of command:|{0}|\n".format(logAdditionalInfo), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            
            ### treat windows output 
            if OSType == 'Windows':
                ### skip first 3 items and last item from the returnOutput list, those have std info from powershell
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
                    print("DEBUG-2 JAOperationCompareFiles() Finding non-ignorable differences using command:|{0}|".format(tempCompareCommand))

                returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                        tempCompareCommand, debugLevel, OSType)

                if returnResult == False:
                    returnStatus = False
                    errorMsg = "ERROR JAOperationCompareFiles() Unable to execute diff command:|{0}|, return response:{1}, error:{2}".format(
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
                            "PASS  seen only ignorable differences, current file:|{0}|, reference file:|{1}|".format(
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
        if logAdditionalInfo != '':
            JAGlobalLib.LogLine(
                "DIFF  output of command:|{0}| differs from reference file:{1}".format(logAdditionalInfo, previousFileName ), 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        else:
            JAGlobalLib.LogLine(
                "DIFF  current file:{0} differs from reference file:{1}".format(currentFileName, previousFileName ), 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
    returnStatus = True

    return returnStatus, fileDiffer, errorMsg

def JAOperationSaveCompare( 
    baseConfigFileName, 
    subsystem, 
    myPlatform, 
    version,
    OSType, OSName, OSVersion,  
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime,
    allowedCommands,
    operation ):

    """
    This function can be called to perform operations like 'backup, 'compare' and 'save'
    For 'save' operation, it
        Reads the environment spec file for the given subsystem
        For Command type of object, executes commands to gather environment info and saves in file name specified under saveDir
        For FileNames type of object, 
            if checksum is to be stored, it computes the checksum and stores it in filename <objectName>.checksum
            else, copies the contents of the file to saveDir/<objectName>

    For 'backup' operation, it
        Deletes any BackupYYYYMMDD directories that are older than specified retency period in param 'BackupRetencyDurationInDays'
        Derives the saveDir name in the form BackupYYYYMMDD using current time
        Performs all the tasks of 'save' operation with derived saveDir.

    for 'compare' operation, it
        Reads the environment spec file for the given subsystem
        For Command type of object, executes commands to gather environment info and saves in temp file
        For FileNames type of object, 
            if checksum is to be compared, it computes the checksum, reads the saved checksum from a saveDir/<objectName>.checksum 
                and compares the two checksums
            else, compares current file to the file saved in saveDir/<objectName>

    """
    returnStatus = True
    numberOfItems = 0

    errorMsg = ''

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAOperationSaveCompare() subsystem:{0}, AppConfig:{1}, version:{2}".format(
                subsystem, baseConfigFileName, version),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### dictionary to hold object definitions
    saveCompareParameters = defaultdict(dict)

    ### read the object spec file contents
    returnStatus, numberOfItems = JAOperationReadConfig( 
        baseConfigFileName, 
        subsystem, 
        version, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel,
        saveCompareParameters, allowedCommands )
    if returnStatus == False:
        ### fatal error, can't proceed.
        return returnStatus, numberOfItems

    if operation == 'backup':
        ### first delete older backup directories, older than 'BackupRetencyDurationInDays'
    
        backupRetencyDurationInDays = defaultParameters['BackupRetencyDurationInDays']

        if OSType == 'Windows':
            ### get list of files older than retency period
            filesToDelete = JAGlobalLib.JAFindModifiedFiles(
                    '{0}/Backup*'.format(defaultParameters['LocalRepositoryHome']), 
                    currentTime - (backupRetencyDurationInDays*3600*24), ### get files modified before this time
                    debugLevel, thisHostName)
            if len(filesToDelete) > 0:
                for fileName in filesToDelete:
                    try:
                        os.remove(fileName)
                        if debugLevel > 3:
                            print("DEBUG-4 JAOperationSaveCompare() Deleting the file:{0}".format(fileName))
                    except OSError as err:
                        JAGlobalLib.LogLine(
                            "ERROR JAOperationSaveCompare() Error deleting old backup file:{0}, errorMsg:{1}".format(fileName, err), 
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        
        else:
            # delete directories older than retency period
            command = 'find {0} -name "Backup*" -mtime +{1} -type d |xargs rm'.format(
                defaultParameters['LocalRepositoryHome'], backupRetencyDurationInDays)
            if debugLevel > 1:
                print("DEBUG-2 JAOperationSaveCompare() purging files with command:{0}".format(command))

            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(command, debugLevel, OSType)
            if returnResult == False:
                if re.match(r'File not found', errorMsg) != True:
                    JAGlobalLib.LogLine(
                        "INFO JAOperationSaveCompare() File not found, Error deleting old backup files:{0} ".format(returnOutput), 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        ### derive the saveDir using current time in the form BackupYYYYMMDD
        defaultParameters['SaveDir'] = saveDir = "{0}/Backup{1}".format( 
            defaultParameters['LocalRepositoryHome'],
            JAGlobalLib.UTCDateForFileName() )

    elif re.search(r'save|compare', operation) :
        saveDir = defaultParameters['SaveDir']

    if os.path.exists(saveDir) :
        if operation == "save":
            ### if saveDir present and it starts with 'Pre', skip save operation
            tempBaseFileName = os.path.basename(saveDir)
            if re.match(r'^Pre', tempBaseFileName):
                JAGlobalLib.LogLine(
                    "ERROR JAOperationSaveCompare() save directory:|{0}| starting with 'Pre' is already present, Skipped save operation".format(saveDir),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                return False, numberOfItems

    else:
        if operation == "save" or operation == 'backup':
            ### save directory not present, create it
            try:
                os.mkdir(saveDir)
            except OSError as err:
                JAGlobalLib.LogLine(
                    "ERROR JAOperationSaveCompare() Error creating {0} directory:{1}, error:{2}, Skipped {3} operation".format(
                        operation, saveDir, err, operation),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                return False, numberOfItems
        else:
            ### compare operation expects reference contents in saveDir.
            ###   fatal error, return
            JAGlobalLib.LogLine(
                "ERROR JAOperationSaveCompare() save directory:|{0}| not present, Skipped compare operation".format(saveDir),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            return False, numberOfItems

    if os.path.isdir(saveDir) == False:
        JAGlobalLib.LogLine(
            "ERROR JAOperationSaveCompare() Save directory:|{0}| passed is not a directory, Skipped {1} operation".format(saveDir, operation),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return False, numberOfItems

    ### this file is used as temporary storage for output of commands
    ### this temp file is deleted at the end of compare operation
    currentDataFileName ="{0}/JAAudit.dat.{1}".format(
        defaultParameters['LogFilePath'],
         os.getpid() )

    if defaultParameters['DownloadHostName'] == None:
        compareH2H = False
        compareCommandH2H = compareCommandH2HSedCommand = None
    else:
        compareH2H = True
        compareCommandH2H = defaultParameters['CompareCommandH2H']
        compareCommandH2HSedCommand = defaultParameters['CompareCommandH2HSedCommand']

    discoveredSpecFileName = "{0}/{1}{2}.{3}".format(
        saveDir, subsystem, baseConfigFileName, operation  )
    ### write the current AppConfig spec info to saveDir. 
    # This info will be used later while comparing the current environment to saved environment
    with open(discoveredSpecFileName, "w") as file:
        for objectName, attributes in saveCompareParameters.items():
            file.write("{0}:\n\tCommand: {1}\n\tFileNames: {2}\n\tCompareType:{3}\n\tSkipH2H: {4}\n\n".format(
                    objectName,
                    attributes['Command'],
                    attributes['FileNames'],
                    attributes['CompareType'],
                    attributes['SkipH2H']
                ))
        file.close()
    if operation == 'compare':
        discoveredSpecSaveFileName = "{0}/{1}{2}.save".format(
            saveDir, subsystem, baseConfigFileName  )
        ### compare two files as text files to find delta between the two
        returnStatus, fileDiffer, errorMsg = JAOperationCompareFiles(
            discoveredSpecFileName, discoveredSpecSaveFileName, 
            defaultParameters['BinaryFileTypes'],
            'text', # compareType
            defaultParameters['CompareCommand'],
            compareH2H, compareCommandH2H, compareCommandH2HSedCommand,
            '', ### file comparison, no additional info to print
            interactiveMode, debugLevel,
            myColors, colorIndex, outputFileHandle, HTMLBRTag,
            OSType)
        if returnStatus == True:
            if fileDiffer == True:
                JAGlobalLib.LogLine(
                    "\n\nWARN JAOperationSaveCompare() Discovered environment spec file:|{0}| and saved environment spec file:|{1}| differ\n\n".format(
                    discoveredSpecFileName, discoveredSpecSaveFileName ), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### initialize counters to track summary
    numberOfItems = numberOfErrors = 0
    numberOfCommandOutputSaved = numberOfChecksumsSaved = numberOfFilesSaved = 0
    numberOfChangedFiles = numberOfChangedCommandOutput = numberOfChangedChecksum = numberOfItemsSkipped = 0

    ### save or compare information of each object
    for objectName in saveCompareParameters:
        numberOfItems += 1
        objectAttributes = saveCompareParameters[objectName]

        ### while doing host to host compare, SKIP any object that has SkipH2H set to True
        if operation == 'compare' and compareH2H == True and objectAttributes['SkipH2H'] == True:
            if debugLevel > 0:
                JAGlobalLib.LogLine(
                    "DEBUG-1 JAOperationSaveCompare() Skipping objectName:|{0}|, Command:|{1}|, FileNames:|{2}|, CompareType:|{3}|, SkipH2H:|{4}|".format(
                    objectName,
                    objectAttributes['Command'],
                    objectAttributes['FileNames'],
                    objectAttributes['CompareType'],
                    objectAttributes['SkipH2H'] ), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            numberOfItemsSkipped += 1
            continue

        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-2 JAOperationSaveCompare() processing objectName:|{0}|, Command:|{1}|, FileNames:|{2}|, CompareType:|{3}|, SkipH2H:|{4}|".format(
                   objectName,
                   objectAttributes['Command'],
                   objectAttributes['FileNames'],
                   objectAttributes['CompareType'],
                   objectAttributes['SkipH2H'] ), 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        ### need to save the output of command with object name in save directory
        ### 'Command' takes precedence over FileNames if present
        if objectAttributes['Command'] != None:
            saveFileName = "{0}/{1}".format(saveDir,objectName) 

            if operation == 'compare':
                ### for compare operation, need to take current environment data in separate file and
                ###   compare it with saveFileName (data saved before)
                tempCommand = '{0} > {1}'.format( 
                    objectAttributes['Command'],
                    currentDataFileName)
            else:
                ### for save operation, save current data in saveFileName
                tempCommand = '{0} > {1}'.format( 
                    objectAttributes['Command'],
                    saveFileName)

            if debugLevel > 1:
                JAGlobalLib.LogLine(
                    "DEBUG-2 JAOperationSaveCompare() {0} object:|{1}| with command:|{2}|".format(
                        operation, saveFileName, tempCommand),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

            ### now execute the command to save the environment
            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                tempCommand, debugLevel, OSType)
            if returnResult == False:
                numberOfErrors += 1
                if re.match(r'File not found', errorMsg) != True:
                    JAGlobalLib.LogLine(
                        "ERROR JAOperationSaveCompare() File not found, error saving environment by executing command:|{0}|, error:|{1}|".format(
                                tempCommand, errorMsg), 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                else:
                    JAGlobalLib.LogLine(
                        "ERROR JAOperationSaveCompare() Error executing command:|{0}|, error:|{1}|".format(
                                tempCommand, errorMsg), 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                ### done processing current object
                continue
            else:
                numberOfCommandOutputSaved += 1
                ### if operation is compare, compare currentDataFileName content with saveFileName content
                if operation == 'compare':
                    returnStatus, fileDiffer, errorMsg = JAOperationCompareFiles(
                        currentDataFileName, saveFileName, 
                        defaultParameters['BinaryFileTypes'],
                        objectAttributes['CompareType'],
                        defaultParameters['CompareCommand'],
                        compareH2H, compareCommandH2H, compareCommandH2HSedCommand,
                        "{0}".format(objectAttributes['Command']), ### logAdditionalInfo - command used to get environment details
                        interactiveMode, debugLevel,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag,
                        OSType)

                    if fileDiffer == True:
                        numberOfChangedCommandOutput += 1

                ### done processing current object
                continue

        elif objectAttributes['FileNames'] != None:
            referenceFileName = objectAttributes['FileNames']
            if objectAttributes['CompareType'] == 'checksum':

                ### if CompareType is checksum, save checksum with .checksum as part of file name
                saveFileName = '{0}/{1}.checksum'.format( saveDir, objectName)

                ### compute MD5 checksum and compare 
                try:
                    ### compute checksum and store it in fileName ending with .checksum
                    with open(referenceFileName,"rb") as f:
                        md5_hash = hashlib.md5()
                        # Read and update hash in chunks of 8K
                        for byte_block in iter(lambda: f.read(32768),b""):
                            md5_hash.update(byte_block)
                        currentFileMD5Digest = md5_hash.hexdigest()
                        f.close()
                except OSError as err:
                    JAGlobalLib.LogLine(
                        "ERROR JAOperationSaveCompare() Not able to open reference file:|{0}|".format(referenceFileName), 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfErrors += 1
                    ### done processing current object
                    continue

                if operation == 'save' or operation == 'backup':
                    ### save current checksum computed in save file name
                    try:
                        with open(saveFileName,"w") as file:
                            file.write(currentFileMD5Digest)
                            file.close()
                            numberOfChecksumsSaved += 1
                    except OSError as err:
                        JAGlobalLib.LogLine(
                            "ERROR JAOperationSaveCompare() Not able to save checksum in the file:|{0}|".format(saveFileName), 
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        numberOfErrors += 1
                    ### done processing current object
                    continue
                else:
                    ### compare operation, compare current checksum with checksum stored before
                    try:
                        ### previous file has checksum stored, read it directly          
                        with open(saveFileName,"r") as f: 
                            previousFileMD5Digest = f.readline()
                            previousFileMD5Digest = previousFileMD5Digest.strip()
                            f.close()
                            numberOfChecksumsSaved += 1
                        if currentFileMD5Digest != previousFileMD5Digest:
                            if debugLevel > 0:
                                print("DEBUG-1 JAOperationSaveCompare() MD5 checksum differ, current file:|{0}|, saved file:|{1}|".format(
                                    referenceFileName,  saveFileName ))
                            fileDiffer = True
                            numberOfChangedChecksum += 1

                    except OSError as err:
                        JAGlobalLib.LogLine(
                                "ERROR JAOperationCompareFiles() Not able to open file:{0}".format(saveFileName), 
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                    ### done processing current object
                    continue
            else:
                ### if CompareType is not checksum, save reference file contents as is
                saveFileName = '{0}/{1}'.format( saveDir, objectName)

                ### copy the file to save directory
                if operation == 'save' or operation == 'backup':
                    try:
                        shutil.copy2(referenceFileName, saveFileName)
                        numberOfFilesSaved += 1

                    except OSError as err:
                        JAGlobalLib.LogLine(
                            "ERROR JAOperationSaveCompare() Not able to save reference file:|{0}| as save file:|{1}|, error:|{2}|".format(
                                referenceFileName, saveFileName, err), 
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        numberOfErrors += 1
                else:
                    numberOfFilesSaved += 1
                    ### compare two files 
                    ### compare reference file content with saveFileName content
                    returnStatus, fileDiffer, errorMsg = JAOperationCompareFiles(
                        referenceFileName, saveFileName, 
                        defaultParameters['BinaryFileTypes'],
                        objectAttributes['CompareType'],
                        defaultParameters['CompareCommand'],
                        compareH2H, compareCommandH2H, compareCommandH2HSedCommand,
                        '', ### file comparison, no additional info to print
                        interactiveMode, debugLevel,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag,
                        OSType)
                    if returnStatus == False:
                        numberOfErrors += 1
                    else:
                        if fileDiffer == True:
                            numberOfChangedFiles += 1
                            
    if operation == 'save' or operation == 'backup':
        JAGlobalLib.LogLine(
            "INFO JAOperationSaveCompare() total objects:{0}, Saved objects of commands:{1}, checksums:{2}, files:{3} with errors:{4}".format(
                numberOfItems, numberOfCommandOutputSaved, numberOfChecksumsSaved,numberOfFilesSaved,numberOfErrors), 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
    else:
        ### delete temporary file that was created during the compare operation 
        os.remove(currentDataFileName)
        JAGlobalLib.LogLine(
            "INFO JAOperationSaveCompare() total objects:{0}, Saved objects of commands:{1}, checksums:{2}, files:{3}, \
changed command outputs:{4}, changed checksums:{5}, changed files:{6}, skipped objects:{7}, with errors:{8}".format(
                numberOfItems, 
                numberOfCommandOutputSaved, numberOfChecksumsSaved, numberOfFilesSaved,
                numberOfChangedCommandOutput, numberOfChangedChecksum, numberOfChangedFiles, numberOfItemsSkipped,
                numberOfErrors), 
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    if re.search(r'upload', defaultParameters['operations']):
        ### upload will follow, prepare upload file list
        JAPrepareUploadFileList(
            baseConfigFileName, 
            subsystem, 
            OSType, 
            outputFileHandle, colorIndex, HTMLBRTag, myColors,
            interactiveMode,
            defaultParameters, saveCompareParameters,
            debugLevel )


    return returnStatus, numberOfItems
