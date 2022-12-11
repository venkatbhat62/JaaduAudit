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

def JAReadConfigConn( 
        baseConfigFileName, 
        subsystem, 
        version, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        connParameters, allowedCommands ):
        
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


    Connectivity spec format: refer to WindowsAPP.Apps.conn.yml and LinuxAPP.Apps.conn.yml for details.

    """
    returnStatus = False
    errorMsg = ''
    numberOfItems = 0
    numberOfErrors = 0
    numberOfWarnings = 0

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigConn() AppConfig:{0}, subsystem:{1}, version:{2} ".format(
                baseConfigFileName, subsystem, version),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### parameter names supported in SaveCompare object definition file
    connAttributes = [
        'Command',
        'Condition'
        'HostNames',
        'Ports',
        'Protocol'
        ]
    baseConfigFileNameParts = baseConfigFileName.split('.')
    if len(baseConfigFileNameParts) != 2:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigConn() AppConfig name not in expected format, no . (dot) in filename:|{0}|".format(baseConfigFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        return returnStatus, numberOfItems

    ### derive the save compare spec file, first check under LocalRepositoryCustom, next under LocalRepositoryCommon
    returnStatus, connSpecFileName, errorMsg = JAGlobalLib.JADeriveConfigFileName( 
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCustom']),
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCommon']),
          baseConfigFileName, subsystem, 'conn', version, debugLevel )
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigConn() AppConfig:|{0}| not present, error:|{1}|".format(baseConfigFileName, errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, numberOfItems
        
    if debugLevel > 1:
        JAGlobalLib.LogLine(
            "DEBUG-2 JAReadConfigConn() Derived AppConfig file name using subsystem and version as part of file name:|{0}|".format(connSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### Now read the yml file
    # use limited yaml reader when yaml is not available
    if yamlModulePresent == True:
        try:
            import yaml
            with open(connSpecFileName, "r") as file:
                connSpec = yaml.load(file, Loader=yaml.FullLoader)
                file.close()
        except OSError as err:
            errorMsg = "ERROR JAReadConfigConn() Can not open configFile:|{0}|, OS error:|{1}|\n".format(
                connSpecFileName, err)
            JAGlobalLib.LogLine(
                "ERROR JAReadConfigConn() AppConfig:|{0}| not present, error:|{1}|".format(connSpecFileName, errorMsg),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    else:
        connSpec = JAGlobalLib.JAYamlLoad(connSpecFileName)

    errorMsg = ''

    ### temporary attributes to process the YML file contents with default values
    tempAttributes = defaultdict(dict)
    variables = defaultdict(dict)

    integerParameters = []
    floatParameters = []

    saveParameter = False  
    overridePrevValue = False

    for key, value in connSpec.items():
             
        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-2 JAReadConfigConn() processing key:|{0}|, value:{1}".format(key, value),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        if key == 'All' or key == 'ALL':
            saveParameter = True
            overridePrevValue = False

        elif value.get('HostName') != None:
            # match current hostname to hostname specified within each environment to find out
            #   which environment spec is to be applied for the current host
            if re.match(value['HostName'], thisHostName):
                saveParameter = True
                overridePrevValue = True
            else:
                overridePrevValue = saveParameter = False

        if saveParameter == False:
            continue

        if value.get('Variable') != None:
            ### expect variable definition to be in dict form
            for variableName, command in value['Variable'].items():

                ### check for valid commands
                if JAGlobalLib.JAIsSupportedCommand( command, allowedCommands, OSType):

                    if OSType == "Windows":
                        tempCommandToComputeVariableValue = '{0} {1}'.format(
                            defaultParameters['CommandPowershell'], command) 
                    else:
                        tempCommandToComputeVariableValue =  command
                    tempCommandToComputeVariableValue = os.path.expandvars( tempCommandToComputeVariableValue ) 

                    returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                                                        tempCommandToComputeVariableValue, debugLevel, OSType)
                    if returnResult == True:
                        variableValue = returnOutput.rstrip("\n")
                        variableValue = variableValue.lstrip()
                        if OSType == 'Windows':
                            ### output of the form "['<value>\r, '']"
                            lineParts = re.findall(r"^\['(.+)(\\)", variableValue)
                            if len(lineParts) > 0:
                                variableValue = lineParts[0][0]
                    else:
                        JAGlobalLib.LogLine(
                            "ERROR JAReadConfigConn() Not able to compute variable value for variable name:{0}, command:{1}, error:{2}".format(
                                variableName, command, errorMsg),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                        variableValue = 'Error'

                    if overridePrevValue == True:
                        ### even if prev value present, override it to use current environment spec
                        variables[variableName] = variableValue
                    else:                
                        if variables[variableName] == None:
                            ### value not defined yet, assign it
                            variables[variableName] = variableValue

                    if debugLevel > 1:
                        JAGlobalLib.LogLine(
                            "DEBUG-2 JAReadConfigConn() variable name:{0}, command:{1}, value:{2}".format(
                                variableName, command, value),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                else:
                    ### not a valid command, log WARNing
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigConn() Unsupported command, variable name:{0}, command:{1}".format(
                            variableName, command),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1

        if value.get('Services') != None:
            ### expect variable definition to be in dict form
            for serviceName, serviceParams in value['Services'].items():
                numberOfItems += 1 
                """ service params can have below attributes 
                    connAttributes = [
                        'Command',
                        'Condition'
                        'HostNames',
                        'Ports',
                        'Protocol'
                        ]
                """
                if overridePrevValue == False:
                    if serviceName in connParameters:
                        if 'HostNames' in connParameters[serviceName]:
                            ### value present for this service already, SKIP current definition
                            continue

                for attribute in serviceParams:
                    attributeValue = serviceParams[attribute]
                    
                    if attribute == 'HostNames':
                        ### replace any variable name with variable value
                        variableNames = re.findall(r'\{\{ (\w+) \}\}', attributeValue)
                        if len(variableNames) > 0:
                            ### replace each variable name with variable value
                            for variableName in variableNames:
                                if variables[variableName] != None:
                                    replaceString = r'\$\{\{ {0} \}\}'.format( variableName)
                                    attributeValue = attributeValue.replace(replaceString, variables[variableName])
                    connParameters[serviceName][attribute] = attributeValue

                if 'Protocol' not in serviceParams:
                    ### set default protocol
                    connParameters[serviceName]['Protocol'] = 'TCP'
                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JAReadConfigConn() Service name:{0}, attributes:{1}".format(
                            serviceName, connParameters[serviceName]),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                
        else:
            JAGlobalLib.LogLine(
                "ERROR JAReadConfigConn() Unsupported key:{0}, value:{1}, skipped this object".format(
                    key, value),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            numberOfErrors += 1

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigConn() Read {0} items with {1} warnings, {2} errors from AppConfig:{3}".format(
                numberOfItems, numberOfWarnings, numberOfErrors, connSpecFileName),
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
    returnStatus, numberOfItems = JAReadConfigConn( 
        baseConfigFileName, 
        subsystem, 
        appVersion, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        connParameters, allowedCommands )
    if returnStatus == False:
        ### fatal error, can't proceed.
        return returnStatus, numberOfItems

    return returnStatus, errorMsg