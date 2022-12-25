"""
This file contains the functions to cert, health, inventory, license and test operations
Author: havembha@gmail.com, 2022-12-16
error
Execution Flow
    Read certificate, health, inventory, license or test spec yml file to buffer
    Extract operation specific parametrs from yml buffer
    For cert operation,
        Decode cert, check validity dates
        Compare patterns if opted to declear success or error
    For license,
        Execute commands to get license info.
        Compare patterns if opted to declear success or error
    For inventory,
        Execute commands to get inventory info
    For inventory,
        Execute commands to get health info
    For test,
        Execute commands, save the results to temp file
        Apply IgnorePatterns to mask patters/text in result that is to be ignored before comparison
        If ComparePatterns is specified, search for those in result.
        Else, compare the result file to the expected result file, whose file name is same as item name.

    If interactive mode, display results
    Else, store the results to a JAAudit.<operation>.log.YYYYMMDD file
    If upload is enabled, add report file to upload file list
    Create JAAudit.<operation>.history file

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

import hashlib
import shutil

def JAReadConfigCHILT(
        operation, 
        baseConfigFileName, 
        subsystem, 
        version, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        CHILTParameters, allowedCommands,
        mandatoryAttribute ):
        
    """
   Parameters passed:
        operation - like cert, license, inventory, health, test
        baseConfigFileName - Vaue of 'AppConfig' parameter defined in JAEnvironment.yml for that host or component for that environment
        subsystem - if not empty, it will be Prefixed to derive config file
        version - if not empty, suffixed to the baseConfigFileName to find release specific config file
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel, 
        CHILTSpec - full details, along with default parameters assigned, are returned in this dictionary
        allowedCommands - commands allowed to be executed
        mandatoryAttribute - mandatory attribute based on operation type. each item needs to have this

    Returned Values:
        returnStatus - True on success, False upon file read error
        numberOfItems - number of items read


    Cert, Inventory, Licensem Health spec format: refer to below files for details
        WindowsAPP.Apps.cert.yml and LinuxAPP.Apps.cert.yml 
        WindowsAPP.Apps.inventory.yml and LinuxAPP.Apps.inventory.yml
        WindowsAPP.Apps.license.yml and LinuxAPP.Apps.license.yml
        WindowsAPP.Apps.health.yml and LinuxAPP.Apps.health.yml

    """
    returnStatus = False
    errorMsg = ''
    numberOfItems = 0
    numberOfErrors = 0
    numberOfWarnings = 0

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigCHILT() AppConfig:{0}, subsystem:{1}, version:{2} ".format(
                baseConfigFileName, subsystem, version),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    baseConfigFileNameParts = baseConfigFileName.split('.')
    if len(baseConfigFileNameParts) != 2:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigCHILT() AppConfig name not in expected format, no . (dot) in filename:|{0}|".format(baseConfigFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        return returnStatus, numberOfItems

    ### derive the save compare spec file, first check under LocalRepositoryCustom, next under LocalRepositoryCommon
    returnStatus, CHILTSpecFileName, errorMsg = JAGlobalLib.JADeriveConfigFileName( 
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCustom']),
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCommon']),
          baseConfigFileName, subsystem, operation, version, debugLevel )
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigCHILT() AppConfig:|{0}| not present, error:|{1}|".format(baseConfigFileName, errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, numberOfItems
        
    if debugLevel > 1:
        JAGlobalLib.LogLine(
            "DEBUG-2 JAReadConfigCHILT() Derived AppConfig file name using subsystem and version as part of file name:|{0}|".format(CHILTSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### Now read the yml file
    # use limited yaml reader when yaml is not available
    if yamlModulePresent == True:
        try:
            import yaml
            with open(CHILTSpecFileName, "r") as file:
                CHILTSpec = yaml.load(file, Loader=yaml.FullLoader)
                file.close()
        except OSError as err:
            errorMsg = "ERROR JAReadConfigCHILT() Can not open configFile:|{0}|, OS error:|{1}|\n".format(
                CHILTSpecFileName, err)
            JAGlobalLib.LogLine(
                "ERROR JAReadConfigCHILT() AppConfig:|{0}| not present, error:|{1}|".format(CHILTSpecFileName, errorMsg),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    else:
        CHILTSpec = JAGlobalLib.JAYamlLoad(CHILTSpecFileName)

    errorMsg = ''

    saveParameter = False  
    overridePrevValue = False

    ### temporary attributes to process the YML file contents with default values
    variables = defaultdict(dict)
    returnStatus, errorMsg = JAGlobalLib.JASetSystemVariables( defaultParameters, thisHostName, variables)
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "{0}".format(errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    for key, value in CHILTSpec.items():
             
        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-2 JAReadConfigCHILT() processing key:|{0}|, value:{1}".format(key, value),
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

        if value.get('Items') != None:
            ### expect variable definition to be in dict form
            for CHILTName, CHILTParams in value['Items'].items():
                numberOfItems += 1 
                """ item can have below attributes 
                    CHILTParams = [
                        'ComparePatterns',
                        'Command',
                        'Condition',
                        'Cert',
                        'License',
                        'Health',
                        'Inventory'
                        'IgnorePatterns',
                        'Test'
                        ]
                """
                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JAReadConfigCHILT() processing item:|{0}|, attributes:{1}".format(
                            CHILTName, CHILTParams),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                if overridePrevValue == False:
                    if CHILTName in CHILTParameters:
                        if mandatoryAttribute in CHILTParameters[CHILTName]:
                            ### value present for this service already, SKIP current definition
                            ###  this is valid, DO NOT warn for this condition
                            ### spec may be present under individual environment and later in All section
                            continue

                ### If any of Command or Condion is present, other one needs to be present.
                if 'Command' in CHILTParams and 'Condition' not in CHILTParams:
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigCHILT() Item name:{0}, 'Condition' not present, need 'Condition' attribute when 'Command' attribute is specified, Skipped this definition".format(
                            CHILTName ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue
                if 'Command' not in CHILTParams and 'Condition' in CHILTParams:
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigCHILT() Item name:{0}, 'Command' not present, need 'Command' attribute when 'Condition' attribute is specified, Skipped this definition".format(
                            CHILTName ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue

                if mandatoryAttribute not in CHILTParams:
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigCHILT() Item name:{0}, mandatory attribute:{1} is NOT specified, Skipped this definition".format(
                            CHILTName, mandatoryAttribute ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue


                ### substitute variable reference with variable values in mandatoryAttribute 
                ###   Cert, License, Health, Inventory spec line can refer to variables
                ###   variable values will be substituted here                
                originalAttribute = CHILTParams[mandatoryAttribute]
                returnStatus, returnedAttribute = JAGlobalLib.JASubstituteVariableValues( variables, originalAttribute)
                if returnStatus == True:
                    ### variable found and replaced it with variable value,
                    ###  use new value of the attribute
                    CHILTParams[mandatoryAttribute] = returnedAttribute
                    if debugLevel > 2:
                        JAGlobalLib.LogLine(
                            "DEBUG-3 JAReadConfigConn() Item:|{0}|, original {1}:|{2}|, {3} after substituting the variable values:|{4}|".format(
                                CHILTName, mandatoryAttribute, originalAttribute, mandatoryAttribute, returnedAttribute),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                ### store current CHILT details
                CHILTParameters[CHILTName] = CHILTParams

                if 'ComparePatterns' not in CHILTParams:
                    ### set default value
                    CHILTParameters[CHILTName]['ComparePatterns'] = None
                else: 
                    ### evaluate group values using current variable values if group values have any variable spec
                    returnStatus = JAGlobalLib.JAEvaluateComparePatternGroupValues(
                            CHILTName, CHILTParams['ComparePatterns'], variables,
                            interactiveMode, debugLevel,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType )

                if 'IgnorePatterns' not in CHILTParams:
                    CHILTParameters[CHILTName]['IgnorePatterns'] = None   

                ### put default value of None for command and condition if not present
                if 'Condition' not in CHILTParams:
                    CHILTParameters[CHILTName]['Condition'] = None
                if 'Command' not in CHILTParams:
                    CHILTParameters[CHILTName]['Command'] = None

                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JAReadConfigCHILT() stored item name:{0}, attributes:{1}".format(
                            CHILTName, CHILTParameters[CHILTName]),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigCHILT() Read {0} items with {1} warnings, {2} errors from AppConfig:{3}".format(
                numberOfItems, numberOfWarnings, numberOfErrors, CHILTSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return True, numberOfItems


def JAOperationCHILT(
    baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion,   
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime, allowedCommands, operation ):

    returnStatus = True
    errorMsg = ''
            
    ### dictionary to hold object definitions
    CHILTParameters = defaultdict(dict)
    summaryResults = defaultdict(dict)

    ### these reserved words are used to parse the yml file and also to report results
    ### key to this dictionary is the operation string passed
    CHILTHeadings = { 'cert': 'Certificate', 'inventory': 'Inventory', 'license': 'License', 'health': 'Health','test': 'Test'}

    if operation in CHILTHeadings:
        if debugLevel > 0:
            JAGlobalLib.LogLine(
                "DEBUG-1 JAOperationCHILT() {0} spec:{1}, subsystem:{2}, appVersion:{3}, interactiveMode:{4}".format(
                operation, baseConfigFileName, subsystem, appVersion, interactiveMode),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
    else:
        errorMsg = "ERROR JAOperationCHILT() Unsupported operation:{0}, operation supported are:|{1}|".format(
                operation, CHILTHeadings.keys() )
        JAGlobalLib.LogLine(
            errorMsg,
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return False, errorMsg

    ### read the object spec file contents
    returnStatus, numberOfItems = JAReadConfigCHILT( 
        operation,
        baseConfigFileName, 
        subsystem, 
        appVersion, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        CHILTParameters, allowedCommands,
        CHILTHeadings[operation] )
    if returnStatus == False:
        ### fatal error, can't proceed.
        return returnStatus, numberOfItems

    ### this file is used as temporary storage for output of commands
    ### this temp file is deleted at the end of compare operation
    currentDataFileName ="{0}/JAAudit.dat.{1}".format(
        defaultParameters['LogFilePath'],
         os.getpid() )

    ### initialize counters to track summary
    ### numberOfErrors - when connectivity fails to all hosts
    ### numberOfFailures - when at least one connection fails to HostNames, 
    ###       typically set when there are more than one host in HostNames
    ### numberOfConditionsMet - connectivity test performed after conditions met
    ### numberOfConditionsNotMet - connectivity test NOT performed since condition was not met
    numberOfItems = numberOfErrors = numberOfFailures  = numberOfConditionsMet = numberOfConditionsNotMet = numberOfPasses = 0
    numberOfComparePatternMatched = numberOfComparePatternNotMatched = 0

    reportFileNameWithoutPath = "JAAudit.{0}.{1}".format( operation, JAGlobalLib.UTCDateForFileName() )
    reportFileName = "{0}/{1}".format( defaultParameters['ReportsPath'], reportFileNameWithoutPath )
    with open( reportFileName, "w") as reportFile:

        ### write report header
        reportFile.write(
"TimeStamp: {0}\n\
Platform: {1}\n\
HostName: {2}\n\
Environment: {3}\n\
Items:\n\
".format(JAGlobalLib.UTCDateTime(), defaultParameters['Platform'], thisHostName, defaultParameters['Environment']) )

        currentTime = time.time()

        ### save or compare information of each object
        for CHILTName in CHILTParameters:
            numberOfItems += 1
            CHILTAttributes = CHILTParameters[CHILTName]

            summaryResults[CHILTName]['Condition'] = 'Unknown'
            summaryResults[CHILTName]['Status'] = 'Unknown'
            summaryResults[CHILTName]['Details'] = 'Unknown'
            
            reportFile.write(
"   {0}:\n\
        Command: {1}\n\
        Condition: {2}\n\
        {3}: {4}\n\
        ComparePatterns: {5}\n\
        Results:\n".format(
            CHILTName,
            CHILTAttributes['Command'],
            CHILTAttributes['Condition'],
            CHILTHeadings[operation],
            CHILTAttributes[ CHILTHeadings[operation] ],
            CHILTAttributes['ComparePatterns'],
            CHILTAttributes['IgnorePatterns']
        ))

            if debugLevel > 2:
                JAGlobalLib.LogLine(
                    "DEBUG-3 JAOperationCHILT() Processing {0} name:|{1}|, {2} attributes:|{3}|".format(
                    operation, CHILTName, operation, CHILTAttributes),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            """
            CHILT attributes are:
                'Command',
                'Condition',
                'Cert', 'Inventory', 'License', 'Health','Test'
                'ComparePatterns', 'IgnorePatterns'
            """
            conditionPresent, conditionMet = JAGlobalLib.JAEvaluateCondition(
                                CHILTName, CHILTAttributes, defaultParameters, debugLevel,
                                interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)

            if conditionPresent == True:
                if conditionMet == False:
                    ### SKIP connectivity test, condition not met
                    numberOfConditionsNotMet += 1
                    ### log result, align the spaces so that yaml layout format is satisfied.
                    ### align strat of text to follow yaml file space format
                    ###  leading space before printing the message below is intentional
                    reportFile.write("\
            Skipped, condition not met\n")

                    summaryResults[CHILTName]['Condition'] = 'Not Met'
                    summaryResults[CHILTName]['Status'] = 'INFO'
                    summaryResults[CHILTName]['Details'] = 'Skipped'

                    continue
                else:
                    numberOfConditionsMet += 1
                    summaryResults[CHILTName]['Condition'] = 'Met'
            else:
                summaryResults[CHILTName]['Condition'] = 'None'

            resultCounterUpdated = False
            ### operation specific command, expand any environment variables used in that command
            tempCommand = os.path.expandvars( CHILTAttributes[ CHILTHeadings[operation] ])

            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                defaultParameters['CommandShell'],
                tempCommand, debugLevel, OSType)
            if returnResult == False:
                if re.match(r'File not found', errorMsg) != True:
                    JAGlobalLib.LogLine(
                        "ERROR JAOperationCHILT() item:{0}, error performing operation:{1}, errorMsg:|{2}|".format(
                            CHILTName, operation, errorMsg), 
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfErrors += 1
                    summaryResults[CHILTName]['Status'] = 'FAIL'
                    summaryResults[CHILTName]['Details'] = errorMsg
                    continue
            else:
                ### used to avoid displaying the error message twice
                donotDisplayError = False
                errorMsg = ''
                if operation == 'cert':
                    ### parse the output for out of range dates
                    if OSType == 'Windows':
                        JAGlobalLib.LogLine(
                            "ERROR JAOperationCHILT() parsing output in windows platform not ready yet, returnOutput:{0}".format(returnOutput), 
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        for line in returnOutput:
                            ### align strat of text to follow yaml file space format
                            ###  leading space before printing the message below is intentional                                    
                            reportFile.write("\
                {0}\n".format(line))
                        summaryResults[CHILTName]['Status'] = 'TBD'
                        summaryResults[CHILTName]['Details'] = 'code not ready yet'

                    else:
                        """
                        Unix/Linux output in the form
    notBefore=Nov 13 15:42:21 2022 GMT
    notAfter=Nov 13 15:42:21 2023 GMT
    issuer=C = US, ST = TX, L = Plano, O = Internet Widgits Pty Ltd, CN = havembha
    <No Alias>
    subject=C = US, ST = TX, L = Plano, O = Internet Widgits Pty Ltd, CN = havembha
                        """

                        for line in returnOutput:
                            ### output may be in the form
                            ###  notBefore=Nov 13 15:42:21 2022 GMT
                            ###  notAfter=Nov 13 15:42:21 2023 GMT
                            ### or 
                            ###    Not Before:Nov 13 15:42:21 2022 GMT
                            ###    Not After:Nov 13 15:42:21 2023 GMT
                            ###
                            dates = line.split(r'=|:')
                            
                            if len(dates) > 1:
                                if re.match(r'^notBefore|Not Before', dates[0]):
                                    ### convert not before date to seconds
                                    timeInSec = JAGlobalLib.JAConvertStringTimeToTimeInMicrosec( 
                                        dates[1], "%b %d %H:%M:%S %Y %Z")
                                    if timeInSec > currentTime:
                                        ### cert notBefore date is in future, declare error
                                        numberOfErrors += 1
                                        resultCounterUpdated = True
                                        errorMsg += "ERROR JAOperationCHILT() Cert {0} has future 'notBefore date' {1}".format(CHILTName, dates[1] )
                                        line = "ERROR {0}".format(line)

                                        summaryResults[CHILTName]['Status'] = 'FAIL'
                                        summaryResults[CHILTName]['Details'] = 'Future NotBefore date'

                                elif re.match(r'^notAfter|Not After', dates[0]):
                                    ### convert not After date to seconds
                                    timeInSec = JAGlobalLib.JAConvertStringTimeToTimeInMicrosec( 
                                        dates[1], "%b %d %H:%M:%S %Y %Z")
                                    if timeInSec < currentTime:
                                        ### cert notAfter date is in the past, declare error
                                        numberOfErrors += 1
                                        summaryResults[CHILTName]['Status'] = 'FAIL'
                                        summaryResults[CHILTName]['Details'] = 'Expired cert'

                                        resultCounterUpdated = True
                                        errorMsg += "ERROR JAOperationCHILT() Cert {0} expired already, 'notAfter date' {1}".format(CHILTName, dates[1] )
                                        line = "ERROR {0}".format(line)
                            ### align strat of text to follow yaml file space format
                            ###  leading space before printing the message below is intentional                                    
                            reportFile.write("\
                {0}\n".format(line))


                elif operation == 'test':

                    ### if ComparePatterns is not present, compare current result to the expected result file
                    if 'ComparePatterns' in CHILTAttributes:
                        if CHILTAttributes['ComparePatterns'] == None:
                            compareResults = True
                            ### expect reference file in custom path with test name; as specified in test yml file, as file name. 
                            referenceFileName = "{0}/{1}/{2}".format(
                                defaultParameters['LocalRepositoryHome'], 
                                defaultParameters['LocalRepositoryCustom'],
                                CHILTName )
                            ### current result in Logs directory with <testName>.current as file name
                            currentResponseFileName = "{0}/{1}.current".format(
                                defaultParameters['LogFilePath'], 
                                CHILTName )
                            ### save the current results
                            try:
                                with open( currentResponseFileName, "w") as file:
                                    for line in returnOutput:
                                        file.write(line+'\n')
                                    file.close()
                            except OSError as err:
                                errorMsg += "ERROR JAOperationCHILT() Can't write test:|{0}| result to temporary file:|{1}|, OSError:|{2}|".format(
                                    CHILTName, currentResponseFileName, err)
                                compareResults = False
                                numberOfErrors += 1
                                resultCounterUpdated = True
                                summaryResults[CHILTName]['Status'] = 'FAIL'
                                summaryResults[CHILTName]['Details'] = "Can't save results to a file for comparison"

                            if compareResults == True:
                                ### compare current result with reference reference file
                                returnStatus, fileDiffer, errorMsg = JAOperationSaveCompare.JAOperationCompareFiles(
                                    currentResponseFileName, referenceFileName, 
                                    defaultParameters['BinaryFileTypes'],
                                    'text', # compareType
                                    defaultParameters['CompareCommand'],
                                    False, ### not H2H compare scenario
                                    CHILTAttributes['IgnorePatterns'],  
                                    "{0}".format(CHILTAttributes['Test']), ### logAdditionalInfo - command used to run test
                                    interactiveMode, debugLevel,
                                    myColors, colorIndex, outputFileHandle, HTMLBRTag,
                                    OSType,
                                    defaultParameters['CommandShell'],
                                    defaultParameters['LogFilePath'])
                                if returnStatus == True:
                                    if fileDiffer == True:
                                        JAGlobalLib.LogLine(
                                            "ERROR JAOperationCHILT() test:|{0}|, current result:|{1}| differs from expected result:|{2}|".format(
                                            CHILTName, currentResponseFileName, referenceFileName ), 
                                            interactiveMode,
                                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                                        numberOfFailures += 1
                                        summaryResults[CHILTName]['Status'] = 'DIFF'
                                        summaryResults[CHILTName]['Details'] = "Current result differ from expected result"

                                        resultCounterUpdated = True
                                        ### below is to ensure that numberOfPasses is not incremented later for this case.
                                    else:
                                        ### treat ignorable difference as pass
                                        numberOfPasses += 1
                                        resultCounterUpdated = True
                                        summaryResults[CHILTName]['Status'] = 'PASS'
                                        summaryResults[CHILTName]['Details'] = "Seen ignorable differences only"
                                else:
                                    numberOfFailures += 1
                                    resultCounterUpdated = True
                                    summaryResults[CHILTName]['Status'] = 'FAIL'
                                    summaryResults[CHILTName]['Details'] = "Error comparing current result to expected result file"

                    for line in returnOutput:
                        ### align strat of text to follow yaml file space format
                        ###  leading space before printing the message below is intentional                                    
                        reportFile.write("\
                {0}\n".format(line))
                    if errorMsg != '':
                        reportFile.write("\
                {0}\n".format(errorMsg))
                    errorMsg = ''

                else:
                    ### for license, health operations, log the output to result file
                    for line in returnOutput:
                        ### align strat of text to follow yaml file space format
                        ###  leading space before printing the message below is intentional                                    
                        reportFile.write("\
            {0}\n".format(line))


                ### common processing for cert, license, inventory, and health operations
                ### for all other lines, try to match using  compare patterns if present 
                if 'ComparePatterns' in CHILTAttributes:
                    if CHILTAttributes['ComparePatterns'] != None:
                        ### check whether the command output has search patterns
                        returnStatus, patternsMatched, patternsNotMatched, errorMsg = JAGlobalLib.JAComparePatterns(
                                CHILTName,
                                CHILTAttributes['ComparePatterns'], None, returnOutput,
                                interactiveMode, debugLevel,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)
                        if returnStatus == False:
                            ### one or more pattern not present, declare error
                            numberOfFailures += 1

                            summaryResults[CHILTName]['Status'] = 'FAIL'
                            summaryResults[CHILTName]['Details'] = "One or more pattern not present"

                            resultCounterUpdated = True
                            tempErrorMsg = "ERROR JAOperationCHILT() {0}:{1} ComparePatterns:|{2}| NOT matched".format(
                                CHILTHeadings[operation], CHILTName, CHILTAttributes['ComparePatterns'] )
                            errorMsg += tempErrorMsg
                            ### align strat of text to follow yaml file space format
                            ###  leading space before printing the message below is intentional
                            reportFile.write("\
        {0}\n".format(errorMsg))

                        ### even under partial match, these variables will be set.
                        numberOfComparePatternMatched += patternsMatched 
                        numberOfComparePatternNotMatched += patternsNotMatched

                if errorMsg != '':
                        JAGlobalLib.LogLine(
                            errorMsg,
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                
                ### if result is not yet updated, no error occured, consider it as pass
                if resultCounterUpdated == False:
                    numberOfPasses += 1
                    summaryResults[CHILTName]['Status'] = 'PASS'
                    summaryResults[CHILTName]['Details'] = ""

        JAGlobalLib.LogLine(
            "SummaryStart++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n\
Total Items:{0}, conditions met:{1}, conditions NOT met:{2}, \
all passed:{3}, failed:{4}, ComparePatterns matched:{5}, ComparePatterns NOT matched:{6}, errors:{7}\n".format(
            numberOfItems, numberOfConditionsMet, numberOfConditionsNotMet, numberOfPasses, numberOfFailures, 
            numberOfComparePatternMatched, numberOfComparePatternNotMatched, numberOfErrors ),
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
    ComparePatternsMatched: {5}\n\
    ComparePatternsNotMatched: {6}\n\
    Error: {7}\n\
    Details:\n\
".format( numberOfItems, numberOfConditionsMet, numberOfConditionsNotMet, numberOfPasses, numberOfFailures, 
            numberOfComparePatternMatched, numberOfComparePatternNotMatched, numberOfErrors ) )

        ### print heading for details tables
        JAGlobalLib.LogLine(
            "{0:26s} {1:6s} {2:48s} {3:12s} {4}".format(
                "DateTime","Status", "Item", "Condition", "Details" ),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        reportFile.write("\
        {0:6s} {1:48s} {2:12s} {3}\n".format(
            "Status", "Item", "Condition", "Details" ) )

        ### Now, write concise report line per item
        for CHILTName in CHILTParameters:
            JAGlobalLib.LogLine(
            "{0:6s} {1:48s} {2:12s} {3}".format(
                summaryResults[CHILTName]['Status'], 
                CHILTName, 
                summaryResults[CHILTName]['Condition'], 
                summaryResults[CHILTName]['Details'] ),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

            reportFile.write("\
        {0:6s} {1:48s} {2:12s} {3}\n".format(
                summaryResults[CHILTName]['Status'], 
                CHILTName, 
                summaryResults[CHILTName]['Condition'], 
                summaryResults[CHILTName]['Details'] ) )
        
        reportFile.close()

        JAGlobalLib.LogLine(
            "SummaryEnd---------------------------------------------------------------\n\n".format(),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        ### if interactive session, display the report file
        if interactiveMode == True:
            JAGlobalLib.JAPrintFile( reportFileName)

        ### add current report file to upload list if upload is opted
        if re.search(r'upload', defaultParameters['Operations']):
            defaultParameters['ReportFileNames'].append(reportFileNameWithoutPath)

        
    ### write history file
    JAGlobalLib.JAUpdateHistoryFileName(subsystem, operation, defaultParameters )

    return returnStatus, errorMsg