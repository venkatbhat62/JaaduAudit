"""
This file contains the functions to gather stats from log files
Author: havembha@gmail.com, 2022-12-25
error
Execution Flow
    Read stats spec yml file to buffer. Spec file layout is common for perfStatsApp operation, used by JaaduVision/JAGatherLogStats.py
    Extract operation specific parametrs from yml buffer.
    Below params are used by this module
    From Environment section
        HostName:
        PatternTimeStamp:
        TimeStampGroup:

    From LogFile section,
        Item (or log event name)
        LogFileName: 
        PatternCount: 
        PatternPass:
        PatternFail:
        PatternAverage:
        PatternDelta:
        PatternSum:
        PatternTimeStamp:
        TimeStampGroup:

    If interactive mode, display results
    Else, store the results to a JAAudit.<operation>.YYYYMMDD file
    If upload is enabled, add report file to upload file list
    Create JAAudit.<operation>.history file

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

def JAReadConfigLogsStats(
        operation, 
        baseConfigFileName, 
        subsystem, 
        version, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        statsParameters, allowedCommands):
        
    """
   Parameters passed:
        operation - like stats, logs
        baseConfigFileName - Vaue of 'AppConfig' parameter defined in JAEnvironment.yml for that host or component for that environment
        subsystem - if not empty, it will be Prefixed to derive config file
        version - if not empty, suffixed to the baseConfigFileName to find release specific config file
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel, 
        statsSpec - full details, along with default parameters assigned, are returned in this dictionary
        allowedCommands - commands allowed to be executed

    Returned Values:
        returnStatus - True on success, False upon file read error
        numberOfItems - number of items read

    Refer to yml file of 'JaaduVisionPath'/JAGatherLogStats.yml for details of yml spec.

    """
    returnStatus = False
    errorMsg = ''
    numberOfItems = 0
    numberOfErrors = 0
    numberOfWarnings = 0

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigLogsStats() Operation: {0}, AppConfig:{1}, subsystem:{2}, version:{3} ".format(
                operation, baseConfigFileName, subsystem, version),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    baseConfigFileNameParts = baseConfigFileName.split('.')
    if len(baseConfigFileNameParts) != 2:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigLogsStats() AppConfig name not in expected format, no . (dot) in filename:|{0}|".format(baseConfigFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        return returnStatus, numberOfItems

    ### use the spec file specified as is for the current host.
    ### For 'stats' operation, 
    ###   if 'JaaduVisionPath' is not None, spec file will be searched there.
    ###   else, the spec file is expected to be at path pointed by 'LocalRepositoryCustom'
    statsSpecPath1 = statsSpecPath2 = ''
    tempBaseConfigFileName = ''
    useDefaultPerfStatsAppsConfig = False
    if 'JaaduVisionPath' not in defaultParameters:
        useDefaultPerfStatsAppsConfig = True
    elif defaultParameters['JaaduVisionPath'] == '' or defaultParameters['JaaduVisionPath'] == 'None':
        useDefaultPerfStatsAppsConfig = True
    elif 'PerfStatsAppsConfig' not in defaultParameters:
        useDefaultPerfStatsAppsConfig = True

    if useDefaultPerfStatsAppsConfig == True:
        statsSpecPath1 = "{0}/{1}".format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCustom'])
        statsSpecPath2 = "{0}/{1}".format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCommon'])
        tempBaseConfigFileName = baseConfigFileName
    else:
        statsSpecPath1 = "{0}".format(defaultParameters['JaaduVisionPath'] )
        statsSpecPath2 = "{0}/{1}".format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCustom'])
        tempBaseConfigFileName = defaultParameters['PerfStatsAppsConfig']

    returnStatus, statsSpecFileName, errorMsg = JAGlobalLib.JADeriveConfigFileName( 
          statsSpecPath1, statsSpecPath2,  
          tempBaseConfigFileName, subsystem, operation, version, debugLevel )
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigLogsStats() AppConfig:|{0}| not present, error:|{1}|".format(tempBaseConfigFileName, errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, numberOfItems
        
    if debugLevel > 1:
        JAGlobalLib.LogLine(
            "DEBUG-2 JAReadConfigLogsStats() Derived AppConfig file:|{0}|, defaultParameters['JaaduVisionPath']:|{1}|, defaultParameters['PerfStatsAppsConfig']:|{2}|".format(
                statsSpecFileName, defaultParameters['JaaduVisionPath'], defaultParameters['PerfStatsAppsConfig']),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### Now read the yml file
    # use limited yaml reader when yaml is not available
    if yamlModulePresent == True:
        try:
            import yaml
            with open(statsSpecFileName, "r") as file:
                statsSpec = yaml.load(file, Loader=yaml.FullLoader)
                file.close()
        except OSError as err:
            errorMsg = "ERROR JAReadConfigLogsStats() Can not open configFile:|{0}|, OS error:|{1}|\n".format(
                statsSpecFileName, err)
            JAGlobalLib.LogLine(
                "ERROR JAReadConfigLogsStats() AppConfig:|{0}| not present, error:|{1}|".format(statsSpecFileName, errorMsg),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    else:
        statsSpec = JAGlobalLib.JAYamlLoad(statsSpecFileName)

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

    ### below param value spec can use variable names in them.
    paramsWithVariables = ['PatternCount', 'PatternPass', 'PatternFail', 'PatternAverage', 'PatternDelta', 'PatternSum', 'PatternLog']
    ### extract below attributes of log events from yml spec file
    paramsToStore = [ 
        'LogFileName', 'PatternCount', 'PatternPass', 'PatternFail', 'PatternLog', 'MaxLogLines', 'Priority',
        'PatternAverage', 'PatternDelta', 'PatternSum', 'PatternTimeStamp', 'TimeStampGroup'
    ]
    paramsToSkipWhenPassFailPresent = [ 'PatternCount', 'PatternAverage', 'PatternDelta', 'PatternSum' ]
    patternTimeStamp = ''
    timeStampGroup = 1
    maxLogLinesPerLogEvent = 10

    if 'Environment' in statsSpec:
        for key, value in statsSpec['Environment'].items():
             
            if debugLevel > 1:
                JAGlobalLib.LogLine(
                    "DEBUG-2 JAReadConfigLogsStats() processing key:|{0}|, value:{1}".format(key, value),
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

            ### default values that applies to all log files if local definition does not exist
            if value.get('PatternTimeStamp') != None:
                patternTimeStamp = value.get('PatternTimeStamp') 
            if value.get('TimeStampGroup') != None:
                timeStampGroup = value.get('TimeStampGroup')
            if value.get('MaxLogLines') != None:
                maxLogLinesPerLogEvent = value.get('MaxLogLines')

    if 'LogFile' in statsSpec:
        for key, value in statsSpec['LogFile'].items():
            numberOfItems += 1 
            if debugLevel > 1:
                JAGlobalLib.LogLine(
                    "DEBUG-2 JAReadConfigLogsStats() processing log event:|{0}|, attributes:{1}".format(
                        key, value),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

            if 'LogFileName' not in value:
                JAGlobalLib.LogLine(
                    "ERROR JAReadConfigLogsStats() 'LogFileName' not present for the log event:|{0}|, attributes:{1}, skipping this event".format(
                        key, value),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                continue
            else:
                logFileName = value['LogFileName']

            if overridePrevValue == False:
                if key in statsParameters[logFileName]:
                    ### value present for this log event already, SKIP current definition
                    ###  this is valid, DO NOT warn for this condition
                    ### spec may be present under individual environment and later in All section
                    continue

            logEventAttributes = defaultdict(dict)

            ### expect variable definition to be in dict form
            for paramName, paramValue in value.items():
                """ log event can have below attributes 
                    paramValue = [
                        LogFileName: 
                        MaxLogLines:
                        PatternCount: 
                        PatternFail:
                        PattenrLog:
                        PatternPass:
                        PatternTimeStamp:
                        Priority:
                        TimeStampGroup:
                        ]
                """
                if paramName not in paramsToStore:
                    continue

                if paramName in paramsToSkipWhenPassFailPresent and ( 'PatternPass' in value or 'PatternFail' in value):
                    if debugLevel > 0:
                        JAGlobalLib.LogLine(
                            "DEBUG-1 JAReadConfigLogsStats() log event:{0}, attributes:{1}, attribute:{2} is present along with 'PatternPass', 'PatternFail', Skipped this attribute".format(
                                key, value, paramName ),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue

                ### substitute variable reference with variable values
                if paramName in paramsWithVariables:
                    ###   variable values will be substituted here                
                    originalAttribute = paramValue
                    returnStatus, returnedAttribute = JAGlobalLib.JASubstituteVariableValues( variables, originalAttribute)
                    if returnStatus == True:
                        ### variable found and replaced it with variable value,
                        ###  use new value of the attribute
                        paramValue = returnedAttribute
                        if debugLevel > 2:
                            JAGlobalLib.LogLine(
                                "DEBUG-3 JAReadConfigConn() log event:|{0}|, original {1}:|{2}|, {3} after substituting the variable values:|{4}|".format(
                                    key, paramName, originalAttribute, paramName, returnedAttribute),
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                
                logEventAttributes[paramName] = paramValue

            ### if PatternTimeStamp, TimeStampGroup are not defined, use default one
            if 'PatternTimeStamp' not in logEventAttributes:
                logEventAttributes['PatternTimeStamp'] = patternTimeStamp
            if 'TimeStampGroup' not in logEventAttributes:
                logEventAttributes['TimeStampGroup'] = timeStampGroup
            ### if MaxLogLines is not defined for current log event, use the default one
            if 'MaxLogLines' not in logEventAttributes:
                logEventAttributes['MaxLogLines'] = maxLogLinesPerLogEvent

            statsParameters[logFileName][key] = dict(logEventAttributes)

            if debugLevel > 1:
                JAGlobalLib.LogLine(
                    "DEBUG-2 JAReadConfigLogsStats() stored log event:{0}, attributes:{1}".format(
                        key, logEventAttributes),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                
    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigLogsStats() Read {0} items with {1} warnings, {2} errors from AppConfig:{3}".format(
                numberOfItems, numberOfWarnings, numberOfErrors, statsSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return True, numberOfItems

def JAProcessLogFile( 
                operation,
                OSType, outputFileHandle, colorIndex, HTMLBRTag, myColors,
                interactiveMode, defaultParameters, debugLevel, thisHostName,
                statsAttributes, fromTimeInSec, toTimeInSec,
                logFileName ):
    """
    This function processes given log file, searches for events within the time interval specified

    Open the log file that was changed within the FromTime specified, using binary halving method, locate the starting log line
    Read each log line, if the timestamp is before the 'ToTime', 
    For 'stats' operation,
        search for patterns matching 'PatternCount', 'PatternPass', 'PatternFail' and increment the count in summaryResults if pattern found
    For 'logs' operation,
        search for patterns matching 'PatternLog', display that line if priority of that log event is less than or equal to the
          log event priority desired

    """
    returnStatus = True
    errorMsg = ''

    ### find log files changed within the desired time window
    logFiles = JAGlobalLib.JAFindModifiedFiles(
        logFileName, 
        (0- int(fromTimeInSec*1000000)/1000000), ### pass -ve number to find files changed in last X seconds
        debugLevel, 
        thisHostName )

    if len(logFiles) == 0:
        ### if log file is not found, try to find them under 'JaaduVisionPath'
        logFiles = JAGlobalLib.JAFindModifiedFiles(
            "{0}/{1}".format( defaultParameters['JaaduVisionPath'], logFileName), 
            (0- int(fromTimeInSec*1000000)/1000000), ### pass -ve number to find files changed in last X seconds
            debugLevel, 
            thisHostName )

    if len(logFiles) == 0:
        return False

    ### get values at log file level from first key definition
    ###  all keys are expected to have same attributes since log line format is same for all those keys
    for key, attributes in statsAttributes.items():
        patternTimeStamp = attributes['PatternTimeStamp']
        timeStampGroup = attributes['TimeStampGroup']
        break

    if operation == 'stats':
        ### initialize counters to zero
        for key, attributes in statsAttributes.items():
            attributes['CountPass'] = attributes['CountFail'] = 0
    else:
        maxLogLines = defaultParameters['MaxLogLines']
        logEventPriority = defaultParameters['LogEventPriority']

    if debugLevel > 1:
        if operation == 'stats':
            tempMsg = "DEBUG-2 JAProcessLogFile() processing log files:|{0}|".format(logFiles )
        else:
            tempMsg = "DEBUG-2 JAProcessLogFile() processing log files:|{0}| with priority:{1}, maxLogLines:{2}".format(
                logFiles, logEventPriority, maxLogLines )
        JAGlobalLib.LogLine(
            tempMsg,
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    displayLogFileName = True
    for logFileName in logFiles:
        try:
            fileSize = os.path.getsize(logFileName)
            logTimePointFound = False
            with open(logFileName, "r") as file:
                ### Open the log file that was changed within the FromTime specified, using binary halving method, locate the starting log line
                filePosition = int(fileSize / 2)
                lastCheck = 0
                lastPosition = 0
                logLine = ''
                while logTimePointFound == False:
                    file.seek( filePosition, 0)
                    ### read two lines so that 2nd line has full line, including timestamp
                    logLine = file.readline()
                    logLine = file.readline()
                    filePosition = file.tell()
                    ### if PatternTimeStamp is not defined, try to find out the timestamp format 
                    if patternTimeStamp == '':
                        returnStatus, patternTimeStamp = JAGlobalLib.JAFindTimeStampPattern( logLine )
                        if returnStatus == False:
                            JAGlobalLib.LogLine(
                                "ERROR JAProcessLogFile() Not able to guess time stamp pattern from log line:|{0}|, add 'PatternTimeStamp' to yml spec file, skipping this log file".format(
                                logFileName),
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                            file.close()
                            return False
                    ### search for timestamp pattern
                    try:
                        myResults = re.findall( r"{0}".format(patternTimeStamp), logLine)
                        patternMatchCount =  len(myResults)
                        if myResults != None and patternMatchCount > 0 :
                            ### if patterns found is greater than or equal to timeStampGroup, pick up the timeStamp value
                            if patternMatchCount >= timeStampGroup:
                                currentTimeStampString = str(myResults[timeStampGroup-1])
                                returnStatus, timeInSeconds, errorMsg = JAGlobalLib.JAParseDateTime(currentTimeStampString )
                                if returnStatus == False:
                                    JAGlobalLib.LogLine(
                                        "ERROR JAProcessLogFile() Error parsing the timestamp string:|{0}|, picked up from log line:|{1}, using the 'PatternTimeStamp' spec:|{2}|, event:{3}, logFile:|{4}|, errorMsg:|{5}|".format(
                                        currentTimeStampString, logLine, patternTimeStamp, key, logFileName, errorMsg),
                                        interactiveMode,
                                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                                    return returnStatus, 0

                                if timeInSeconds >  fromTimeInSec:                             
                                    ### current time is greater than fromTime desired
                                    if lastCheck < 0:
                                        ### last check was less than fromTime
                                        filePosition = lastPosition
                                        if filePosition < 0:
                                            filePosition = 0
                                        file.seek( filePosition, 0)
                                        break

                                    if filePosition < 3000:
                                        file.seek( 0, 0)
                                        break

                                    lastPosition =  filePosition
                                    filePosition = int(filePosition / 2)
                                    lastCheck = 1
                                elif timeInSeconds < fromTimeInSec:   
                                    ### current time is less than fromTime desired
                                    if lastCheck > 0:
                                        ### last time current timestamp was greater than fromTime
                                        break
                                    lastCheck = -1
                                    if filePosition > ( fileSize - 3000) :
                                        file.seek( filePosition, 0)
                                        break
                                    lastPosition = filePosition
                                    filePosition = filePosition + int((fileSize - filePosition)/2)
                            else:
                                ### position to end of current line, to read next line that may have timestamp
                                filePosition += len(logLine)
                    except re.error as err: 
                        JAGlobalLib.LogLine(
                            "ERROR JAProcessLogFile() invalid timestamp pattern:|{0}|, regular expression error:|{1}|, skipping the log file:|{2}|".format(
                                patternTimeStamp,err, logFileName),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                        file.close()
                        return False

                ### now process log lines until the timestamp is greater than toTime passed
                while True:
                    logLine = file.readline()
                    if not logLine:
                        break
                    myResults = re.findall( r"{0}".format(patternTimeStamp), logLine)
                    patternMatchCount =  len(myResults)
                    if myResults != None and patternMatchCount > 0 :
                        ### if patterns found is greater than or equal to timeStampGroup, pick up the timeStamp value
                        if patternMatchCount >= timeStampGroup:
                            currentTimeStampString = str(myResults[timeStampGroup-1])
                            returnStatus, timeInSeconds, errorMsg = JAGlobalLib.JAParseDateTime(currentTimeStampString )
                            if returnStatus == False:
                                JAGlobalLib.LogLine(
                                    "ERROR JAProcessLogFile() Error parsing the timestamp string:|{0}|, picked up from log line:|{1}, using the 'PatternTimeStamp' spec:|{2}|, event:{3}, logFile:|{4}|".format(
                                    currentTimeStampString, logLine, patternTimeStamp, key, logFileName),
                                    interactiveMode,
                                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                                break

                            if timeInSeconds < fromTimeInSec:
                                ### current time is less than desired time, continue to process next log line
                                ### this can happen when binary search of the log file is not at exact time location.
                                continue
                            if timeInSeconds > toTimeInSec:
                                ### current time is greater than desired window, get out
                                break

                    if debugLevel > 2:
                        tempMsg = "DEBUG-3 JAProcessLogFile() processing line:|{0}|".format( logLine )
                        JAGlobalLib.LogLine(
                            tempMsg,
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                    ### search for log events in current line
                    for key, attributes in statsAttributes.items():
                        foundMatch = False
                        if debugLevel > 2:
                            tempMsg = "DEBUG-3 JAProcessLogFile()                  log event:|{0}|".format( key )
                            JAGlobalLib.LogLine(
                                tempMsg,
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                        if operation == 'stats':
                            if 'PatternFail' in attributes:
                                myResults = re.search(attributes['PatternFail'], logLine)
                                if myResults != None:
                                    attributes['CountFail'] += 1
                                    foundMatch = True
                            if foundMatch == False and 'PatternPass' in attributes:
                                myResults = re.search(attributes['PatternPass'], logLine)
                                if myResults != None:
                                    attributes['CountPass'] += 1
                                    foundMatch = True
                            if foundMatch == False and 'PatternCount' in attributes:
                                myResults = re.search(attributes['PatternCount'], logLine)
                                if myResults != None:
                                    attributes['CountPass'] += 1
                                    foundMatch = True
                        else:
                            ### logs operation
                        
                            ### max log lines parameter passed from command line overrides the value specified in yml file
                            if maxLogLines != None:
                                tempMaxLogLines = maxLogLines
                            else:
                                if 'MaxLogLines' not in attributes:
                                    tempMaxLogLines = None
                                else:
                                    tempMaxLogLines = attributes['MaxLogLines']

                            if 'LogLinesCount' not in attributes:
                                ### first time, it will not be there, initialize to zero
                                attributes['LogLinesCount'] = 0

                            if tempMaxLogLines != None:
                                if attributes['LogLinesCount'] < tempMaxLogLines:
                                    displayCurrentLogLine = True
                                else:
                                    if 'DisplayedMaxCountReached' not in attributes:
                                        attributes['DisplayedMaxCountReached'] = True
                                        JAGlobalLib.LogLine(
                                            "INFO JAProcessLogFile() reached MaxLogLines:{0} for log event:{1}, logFile:|{2}|, not displaying the log line anymore".format( 
                                                tempMaxLogLines, key, logFileName ),
                                            interactiveMode,
                                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                                    displayCurrentLogLine = False
                            else:
                                displayCurrentLogLine = True

                            if displayCurrentLogLine == True:
                                ### log event priority passed from command line overrides the value specified in yml file
                                if logEventPriority != None:
                                    tempPriority = logEventPriority
                                else:
                                    if 'Priority' not in attributes:
                                        tempPriority = None
                                    else:
                                        tempPriority = attributes['Priority']
                                    
                                if tempPriority != None:
                                    if attributes['Priority'] <= tempPriority:
                                        displayCurrentLogLine = True
                                    else:
                                        displayCurrentLogLine = False
                                else:
                                    displayCurrentLogLine = True

                            if displayCurrentLogLine == True:
                                if 'PatternLog' in attributes:
                                    myResults = re.search(attributes['PatternLog'], logLine)
                                    if myResults != None:
                                        if displayLogFileName == True:
                                            displayLogFileName = False
                                            JAGlobalLib.LogLine(
                                            "\n\nINFO JAProcessLogFile() displaying log lines of log file:|{0}|".format( 
                                                logFileName ),
                                            interactiveMode,
                                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                                        JAGlobalLib.LogLine(
                                        "{0}".format( logLine ),
                                        interactiveMode,
                                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                                        attributes['LogLinesCount']  += 1
                file.close()

        except OSError as err:
            JAGlobalLib.LogLine(
                "ERROR JAProcessLogFile() Error reading the log file:|{0}|, OSError:{1}".format(
                    logFileName, err),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return returnStatus

def JAOperationLogsStats(
    baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion,   
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime, allowedCommands, operation ):

    returnStatus = True
    errorMsg = ''
            
    currentTime = time.time()

    ### dictionary to hold object definitions
    statsParameters = defaultdict(dict)
    summaryResults = defaultdict(dict)

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAOperationLogsStats() {0} spec:{1}, subsystem:{2}, appVersion:{3}, interactiveMode:{4}".format(
            'stats', baseConfigFileName, subsystem, appVersion, interactiveMode),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### read the object spec file contents
    returnStatus, numberOfItems = JAReadConfigLogsStats( 
        operation,
        baseConfigFileName, 
        subsystem, 
        appVersion, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        statsParameters, allowedCommands )
    if returnStatus == False:
        ### fatal error, can't proceed.
        return returnStatus, numberOfItems

    reportFileNameWithoutPath = "JAAudit.{0}.{1}".format( operation, JAGlobalLib.UTCDateForFileName() )
    reportFileName = "{0}/{1}".format( defaultParameters['ReportsPath'], reportFileNameWithoutPath )
    if operation == 'stats':
        try:
            reportFile = open( reportFileName, "a")

        except OSError as err:
            JAGlobalLib.LogLine(
                "ERROR JAOperationLogsStats() Can't write report file:|{0}|, OSError:|{1}|".format(
                   reportFileName, err ),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            reportFile = None   
    else:
        reportFile = None

    if operation == 'stats':
        ### write the summary and close the report file
        ### print heading for details tables
        JAGlobalLib.LogLine(
            "SummaryStrat+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++\n\n".format(),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    if reportFile != None:
        ### write report header
        reportFile.write("\
TimeStamp: {0}\n\
    Platform: {1}\n\
    HostName: {2}\n\
    Environment: {3}\n\
    Items:\n\
".format(JAGlobalLib.UTCDateTime(), defaultParameters['Platform'], thisHostName, defaultParameters['Environment']) )


    returnStatus, fromTimeInSec, errorMsg = JAGlobalLib.JAParseDateTime(defaultParameters['FromTime'])
    returnStatus, toTimeInSec, errorMsg = JAGlobalLib.JAParseDateTime(defaultParameters['ToTime'])

    if operation == 'stats':
        JAGlobalLib.LogLine(
            "{0:16s} {1:24s} {2:8s} {3:8s} {4}".format(
                "host", "Event", "Pass/Count", "  Fail", "%Pass" ),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    for logFileName in statsParameters:

        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-3 JAOperationLogsStats() Processing log file:|{0}|, attributes:{1}".format(
                    logFileName, statsParameters[logFileName]),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        ### process log event
        returnStatus = JAProcessLogFile( 
            operation, OSType, outputFileHandle, colorIndex, HTMLBRTag, myColors,
            interactiveMode, defaultParameters, debugLevel, thisHostName,
            statsParameters[logFileName], 
            fromTimeInSec, toTimeInSec, logFileName )

        if operation == 'stats':
            for key, attributes in statsParameters[logFileName].items():
                
                if 'CountPass' in attributes:
                    countPass = attributes['CountPass']
                else:
                    countPass = 0

                if 'CountFail' in attributes:
                    countFail = attributes['CountFail']
                else:
                    countFail = 0

                totalCount = countPass + countFail
                if totalCount > 0:
                    passPercentage = float((countPass *100 )/ totalCount )
                else:
                    passPercentage = float(0.0)
                JAGlobalLib.LogLine(
                "{0:16s} {1:24s} {2:8d} {3:8d}   {4:1.1f}".format(
                    thisHostName, 
                    key, 
                    countPass, 
                    countFail,
                    passPercentage ),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

                if reportFile != None:
                ### write log event details to report file
                    reportFile.write("\
        {0}:\n\
            Pass: {1}\n\
            Fail: {2}\n\
            PercentPass: {3:1.1f}\n".format( key, countPass, countFail, passPercentage ))
    
    if reportFile != None:
        reportFile.close()

    if operation == 'stats':
        JAGlobalLib.LogLine(
            "SummaryEnd---------------------------------------------------------------\n\n".format(),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        ### add current report file to upload list if upload is opted
        if re.search(r'upload', defaultParameters['Operations']):
            defaultParameters['ReportFileNames'].append(reportFileNameWithoutPath)
        
    ### write history file
    JAGlobalLib.JAUpdateHistoryFileName(subsystem, operation, defaultParameters )

    completionTime = time.time()
    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAOperationLogsStats()Elapsed processing time in seconds:{0}".format( completionTime - currentTime),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return returnStatus, errorMsg