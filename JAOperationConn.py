"""
This file contains the functions to handle connectivity check
Author: havembha@gmail.com, 2022-11-06

Execution Flow
    Read connectivity spec yml file to buffer
    Extract connectivity check specific parametrs from yml buffer
    Run connectivity check
    If interactive mode, display results
    Else, store the results to a Reports/JAAudit.conn.YYYYMMDD file
    If upload is enabled, add report file to upload file list
    Write history file

"""

#import os
#import sys
import re
#import datetime
#import time
#import subprocess
#import signal
from collections import defaultdict
import JAGlobalLib


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

    baseConfigFileNameParts = baseConfigFileName.split('.')
    if len(baseConfigFileNameParts) != 2:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigConn() AppConfig name not in expected format, no . (dot) in filename:|{0}|".format(baseConfigFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        return returnStatus, numberOfItems

    ### derive the  spec file, first check under LocalRepositoryCustom, next under LocalRepositoryCommon
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
    variables = defaultdict(dict)
    returnStatus, errorMsg = JAGlobalLib.JASetSystemVariables( defaultParameters, thisHostName, variables)
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "{0}".format(errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

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
            for serviceName, serviceParams in value['Items'].items():
                numberOfItems += 1 
                """ service params can have below attributes 
                    connAttributes = [
                        'Command',
                        'Condition',
                        'HostNames',
                        'Ports',
                        'Protocol'
                        ]
                """
                if overridePrevValue == False:
                    if serviceName in connParameters:
                        if 'HostNames' in connParameters[serviceName]:
                            ### value present for this service already, SKIP current definition
                            ###  this is valid, DO NOT warn for this condition
                            ### spec may be present under individual environment and later in All section
                            continue

                ### If any of Command or Condion is present, other one needs to be present.
                if 'Command' in serviceParams and 'Condition' not in serviceParams:
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigConn() Service name:{0}, 'Condition' not present, need 'Condition' attribute when 'Command' attribute is specified, Skipped this definition".format(
                            serviceName ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue
                if 'Command' not in serviceParams and 'Condition' in serviceParams:
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigConn() Service name:{0}, 'Command' not present, need 'Command' attribute when 'Condition' attribute is specified, Skipped this definition".format(
                            serviceName ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue

                for attribute in serviceParams:
                    attributeValue = serviceParams[attribute]
                    
                    if attribute == 'HostNames':
                        originalAttributeValue = attributeValue
                        returnStatus, attributeValue = JAGlobalLib.JASubstituteVariableValues( variables, attributeValue)
                        if returnStatus == True:
                            if debugLevel > 2:
                                JAGlobalLib.LogLine(
                                    "DEBUG-3 JAReadConfigConn() Service Name:|{0}|, original HostNames:|{1}|, HostNames after substituting the variable values:|{2}|".format(
                                        serviceName, originalAttributeValue, attributeValue),
                                    interactiveMode,
                                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                    connParameters[serviceName][attribute] = attributeValue

                if 'Protocol' not in serviceParams:
                    ### set default protocol
                    connParameters[serviceName]['Protocol'] = 'TCP'

                ### put default value of None for command and condition if not present
                if 'Condition' not in serviceParams:
                    connParameters[serviceName]['Condition'] = None

                if 'Command' not in serviceParams:
                    connParameters[serviceName]['Command'] = None

                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JAReadConfigConn() Service name:{0}, attributes:{1}".format(
                            serviceName, connParameters[serviceName]),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                
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
        JAGlobalLib.LogLine(
            "DEBUG-1 JAOperationConn() Connectivity spec:{0}, subsystem:{1}, appVersion:{2}, interactiveMode:{3}".format(
            baseConfigFileName, subsystem, appVersion, interactiveMode),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
    
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

    ### initialize counters to track summary
    ### numberOfErrors - when connectivity fails to all hosts
    ### numberOfFailures - when at least one connection fails to HostNames, 
    ###       typically set when there are more than one host in HostNames
    ### numberOfConditionsMet - connectivity test performed after conditions met
    ### numberOfConditionsNotMet - connectivity test NOT performed since condition was not met
    numberOfItems = numberOfErrors = numberOfFailures  = numberOfConditionsMet = numberOfConditionsNotMet = numberOfPasses = 0
    numberOfConnectivityTests = 0

    ### environment spec has command with all options
    tcpOptions = udpOptions = ''

    connectionErrors = r"Connection timed out|timed out: Operation now in progress|No route to host"
    hostNameErrors = r"host lookup failed|Could not resolve hostname|Name or service not known"
    connectivityPassed = r"succeeded|Connected to| open"
    connectivityUnknown = r"Connection refused"

    if 'CommandConnCheck' in defaultParameters:
        command = defaultParameters['CommandConnCheck']
    else:
        if OSType == 'Linux':
            # connection check command not defined, use nc by default
            command = 'nc'
            ### assume nc is available on this host
            ### specifiy options for nc command
            if OSVersion < 6:
                tcpOptions = "-vz -w 8"
                udpOptions = "-u"
            else:
                tcpOptions = "-i 1 -v -w 8"
                udpOptions = "-u"
        elif OSType == 'windows':
            command = 'Test-NetConnection'
        elif OSType == 'SunOS':
            command = 'telnet'
        if debugLevel > 1:
            JAGlobalLib.LogLine(
                'DEBUG-2 JAOperationConn() CommandConnCheck parameter not defined in environment spec, using default command:{0}, tcpOptions:{1}, udpOptions:{2}'.format(
                    command, tcpOptions, udpOptions),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    reportFileNameWithoutPath = "JAAudit.conn.{0}".format( JAGlobalLib.UTCDateForFileName() )
    reportFileName = "{0}/{1}".format( defaultParameters['ReportsPath'], reportFileNameWithoutPath )
    with open( reportFileName, "a") as reportFile:

        ### write report header
        reportFile.write("\
TimeStamp: {0}\n\
    Platform: {1}\n\
    HostName: {2}\n\
    Environment: {3}\n\
    Items:\n\
".format(JAGlobalLib.UTCDateTime(), defaultParameters['Platform'], thisHostName, defaultParameters['Environment']) )

        ### save or compare information of each object
        for serviceName in connParameters:
            numberOfItems += 1
            serviceAttributes = connParameters[serviceName]

            if debugLevel > 2:
                JAGlobalLib.LogLine(
                    "DEBUG-3 JAOperationConn() Processing service name:|{0}|, service attributes:|{1}|".format(
                    serviceName, serviceAttributes),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            """
            Service attributes are:
                'Command',
                'Condition',
                'HostNames',
                'Ports',
                'Protocol'
            """
            conditionPresent, conditionMet = JAGlobalLib.JAEvaluateCondition(
                                serviceName, serviceAttributes, defaultParameters, debugLevel,
                                interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)

            if conditionPresent == True:
                if conditionMet == False:
                    if debugLevel > 1:
                        JAGlobalLib.LogLine(
                            "DEBUG-2 JAOperationConn() condition not met for service name:|{0}|, service attributes:|{1}|, skipping the test".format(
                            serviceName, serviceAttributes),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                    ### SKIP connectivity test, condition not met
                    numberOfConditionsNotMet += 1
                    ### log result, align the spaces so that yaml layout format is satisfied.
                    ### leading space in write content is intentional, to align the data per yml format.
                    reportFile.write("\
        {0}:\n\
            Command: {1}\n\
            Condition: {2}\n\
            HostNames: {3}\n\
            Ports: {4}\n\
            Protocol: {5}\n\
            Results:\n\
                Skipped, condition not met\n".format(
                serviceName,
                serviceAttributes['Command'],
                serviceAttributes['Condition'],
                serviceAttributes['HostNames'],
                serviceAttributes['Ports'],
                serviceAttributes['Protocol']
            ))
                    continue
                else:
                    numberOfConditionsMet += 1

            ### if multiple hostnames, make a list to iterate later
            tempHostNames = serviceAttributes['HostNames'].split(',')

            ### if multiple ports or port range, make a list to iterate later
            tempPorts = []
            if re.search(r'-', str(serviceAttributes['Ports'])):
                ### port range specified in the form startPort-endPort
                ###  get all port numbers inclusive of start and end ports
                tempPortRange = serviceAttributes['Ports'].split(r'-')
                for tempPort in range(int(tempPortRange[0]), int(tempPortRange[1])+1):
                    tempPorts.append(str(tempPort))
            else:
                ### if ports are in CSV form, get those in to a list
                tempPorts = str(serviceAttributes['Ports']).split(',')

            if debugLevel > 1:
                JAGlobalLib.LogLine(
                    "DEBUG-2 JAOperationConn() service name:|{0}|, service attributes:|{1}|, hosts:|{2}|, ports:|{3}|".format(
                    serviceName, serviceAttributes, tempHostNames, tempPorts),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

            tempProtocol = serviceAttributes['Protocol']

            ### below are temp counters for current HostNames, Ports set only to iterate through
            passCount = failureCount = numberOfConnectivityTestsPerService = 0

            ### While testing single host and for single port, when it fails, declare ERROR.
            ### while testing multiple hosts or multiple ports, when single test fails, declare FAIL.
            numberOfHostNames = len(tempHostNames)
            numberOfPorts = len(tempPorts)
            if numberOfHostNames > 1 or numberOfPorts > 1:
                errorString = 'FAIL '
            else:
                errorString = 'ERROR'
            
            ### leading space in write content is intentional, to align the data per yml format.
            reportFile.write("\
        {0}:\n\
            Command: {1}\n\
            Condition: {2}\n\
            HostNames: {3}\n\
            Ports: {4}\n\
            Protocol: {5}\n\
            Results:\n".format(
                serviceName,
                serviceAttributes['Command'],
                serviceAttributes['Condition'],
                serviceAttributes['HostNames'],
                serviceAttributes['Ports'],
                serviceAttributes['Protocol']
            ))

            ### now check the conectivity for each destination host and each port
            for tempHostName in tempHostNames:
                for tempPort in tempPorts:
                    numberOfConnectivityTests += 1
                    numberOfConnectivityTestsPerService += 1
                    tempResult = 'TBD'
                    tempReturnStatus,returnOutput, errorMsg = JAGlobalLib.JACheckConnectivity( 
                        tempHostName, tempPort, tempProtocol, command, tcpOptions, udpOptions, OSType, OSName, OSVersion, debugLevel,
                        defaultParameters['CommandShell'])
                    if tempReturnStatus == False:
                        failureCount += 1
                        JAGlobalLib.LogLine(
                            "ERROR JAOperationConn() Error executing command:{0}, error msg:{1}".format(
                                command,  errorMsg ),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        tempResult = 'ERROR'
                        break
                    else:
                        # parse the returnOutput or command output
                        if re.search(connectivityPassed, returnOutput):
                            passCount += 1
                            tempResult = "PASS "
                        elif re.search(connectivityUnknown, returnOutput):
                            failureCount += 1
                            
                            tempResult = errorString
                        elif re.search(connectionErrors, returnOutput):
                            failureCount += 1
                            tempResult = errorString
                        elif re.search(hostNameErrors, returnOutput):
                            failureCount += 1
                            tempResult = errorString
                    JAGlobalLib.LogLine(
                        "{0:5s} {1:12s} {2:24s} {3:6s} {4:3s} {5}".format(
                        tempResult, serviceName, tempHostName, tempPort, tempProtocol, returnOutput ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    
                    ### leading space in write content is intentional, to align the data per yml format.
                    reportFile.write("\
                - Name: {0}\n\
                Port: {1}\n\
                Result: {2}\n\
                Details: {3}\n".format(tempHostName, tempPort, tempResult, returnOutput) )

            tempResult = 'TBD'
            if numberOfConnectivityTestsPerService > 1:
                returnOutput = 'Overall Result for all hosts'
                ### for the case of single hostname and single port, result is already printed before
                if passCount == numberOfConnectivityTestsPerService:
                    ### all connectivity tests passed
                    numberOfPasses += 1
                    tempResult = "PASS "
                elif failureCount == numberOfConnectivityTestsPerService:
                    ### if connectivity fail to all hosts, declare ERROR
                    numberOfErrors += 1
                    tempResult = "ERROR"
                else:
                    ### at least one connectivity passed, indicate partial failure, DO NOT increment ERROR
                    numberOfFailures += 1
                    tempResult = "FAIL "
                JAGlobalLib.LogLine(
                    "{0:5s} {1:12s} {2:24s} {3:6s} {4:3s} {5}".format(
                    tempResult, serviceName, serviceAttributes['HostNames'], serviceAttributes['Ports'], tempProtocol, returnOutput ),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                ### leading space in write content is intentional, to align the data per yml format.
                reportFile.write("\
                - Name: {0}\n\
                Port: {1}\n\
                Result: {2}\n\
                Details: {3}\n".format(serviceAttributes['HostNames'], serviceAttributes['Ports'], tempResult, returnOutput) )
            else:
                ### use single test results as final results
                if passCount > 0:
                    numberOfPasses += 1
                elif failureCount > 0:
                    numberOfErrors += 1

        JAGlobalLib.LogLine(
            "INFO JAOperationConn() Total Services:{0}, conditions met:{1}, conditions NOT met:{2}, \
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


        ### if command present to get listen port info, collect it.
        if 'CommandToGetListenPorts' in defaultParameters:
            if debugLevel > 1:
                JAGlobalLib.LogLine(
                    "DEBUG-2 JAOperationConn() Executing command:|{0} {1}| to get ports in LISTEN state".format(
                    defaultParameters['CommandShell'], defaultParameters['CommandToGetListenPorts']    ), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            
            returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
                defaultParameters['CommandShell'], 
                defaultParameters['CommandToGetListenPorts'], 
                debugLevel, OSType)

            if returnResult == True:
                if len(returnOutput) > 0:
                    reportFile.write("ListenPorts:\n")
                    for line in returnOutput:
                        reportFile.write("\
        {0}\n".format(line))
            else:
                JAGlobalLib.LogLine(
                    errorMsg, 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        reportFile.close()

        ### add current report file to upload list if upload is opted
        if re.search(r'upload', defaultParameters['Operations']):
            defaultParameters['ReportFileNames'].append(reportFileNameWithoutPath)
    
    ### write history file
    JAGlobalLib.JAUpdateHistoryFileName(subsystem, operation, defaultParameters )

    return returnStatus, errorMsg