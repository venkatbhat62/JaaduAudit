"""
This file contains the functions to handle heal and task operations
Author: havembha@gmail.com, 2022-12-29

Execution Flow
    Read spec yml file to buffer
    Extract heal or task specific parametrs from yml buffer
    Execute instructions
    If interactive mode, display results
    Else, store the results to a JAAudit.heal.YYYYMMDD or JAAudit.task.YYYYMMDD file
    If upload is enabled, add report file to upload file list
    Write history file

"""

import os
#import sys
import re
#import datetime
import time
#import subprocess
#import signal
from collections import defaultdict
import JAGlobalLib


def JAReadConfigHealTask( 
        operation,
        baseConfigFileName, 
        subsystem, 
        version, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        operationParameters, allowedCommands ):
        
    """
   Parameters passed:
        baseConfigFileName - Vaue of 'AppConfig' parameter defined in JAEnvironment.yml for that host or component for that environment
        subsystem - if not empty, it will be Prefixed to derive config file
        version - if not empty, suffixed to the baseConfigFileName to find release specific config file
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel, 
        operationSpec - full details, along with default parameters assigned, are returned in this dictionary

    Returned Values:
        returnStatus - True on success, False upon file read error
        numberOfItems - number of items read


    heal spec format: refer to WindowsAPP.Apps.heal.yml and LinuxAPP.Apps.heal.yml for details.
    task spec format: refer to WindowsAPP.Apps.task.yml and LinuxAPP.Apps.task.yml for details.
    """
    returnStatus = False
    errorMsg = ''
    numberOfItems = 0
    numberOfErrors = 0
    numberOfWarnings = 0
    numberOfSkipped = 0

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigHealTask() AppConfig:{0}, subsystem:{1}, version:{2} ".format(
                baseConfigFileName, subsystem, version),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    baseConfigFileNameParts = baseConfigFileName.split('.')
    if len(baseConfigFileNameParts) != 2:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigHealTask() AppConfig name not in expected format, no . (dot) in filename:|{0}|".format(baseConfigFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        return returnStatus, numberOfItems

    ### derive the  spec file, first check under LocalRepositoryCustom, next under LocalRepositoryCommon
    returnStatus, operationSpecFileName, errorMsg = JAGlobalLib.JADeriveConfigFileName( 
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCustom']),
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCommon']),
          baseConfigFileName, subsystem, operation, version, debugLevel )
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigHealTask() AppConfig:|{0}| not present, error:|{1}|".format(baseConfigFileName, errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, numberOfItems
        
    if debugLevel > 1:
        JAGlobalLib.LogLine(
            "DEBUG-2 JAReadConfigHealTask() Derived AppConfig file name using subsystem and version as part of file name:|{0}|".format(
                operationSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### Now read the yml file
    # use limited yaml reader when yaml is not available
    if yamlModulePresent == True:
        try:
            import yaml
            with open(operationSpecFileName, "r") as file:
                operationSpec = yaml.load(file, Loader=yaml.FullLoader)
                file.close()
        except OSError as err:
            JAGlobalLib.LogLine(
                "ERROR JAReadConfigHealTask() AppConfig:|{0}| not present, error:|{1}|".format(
                    operationSpecFileName, errorMsg),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    else:
        operationSpec = JAGlobalLib.JAYamlLoad(operationSpecFileName)

    errorMsg = ''

    ### temporary attributes to process the YML file contents with default values
    variables = defaultdict(dict)
    returnStatus, errorMsg = JAGlobalLib.JASetSystemVariables( defaultParameters, thisHostName, variables)
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "{0}".format(errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    saveParameter = False  
    overridePrevValue = False

    if operation == 'heal':
        environmentLevelParams = [ 'Alert', 'AppStatusFile', 'Enabled', 'HealAfterInSec', 'HealIntervalInSec', 'MaxAttempts' ]
    elif operation == 'task':
        environmentLevelParams = [ 'Alert', 'Enabled']

    for key, value in operationSpec.items():
             
        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-2 JAReadConfigHealTask() processing item:|{0}|, value:{1}".format(key, value),
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
            returnStatus, tempWarnings, tempErrors = JAGlobalLib.JAParseVariables(
                    key, value['Variable'], overridePrevValue, variables,
                    defaultParameters, allowedCommands, 
                    interactiveMode, debugLevel,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType )
            if returnStatus == True:
                numberOfErrors += tempErrors
                numberOfWarnings += tempWarnings

        ### read default values applicable to all items in a matching environment
        for environmentParams in environmentLevelParams:
            tempValue = value.get(environmentParams)
            if tempValue != None:
                defaultParameters[environmentParams] = tempValue

        if value.get('Items') != None:
            ### expect variable definition to be in dict form
            for itemName, itemParams in value['Items'].items():
                numberOfItems += 1 
                """ service params can have below attributes 
                    operationAttributes = [
                        'Alert'
                        'AppStatusFile'
                        'Command',
                        'ComparePatterns'
                        'Condition',
                        'Enabled'
                        'HealAction',
                        'HealAfterInSec'
                        'HealIntervalInSec'
                        'MaxAttempts'
                        'Task'
                        ]
                """
                if overridePrevValue == False:
                    if itemName in operationParameters:
                        if 'HostNames' in operationParameters[itemName]:
                            ### value present for this service already, SKIP current definition
                            ###  this is valid, DO NOT warn for this condition
                            ### spec may be present under individual environment and later in All section
                            continue
                
                if operation == 'heal':
                    ### command and condition both are mandatory for heal operation
                    if 'Command' not in itemParams or 'Condition' not in itemParams:
                        JAGlobalLib.LogLine(
                            "WARN JAReadConfigHealTask() {0} item:{1}, 'Command' and 'Condition' both are mandatory, Skipped this definition".format(
                                operation, itemName ),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        numberOfWarnings += 1
                        continue

                    if 'HealAction' not in itemParams:
                        JAGlobalLib.LogLine(
                            "WARN JAReadConfigHealTask() {0} item:{1}, 'HealAction', Skipped this definition".format(
                                operation, itemName ),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        numberOfWarnings += 1
                        continue

                    if 'Enabled' in itemParams:
                        if itemParams['Enabled'] == 'No' or itemParams['Enabled'] == 'no':
                            if debugLevel > 1:
                                JAGlobalLib.LogLine(
                                    "DEBUG-2 JAReadConfigHealTask() {0} item:{1}, not enabled, Skipped this definition".format(
                                        operation, itemName ),
                                    interactiveMode,
                                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                            numberOfSkipped += 1
                            continue

                ### use default values if current item does not have that param defined
                skipThisItem = False
                for environmentParams in environmentLevelParams:
                    if environmentParams not in itemParams:
                        if environmentParams in defaultParameters:
                            itemParams[environmentParams] = defaultParameters[environmentParams] 
                        else:
                            JAGlobalLib.LogLine(
                                "WARN JAReadConfigHealTask() {0} item:|{1}|, {2} is not defined in heal spec as well as in Environment yml file, skipped this item".format(
                                    operation, itemName ),
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                            skipThisItem = True
                            numberOfWarnings += 1
                            break
                if skipThisItem == True:
                    continue

                for attribute in itemParams:
                    attributeValue = itemParams[attribute]
                    
                    if attribute == 'Alert':
                        originalAttributeValue = attributeValue
                        returnStatus, attributeValue = JAGlobalLib.JASubstituteVariableValues( variables, attributeValue)
                        if returnStatus == True:
                            if debugLevel > 2:
                                JAGlobalLib.LogLine(
                                    "DEBUG-3 JAReadConfigHealTask() {0} item:|{1}|, original HostNames:|{2}|, HostNames after substituting the variable values:|{3}|".format(
                                        operation, itemName, originalAttributeValue, attributeValue),
                                    interactiveMode,
                                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    elif attribute == 'ComparePatterns':
                        ### evaluate group values using current variable values if group values have any variable spec
                        returnStatus = JAGlobalLib.JAEvaluateComparePatternGroupValues(
                                    itemName, attributeValue, variables,
                                    interactiveMode, debugLevel,
                                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType )

                    operationParameters[itemName][attribute] = attributeValue

                if 'ComparePatterns' not in operationParameters[itemName]:
                    operationParameters[itemName]['ComparePatterns'] = None

                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JAReadConfigHealTask() {0} item:{1}, attributes:{2}".format(
                            operation, itemName, operationParameters[itemName]),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                
    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigHealTask() Read {0} items with {1} warnings, {2} skipped, {3} errors from AppConfig:{4}".format(
                numberOfItems, numberOfWarnings, numberOfSkipped, numberOfErrors, operationSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return returnStatus, numberOfItems

def JAOperationHeal(
    itemName, serviceAttributes, baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion,   
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime, allowedCommands, operation,
    healProfileFileName ):
    """
    This function carries out heal operation. This is called after confirming that the condition is met.
    It checks the application state in AppStatusFile if present
     if application is in Running state, or the AppStatusFile is not present, need to apply the heal rules.
     Records the time at which condition was first detected. this will be used to compute the time elapsed since 
     first detection of the condition.
     If elapsed time since first detection is greater than HealAfterInSec, and number of times the heal action
       taken is lower than MaxAttempts, and HealIntervalInSec not elapsed, proceeds with HealAction
     If Enabled is dryrun, logs the event
        Enabled is Yes or yes, executes the heal action.
     If ComparePatterns is present, compares the returned response to desired/expected response spec

    Returns True - if all actions are successful
            False upon any error

    """
    returnStatus = True
    actionTaken = False
    currentTime = time.time()

    if 'AppStatusFile' in serviceAttributes:
        try:
            with open( serviceAttributes['AppStatusFile'], 'r') as file:
                appStatus = file.readline()
                file.close()
                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JAOperationHealTask() item:|{0}|, item attributes:|{1}|, appStatus:{2}".format(
                        itemName, serviceAttributes, appStatus),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                if appStatus == 'Stopped':
                    JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'FirstDetectedTime', 0 )
                    return returnStatus, actionTaken
        except OSError as err:
            errorMsg = "ERROR JAReadConfigHealTask() item: {0}, Can not open appStatusFile:|{1}|, OS error:|{2}|\n".format(
                itemName, serviceAttributes['AppStatusFile'], err)
            JAGlobalLib.LogLine(
                errorMsg,
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    returnStatus, firstDetectedTime = JAGlobalLib.JAGetProfile( healProfileFileName, itemName + 'FirstDetectedTime')
    if returnStatus == False:
        firstDetectedTime = 0
    else:
        firstDetectedTime = float(firstDetectedTime)
    if  firstDetectedTime == 0:
        ### no previous condition detected time, set current time as first detected time
        JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'FirstDetectedTime', currentTime )
        JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'FirstHealActionTime', 0 )
        JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'HealAttempts', 0 )
    else:
        elapsedTimeSinceFirstDetection = currentTime - firstDetectedTime
        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-2 JAOperationHealTask() item:|{0}|, item attributes:|{1}|, HealAfterInSec:{2}, elapsedTimeSinceFirstDetection:{3}".format(
                itemName, serviceAttributes, serviceAttributes['HealAfterInSec'], elapsedTimeSinceFirstDetection ),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        
        if elapsedTimeSinceFirstDetection < serviceAttributes['HealAfterInSec']:
            return returnStatus, actionTaken

    ### condition was detected before, and elapsed time is greater than or equal to HealAfterInSec
    returnStatus, numberOfHealAttempts = JAGlobalLib.JAGetProfile( healProfileFileName, itemName + 'HealAttempts')
    if returnStatus == False:
        numberOfHealAttempts = 0    
    else:
        numberOfHealAttempts = int(numberOfHealAttempts)

    sendAlert = takeAction = False
    if serviceAttributes['Enabled'] == 'dryrun' :
        alertHeading = "INFO "
    else:
        alertHeading = "ERROR"

    ###  check whether heal interval passed already
    returnStatus, firstHealActionTime = JAGlobalLib.JAGetProfile( healProfileFileName, itemName + 'FirstHealActionTime')
    if returnStatus == False:
        firstHealActionTime = currentTime
        takeAction = True
    else:
        firstHealActionTime = float(firstHealActionTime)
        if firstHealActionTime == 0:
            firstHealActionTime = currentTime
            takeAction = True   
    
    if ( currentTime - firstHealActionTime) > serviceAttributes['HealIntervalInSec']:
        if numberOfHealAttempts >= serviceAttributes['MaxAttempts']:
            errorMsg = "{0} JAAudit - {1} - heal condition still exists after {2} attempts within heal interval:{3} sec".format(
                    alertHeading, itemName, numberOfHealAttempts, serviceAttributes['HealIntervalInSec']  )
            sendAlert = True
        else:
            takeAction = True    
    elif numberOfHealAttempts >= serviceAttributes['MaxAttempts']:
        errorMsg = "{0} JAAudit - {1} - heal condition still exists after {2} attempts within heal interval:{3} sec".format(
                alertHeading, itemName, numberOfHealAttempts, (currentTime - firstHealActionTime)  )
        sendAlert = True
    else:
        takeAction = True 

    if sendAlert == True:
        if serviceAttributes['Alert'] != None:
            JAGlobalLib.LogLine(
                errorMsg,
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            if 'CommandMail' in defaultParameters:
                mailCommand = "echo '{0}' | {1} -s 'JAAudit heal alert for item {2}' {3}".format(
                    errorMsg,
                    defaultParameters['CommandMail'],
                    itemName, 
                    serviceAttributes['Alert']   )
                returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                    defaultParameters['CommandShell'], mailCommand, debugLevel, OSType)
                if returnResult == False:
                    if re.match(r'File not found', errorMsg) != True:
                        JAGlobalLib.LogLine(
                            "ERROR JAOperationHealTask() item:{0}, error performing operation:{1}, errorMsg:|{2}|".format(
                                itemName, operation, errorMsg), 
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                else:
                    if debugLevel > 1:
                        JAGlobalLib.LogLine(
                            "DEBUG-2 JAOperationHealTask() Sent mail using the command:|{0}|".format(mailCommand),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            else:
                JAGlobalLib.LogLine(
                    "ERROR JAOperationHealTask() Can't send email, 'CommandMail' is not set in environment yml file",
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'FirstDetectedTime', 0 )
        JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'FirstHealActionTime', 0 )
        JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'HealAttempts', 0 )

    if takeAction == True:
        numberOfHealAttempts += 1
        if serviceAttributes['Enabled'] == 'dryrun':
            JAGlobalLib.LogLine(
                "INFO JAOperationHealTask() heal {0} dryrun healAction:|{1} {2}|, attempts:{3}, healIntervalElapsed:{4} sec".format( 
                    itemName, defaultParameters['CommandShell'], serviceAttributes['HealAction'],
                    numberOfHealAttempts,  (currentTime - firstHealActionTime) ),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            actionTaken = True
        else:
            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                defaultParameters['CommandShell'], serviceAttributes['HealAction'], debugLevel, OSType)
            if returnResult == False:
                if re.match(r'File not found', errorMsg) != True:
                    JAGlobalLib.LogLine(
                        "ERROR JAOperationHealTask() item:{0}, error performing operation:{1}, errorMsg:|{2}|".format(
                            itemName, operation, errorMsg), 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                returnStatus = False
            else:
                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JAOperationHealTask() heal {0} executed healAction:|{1} {2}|, attempts:{3}, healIntervalElapsed:{4} sec".format( 
                            itemName, defaultParameters['CommandShell'], serviceAttributes['HealAction'],
                            numberOfHealAttempts,  (currentTime - firstHealActionTime) ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            
                actionTaken = True
        JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'FirstHealActionTime', firstHealActionTime )
        JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'HealAttempts', numberOfHealAttempts )

    return returnStatus, actionTaken

def JAOperationTask(
    serviceAttributes, baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion,   
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime, allowedCommands, operation ):

    returnStatus = True
    actionTaken = False

    return returnStatus, actionTaken

def JAOperationHealTask(
        baseConfigFileName, subsystem, myPlatform, appVersion,
                OSType, OSName, OSVersion,   
                outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, operations, thisHostName, yamlModulePresent,
                defaultParameters, debugLevel, currentTime, allowedCommands, operation ):

    """"
    This function handles operations - heal and task

    First reads the spec file, and calls 
        JAOperationHeal to carry out heal actions.
        JAOperationTask to carry out task actions.

    """
    returnStatus = True
    errorMsg = ''

    ### derive connectivity spec file using subsystem and application version info
        
    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAOperationHealTask() Connectivity spec:{0}, subsystem:{1}, appVersion:{2}, interactiveMode:{3}".format(
            baseConfigFileName, subsystem, appVersion, interactiveMode),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
    
    ### dictionary to hold object definitions
    operationParameters = defaultdict(dict)

    ### read the object spec file contents
    returnStatus, numberOfItems = JAReadConfigHealTask( 
        operation,
        baseConfigFileName, 
        subsystem, 
        appVersion, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        operationParameters, allowedCommands )
    if returnStatus == False:
        ### fatal error, can't proceed.
        return returnStatus, numberOfItems

    ### initialize counters to track summary
    ### numberOfErrors - when connectivity fails to all hosts
    ### numberOfFailures - when at least one connection fails to HostNames, 
    ###       typically set when there are more than one host in HostNames
    ### numberOfConditionsMet - connectivity test performed after conditions met
    ### numberOfConditionsNotMet - connectivity test NOT performed since condition was not met
    numberOfItems = numberOfErrors = numberOfFailures  = numberOfConditionsMet = numberOfConditionsNotMet = numberOfPasses = 0
    
    healProfileFileName = "{0}/JAAudit.heal.profile".format( defaultParameters['ReportsPath'] )

    reportFileNameWithoutPath = "JAAudit.{0}.{1}".format( operation, JAGlobalLib.UTCDateForFileName() )
    reportFileName = "{0}/{1}".format( defaultParameters['ReportsPath'], reportFileNameWithoutPath )
    with open( reportFileName, "w") as reportFile:

        ### write report header
        reportFile.write("\
TimeStamp: {0}\n\
Platform: {1}\n\
HostName: {2}\n\
Environment: {3}\n\
Items:\n\
".format(JAGlobalLib.UTCDateTime(), defaultParameters['Platform'], thisHostName, defaultParameters['Environment']) )

        ### save or compare information of each object
        for itemName in operationParameters:
            numberOfItems += 1
            serviceAttributes = operationParameters[itemName]

            if debugLevel > 2:
                JAGlobalLib.LogLine(
                    "DEBUG-3 JAOperationHealTask() Processing item:|{0}|, item attributes:|{1}|".format(
                    itemName, serviceAttributes),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

            conditionPresent, conditionMet = JAGlobalLib.JAEvaluateCondition(
                                itemName, serviceAttributes, defaultParameters, debugLevel,
                                interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)

            if conditionPresent == True:
                if conditionMet == False:
                    if debugLevel > 1:
                        JAGlobalLib.LogLine(
                            "DEBUG-2 JAOperationHealTask() condition not met for item:|{0}|, item attributes:|{1}|, skipping this item".format(
                            itemName, serviceAttributes),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                    numberOfConditionsNotMet += 1
                    if operation == 'heal':
                        ### log result, align the spaces so that yaml layout format is satisfied.
                        ### leading space in write content is intentional, to align the data per yml format.
                        reportFile.write("\
    {0}:\n\
        Alert: {1}\n\
        AppStatusFile: {2}\n\
        Command: {3}\n\
        ComparePatterns: {4}\n\
        Condition: {5}\n\
        Enabled: {6}\n\
        HealAction: {7}\n\
        HealAfterInSec: {8}\n\
        HealIntervalInSec: {9}\n\
        MaxAttempts: {10}\n\
        Results:\n\
            Skipped, condition not met\n".format(
            itemName,
            serviceAttributes['Alert'],
            serviceAttributes['AppStatusFile'],
            serviceAttributes['Command'],
            serviceAttributes['Condition'],
            serviceAttributes['ComparePatterns'],
            serviceAttributes['Enabled'],
            serviceAttributes['HealAction'],
            serviceAttributes['HealAfterInSec'],
            serviceAttributes['HealIntervalInSec'],
            serviceAttributes['MaxAttempts'],
        ))
                    else:
                        reportFile.write("\
    {0}:\n\
        Alert: {1}\n\
        Command: {2}\n\
        Condition: {3}\n\
        Task: {4}\n\
        Periodicity: {5}\n\
        Results:\n\
            Skipped, condition not met\n".format(
            itemName,
            serviceAttributes['Alert'],
            serviceAttributes['Command'],
            serviceAttributes['Condition'],
            serviceAttributes['Task'],
            serviceAttributes['Periodicity'] ))

                    if operation == 'heal':
                            ### if the condition was met before, remove the first detected time in heal tracking data file
                        returnStatus = JAGlobalLib.JASetProfile( healProfileFileName, itemName + 'FirstDetectedTime', 0 )
                        numberOfConditionsMet += 1
                        if debugLevel > 1:
                            JAGlobalLib.LogLine(
                                "DEBUG-2 JAOperationHealTask() condition not met for item:|{0}|, item attributes:|{1}|, skipping this item".format(
                                itemName, serviceAttributes),
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    continue

            if operation == 'heal':
                returnStatus, actionTaken = JAOperationHeal(
                    itemName, serviceAttributes, baseConfigFileName, subsystem, myPlatform, appVersion,
                    OSType, OSName, OSVersion,   
                    outputFileHandle, colorIndex, HTMLBRTag, myColors,
                    interactiveMode, operations, thisHostName, yamlModulePresent,
                    defaultParameters, debugLevel, currentTime, allowedCommands, operation,
                    healProfileFileName )

            else:
                returnStatus, actionTaken = JAOperationTask(
                    itemName, serviceAttributes, baseConfigFileName, subsystem, myPlatform, appVersion,
                    OSType, OSName, OSVersion,   
                    outputFileHandle, colorIndex, HTMLBRTag, myColors,
                    interactiveMode, operations, thisHostName, yamlModulePresent,
                    defaultParameters, debugLevel, currentTime, allowedCommands, operation )

            if returnStatus == True:
                if actionTaken == True:
                    numberOfPasses += 1
            else:
                numberOfFailures += 1

        JAGlobalLib.LogLine(
            "INFO JAOperationHealTask() Total items:{0}, conditions met:{1}, conditions NOT met:{2}, \
    all passed:{3}, failed:{4}, errors:{5}".format(
            numberOfItems, numberOfConditionsMet, numberOfConditionsNotMet, numberOfPasses, numberOfFailures, numberOfErrors ),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        ### write the summary and close the report file
        reportFile.write("\
Summary:\n\
    Total: {0}\n\
    ConditionsMet: {1}\n\
    ConditionsNotMet: {2}\n\
    Pass: {3}\n\
    Fail: {4}\n\
    Error: {5}\n\
".format( numberOfItems, numberOfConditionsMet, numberOfConditionsNotMet, numberOfPasses, numberOfFailures, numberOfErrors ) )



        reportFile.close()

        ### add current report file to upload list if upload is opted
        if re.search(r'upload', defaultParameters['Operations']):
            defaultParameters['ReportFileNames'].append(reportFileNameWithoutPath)
    
    ### write history file
    JAGlobalLib.JAUpdateHistoryFileName(subsystem, operation, defaultParameters )

    return returnStatus, errorMsg