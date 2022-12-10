"""
This file contains the functions to handle connectivity check
Author: havembha@gmail.com, 2022-11-06

Execution Flow
    Read connectivity spec yml file to buffer
    Extract connectivity check specific parametrs from yml buffer
    Run connectivity check
    If interactive mode, display results
    Else, store the results to a JAAudit.conn.log.YYYYMMDD file
    If upload is enabled, add report file to upload file list
    Add OperationConn=<current time in seconds> to Audit.profile

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
   Parameters passed:
        baseConfigFileName - Vaue of 'AppConfig' parameter defined in JAEnvironment.yml for that host or component for that environment
        subsystem - if not empty, it will be Prefixed to derive config file
        version - if not empty, suffixed to the baseConfigFileName to find release specific config file
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel, 
        connSpec - full details, along with default parameters assigned, are returned in this dictionary

    Returned Values:
        returnStatus - True on success, False upon file read error
        numberOfItems - number of items read


    Connectivity spec format:
#   Command: run command to gather currnet state of the process like "ps -ef|grep <processName>" in Linux or
#             get-process -name <processName> in windows
#             to check whether a process is running before doing connection check to listen port on local host
#           Optional parameters, default None
#   Condition: <number> - if above command results in a number greater than or equal to the given <number>
#         connectivity check will be performed, else it will be skipped.
#           Optional parameters, default None
#   Environment: perform this check for the desired environment only
#           Optional parameters, default - match to all enviormnet
#   HostNames: destination hostname in short form or in FQDN form, can be IP address also. Can be single or in CSV format
#         destination hostname can be localhost, in which case the connectivity to local port is verified. 
#         This is be useful to check the local process listening in on expected LISTEN port
#         If more then one hostname is specified via CSV, connectivity check is performed for to all those hosts
#           for each of the ports specified under Ports.
#           Mandatory Parameter
#   Ports: single port or ports in CSV format, or port range like startingPort-(dash)-endingPort
#          if more than one port is specified or range is specified, connectivity is checked to all those ports
#            from current host to destination host
#           Mandatory Parameter
#   Protocol: TCP|UDP
#         If UDP, it will send UDP packets, so that one can check the receipt of packets on other end manually or using other tools
#           UDP does not provide any conclusive test results
#         Optional parameter, defaults to TCP
#

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
    connAttributes = [
        'Command',
        'Condition'
        'Environment',
        'Hostnames',
        'Ports',
        'Protocol'
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
          baseConfigFileName, subsystem, 'compare', version, debugLevel )
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
            if paramName not in connAttributes:
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


def JAOperationConn(
    baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion,   
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime, allowedCommands, operation ):

    returnStatus = True
    errorMsg = ''

    ### derive connectivity spec file using subsystem and application version info
        
    if debugLevel > 0:
        print("DEBUG-1 JAOperationConn() Connectivity spec:{0}, subsystem:{1}, appVersion:{2}, interactiveMode:{3}".format(
            baseConfigFileName, subsystem, appVersion, interactiveMode))
    time.sleep(1)

    ### dictionary to hold object definitions
    connParameters = defaultdict(dict)

    ### read the object spec file contents
    returnStatus, numberOfItems = JAOperationReadConfig( 
        baseConfigFileName, 
        subsystem, 
        appVersion, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel,
        connParameters, allowedCommands )
    if returnStatus == False:
        ### fatal error, can't proceed.
        return returnStatus, numberOfItems

    return returnStatus, errorMsg