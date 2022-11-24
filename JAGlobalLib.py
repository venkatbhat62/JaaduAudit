""""
    This module contains global functions used by JadooAudit

    GetGMTTime() - returns string with current GMT time the form YYYY/MM/DD hh:mm:ss.sss
    JAYamlLoad(fileName) - reads the yaml file, returns data in dictionary

    Author: havembha@gmail.com, 2021-06-28
"""
import datetime
import platform
import re
import sys
import os
import time

JACPUUsageFileName = 'JACPUUsage.data'

def UTCDateTime():
    return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S.%f%Z")

def UTCDateTimeForFileName():
    return datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")

def UTCDate():
    return datetime.datetime.utcnow().strftime("%Y-%m-%d")

def UTCDateForFileName():
    return datetime.datetime.utcnow().strftime("%Y%m%d")

def UTCTime():
    return datetime.datetime.utcnow().strftime("%H:%M:%S")

def JAConvertStringTimeToTimeInMicrosec( dateTimeString, format:str):
    # 2022-06-04 add logic to use timezone while converting time to UTC time ???
    try:
        datetime_obj = datetime.datetime.strptime(dateTimeString, format)
        if sys.version_info[0] < 3 or sys.version_info[1] < 4:
            timeInMicroSeconds =  time.mktime(datetime_obj.timetuple()) * 1000000
        else:
            timeInMicroSeconds = datetime_obj.timestamp() * 1000000
        return timeInMicroSeconds
    except:
        return 0

def JAParseArgs(argsPassed):
    args = sys.argv[1:]
    argc = len(args)
    for index in range(0,argc,2):
        argument = args[index]
        argsPassed[argument] = args[index+1]
            
    return argc

def JAIsYamlModulePresent():
    yamlModulePresent = False
    try:
        if sys.version_info.major >= 3 and sys.version_info.minor >= 3:
            import importlib
            from importlib import util
            try: 
                if util.find_spec("yaml") != None:
                    yamlModulePresent = True
                else:
                    yamlModulePresent = False
            except ImportError:
                yamlModulePresent = False

        else:
            yamlModulePresent = False
    except:
        yamlModulePresent = False
    return yamlModulePresent

def JAGetTime( deltaSeconds:int ):
    tempTime = datetime.datetime.now()
    deltaTime = datetime.timedelta(seconds=deltaSeconds)
    newTime = tempTime - deltaTime
    return newTime.strftime("%H:%M:%S")

def JAGetDayOfMonth( deltaSeconds:int ):
    tempTime = datetime.datetime.now()
    deltaTime = datetime.timedelta(seconds=deltaSeconds)
    newTime = tempTime - deltaTime
    newTimeString = newTime.strftime("%d")
    return newTimeString 

def LogMsg(logMsg:str, fileName:str, appendDate=True, prefixTimeStamp=True):
    if fileName == None:
        print(logMsg)
        return 0
        
    if appendDate == True:
        logFileName = "{0}.{1}".format( fileName, UTCDateForFileName())
    else:
        logFileName = fileName

    try:
        logFileStream = open( logFileName, 'a')
    except OSError:
        return 0
    else:
        if ( prefixTimeStamp == True) :
            logFileStream.write( UTCDateTime() + " " + logMsg )
        else:
            logFileStream.write(logMsg )
        logFileStream.close()
        return 1

"""
This function logs the lines passed in myLines to terminal with colors based on first word seen in first line
If tempPrintLine passed is True, formatted line will be printed to the terminal
While printing first line, current timestamp is printed as first two words

Formatting applied to all lines when first word is
^ERROR |^ERROR, - red
^DIFF - blue
^PASS |^ PASS - gren
^INFO - bold

If subsequent lines start with 
< - printed in blue color
> - printed in cyan color
These lines are considerd as output of diff command

Parameters passed:
    myLines - line to print
    tempPrintLine - True or False, if True, formatted line will be printed to the terminal


"""
def LogLine(myLines, tempPrintLine, myColors, colorIndex:int, outputFile:str, HTMLBRTag:str,  diffLine=False, OSType='Linux'):

    currentTime = UTCDateTime() + ' '
    tempLines = myLines.splitlines(False)

    for line in tempLines:
        if colorIndex == 2:
            line = line.replace("<!--",  "/&lt;!--")
            line = line.replace("-->",  "--&gt;")
        
        # repace \r with \n
        line = line.replace(r'\r', r'\n')

        if ( ( (OSType != "Windows") and re.match( '^< ', line) )
            or ( (OSType == "Windows" and re.search(r'<=$' , line) )) 
            and (diffLine == True) ):
            # diff line, color code it
            line = myColors['blue'][colorIndex]  + line + myColors['clear'][colorIndex]
        elif ( ( (OSType != "Windows") and re.match( '^> ', line) )
            or ( (OSType == "Windows" and re.search(r'=>$' , line) )) 
            and (diffLine == True) ):
            # diff line, color code it
            line = myColors['magenta'][colorIndex] + line + myColors['clear'][colorIndex]
        elif re.match( '^ERROR |^ERROR,', line):
            # diff line, color code it
            line = myColors['red'][colorIndex] + currentTime + line + myColors['clear'][colorIndex]
        elif re.match( '^PASS |^ PASS', line):
            # diff line, color code it
            line = myColors['green'][colorIndex] + currentTime + line + myColors['clear'][colorIndex]    
        elif re.match('^DIFF ', line) :
            line = myColors['cyan'][colorIndex] + currentTime + line + myColors['clear'][colorIndex]   
        elif re.match('^WARN ', line) :
            line = myColors['yellow'][colorIndex] + currentTime + line + myColors['clear'][colorIndex]   
        if outputFile != None:
            outputFile.write( HTMLBRTag + line + '\n')
        if tempPrintLine == True:
            print( line )

"""
Basic function to read config file in yaml format
Use this on host without python 3 or where yaml is not available

"""
def JAYamlLoad(fileName:str ):
    from collections import defaultdict
    import re
    yamlData = defaultdict(dict)
    paramNameAtDepth = {0: '', 1: '', 2: '', 3:'', 4: ''}
    leadingSpacesAtDepth = {0: 0, 1: None, 2: None, 3: None, 4: None}
    prevLeadingSpaces = 0
    currentDepth = 0
    currentDepthKeyValuePairs = defaultdict(dict)

    try:
        with open(fileName, "r") as file:
            depth = 1

            while True:
                tempLine =  file.readline()
                if not tempLine:
                    break
                # SKIP comment line
                if re.match(r'\s*#', tempLine):
                    continue

                tempLine = tempLine.rstrip("\n")
                if re.match("---", tempLine) :
                    continue
                if len(tempLine) == 0:
                    continue
                # remove leading and trailing spaces, newline
                lstripLine = tempLine.lstrip()
                if len(lstripLine) == 0:
                    continue

                ## separate param name and value, split to two parts, the value itself may have ':'
                params = lstripLine.split(':', 1)
                ## remove leading space from value field
                params[1] = params[1].lstrip()

                # based on leading spaces, determine depth
                leadingSpaces = len(tempLine)-len(lstripLine)
                if leadingSpaces == prevLeadingSpaces:

                    if leadingSpaces == 0:
                        if params[1] == None or len(params[1]) == 0 :
                            # if value does not exist, this is the start of parent/child definition
                            paramNameAtDepth[currentDepth+1] = params[0]

                        else:
                            # top layer, assign the key, value pair as is to yamlData
                            yamlData[params[0]] = params[1]
                    else:
                        # store key, value pair with current depth dictionary
                        currentDepthKeyValuePairs[params[0]] = params[1]

                    leadingSpacesAtDepth[currentDepth+1] = leadingSpaces

                elif leadingSpaces < prevLeadingSpaces:
                    # store key, value pair of prev depth 
                    for key, values in currentDepthKeyValuePairs.items():
                        if currentDepth == 1:
                            if paramNameAtDepth[1] not in yamlData.keys() :
                                yamlData[ paramNameAtDepth[1]] = {}
                            
                            yamlData[ paramNameAtDepth[1] ][key] = values

                        elif currentDepth == 2:
                            if paramNameAtDepth[1] not in yamlData.keys() :
                                yamlData[ paramNameAtDepth[1]] = {}
                            if paramNameAtDepth[2] not in yamlData[paramNameAtDepth[1]].keys() :
                                yamlData[ paramNameAtDepth[1]][paramNameAtDepth[2]] = {}

                            yamlData[paramNameAtDepth[1]][paramNameAtDepth[2]][key] = values
                        elif currentDepth == 3:
                            if paramNameAtDepth[1] not in yamlData.keys() :
                                yamlData[ paramNameAtDepth[1]] = {}
                            if paramNameAtDepth[2] not in yamlData[paramNameAtDepth[1]].keys() :
                                yamlData[ paramNameAtDepth[1]][paramNameAtDepth[2]] = {}
                            if paramNameAtDepth[3] not in yamlData[paramNameAtDepth[1]][paramNameAtDepth[2]].keys() :
                                yamlData[ paramNameAtDepth[1]][paramNameAtDepth[2]][paramNameAtDepth[3]] = {}
                            yamlData[paramNameAtDepth[1]][paramNameAtDepth[2]][paramNameAtDepth[3]][key] = values

                    currentDepthKeyValuePairs = defaultdict(dict)
                    
                    if leadingSpacesAtDepth[currentDepth-1] == leadingSpaces:
                        currentDepth -= 1
                    elif leadingSpacesAtDepth[currentDepth-2] == leadingSpaces:
                        currentDepth -= 2
                    elif leadingSpacesAtDepth[currentDepth-3] == leadingSpaces:
                        currentDepth -= 3
                    prevLeadingSpaces = leadingSpaces

                    if params[1] == None or len(params[1]) == 0 :
                        # if value does not exist, this is the start of parent/child definition
                        paramNameAtDepth[currentDepth+1] = params[0]
                elif leadingSpaces > prevLeadingSpaces:
                    leadingSpacesAtDepth[currentDepth+1] = leadingSpaces
                    currentDepth += 1
                    prevLeadingSpaces = leadingSpaces
                    if params[1] == None or len(params[1]) == 0 :
                        # if value does not exist, this is the start of parent/child definition
                        paramNameAtDepth[currentDepth+1] = params[0]
                    else:
                        # save current key, value 
                        currentDepthKeyValuePairs[params[0]] = params[1]

            for key, values in currentDepthKeyValuePairs.items():
                if currentDepth == 1:
                    if paramNameAtDepth[1] not in yamlData.keys() :
                        yamlData[ paramNameAtDepth[1]] = {}
                            
                    yamlData[ paramNameAtDepth[1] ][key] = values

                elif currentDepth == 2:
                    if paramNameAtDepth[1] not in yamlData.keys() :
                        yamlData[ paramNameAtDepth[1]] = {}
                    if paramNameAtDepth[2] not in yamlData[paramNameAtDepth[1]].keys() :
                        yamlData[ paramNameAtDepth[1]][paramNameAtDepth[2]] = {}

                    yamlData[paramNameAtDepth[1]][paramNameAtDepth[2]][key] = values
                elif currentDepth == 3:
                    if paramNameAtDepth[1] not in yamlData.keys() :
                        yamlData[ paramNameAtDepth[1]] = {}
                    if paramNameAtDepth[2] not in yamlData[paramNameAtDepth[1]].keys() :
                        yamlData[ paramNameAtDepth[1]][paramNameAtDepth[2]] = {}
                    if paramNameAtDepth[3] not in yamlData[paramNameAtDepth[1]][paramNameAtDepth[2]].keys() :
                        yamlData[ paramNameAtDepth[1]][paramNameAtDepth[2]][paramNameAtDepth[3]] = {}
                    yamlData[paramNameAtDepth[1]][paramNameAtDepth[2]][paramNameAtDepth[3]][key] = values
            file.close()
            return yamlData

    except OSError as err:
        print('ERROR Can not read file:|' + fileName + '|, ' + "OS error: {0}".format(err) + '\n')
        return yamlData

def JAFindModifiedFiles(fileName:str, sinceTimeInSec:int, debugLevel:int, thisHostName:str):
    """
        This function returns file names in a directory that are modified since given GMT time in seconds
        if sinceTimeInSec is 0, latest file is picked up regardless of modified time
        Can be used instead of find command 

        if sinceTimeInSec is +ve number, files modified before that time are returned
        if sinceTimeInSec is -ve number, files modified since that time are returned

    """
    head_tail = os.path.split( fileName )
    # if no path specified, use ./ (current working directory)
    if head_tail[0] == '' or head_tail[0] == None:
        myDirPath = './'
    else:
        myDirPath = head_tail[0]

    fileNameWithoutPath = head_tail[1]

    # if fileName has variable {HOSTNAME}, replace that with current short hostname
    if re.search(r'{HOSTNAME}', fileNameWithoutPath) != None:
        fileNameWithoutPath = re.sub(r'{HOSTNAME}', thisHostName, fileNameWithoutPath)

    if debugLevel > 1 :
        print('DEBUG-2 JAFileFilesModified() filePath:{0}, fileName: {1}'.format( myDirPath, fileNameWithoutPath))

    import fnmatch
    import glob

    if sinceTimeInSec > 0:
        findFilesOlderThanGivenTime = True
    else:
        # make the number +ve for comparison later
        sinceTimeInSec = abs(sinceTimeInSec)
        findFilesOlderThanGivenTime = False

    fileNames = {}

    try:
        # get all file names in desired directory with matching file spec
        for file in glob.glob(myDirPath + "/" + fileNameWithoutPath):
        
            if debugLevel > 2 :
                print('DEBUG-3 JAFileFilesModified() fileName: {0}, match to desired fileNamePattern: {1}'.format(
                    file, fileNameWithoutPath) )

            # now check the file modified time, if greater than or equal to passed time, save the file name
            fileModifiedTime = os.path.getmtime ( file )
            if findFilesOlderThanGivenTime == True:
                if fileModifiedTime < sinceTimeInSec :
                    fileNames[ fileModifiedTime ] = file 
                    if debugLevel > 2 :
                        print('DEBUG-3 JAFileFilesModified() fileName: {0}, modified time: {1}, later than desired time: {2}'.format( file, fileModifiedTime, sinceTimeInSec) )

            else:
                if fileModifiedTime >= sinceTimeInSec :
                    fileNames[ fileModifiedTime ] = file 
                    if debugLevel > 2 :
                        print('DEBUG-3 JAFileFilesModified() fileName: {0}, modified time: {1}, later than desired time: {2}'.format( file, fileModifiedTime, sinceTimeInSec) )
    except OSError as err:
        errorMsg = "ERROR JAFileFilesModified() Not able to find files in fileName: {0}, error:{1}".format( 
            myDirPath, err)
        print( errorMsg)
        
    sortedFileNames = []
    for fileModifiedTime, fileName in sorted ( fileNames.items() ):
        sortedFileNames.append( fileName )

    if debugLevel > 0 :
        print('DEBUG-1 JAFileFilesModified() modified files in:{0}, since gmtTimeInSec:{1}, fileNames:{2}'.format( 
            fileName, sinceTimeInSec, sortedFileNames) )

    # if sinceTimeInSec is zero, pick up latest file only
    if sinceTimeInSec == 0:
        if len(sortedFileNames) > 0:
            # return single file as list
            return [sortedFileNames[-1]]
    
    return sortedFileNames

def JAGetOSInfo(pythonVersion, debugLevel:int):
    """
    Returns 
        OSType like Linux, Windows
        OSName like rhel for Redhat Linux, ubuntu for Ubuntu, Windows for Windows
        OSVersion like
            7 (for RH7.x), 8 (for RH8.x) for Redhat release
            20 (for Ubuntu)
            10, 11 for Windows

    """
    OSType = platform.system()
    if OSType == 'Linux' :
        try:
            with open("/etc/os-release", "r") as file:
                while True:
                    tempLine = file.readline()
                    if not tempLine:
                        break
                    if len(tempLine)<5:
                        continue
                    tempLine = re.sub('\n$','',tempLine)

                    if re.match(r'ID=', tempLine) != None:
                        dummy, OSName = re.split(r'ID=', tempLine)

                        # remove double quote around the value
                        OSName = re.sub('"','',OSName)

                    elif re.match(r'VERSION_ID',tempLine) != None:
                        dummy,tempOSVersion = re.split(r'VERSION_ID=', tempLine)
                file.close()
        except:
            try:
                with open("/etc/system-release", "r") as file:
                    while True:
                        tempLine = file.readline()
                        if not tempLine:
                            break
                        if len(tempLine)<5:
                            continue
                        tempLine = re.sub('\n$','',tempLine)
                        # line is of the form: red hat enterprise linux server release 6.8 (santiago)
                        #                                                             \d.\d <-- OSVersion
                        myResults = re.search( r'Red Hat (.*) (\d.\d) (.*)', tempLine)
                        if myResults != None:
                            tempOSVersion = myResults.group(2)
                            OSName = 'rhel'

            except:
                try:
                    with open("/etc/redhat-release", "r") as file:
                        while True:
                            tempLine = file.readline()
                            if not tempLine:
                                break
                            if len(tempLine)<5:
                                continue
                            tempLine = re.sub('\n$','',tempLine)
                            # line is of the form: red hat enterprise linux server release 6.8 (santiago)
                            #                                                             \d.\d <-- OSVersion
                            myResults = re.search( r'Red Hat (.*) (\d.\d) (.*)', tempLine)
                            if myResults != None:
                                tempOSVersion = myResults.group(2)
                                OSName = 'rhel'
                except:
                    tempOSVersion = ''
                    OSName = ''
                    print("ERROR JAGetOSInfo() Can't read file: /etc/os-release or /etc/system-release")
                    tempOSReease = ''

    elif OSType == 'Windows' :
        if pythonVersion >= (3,7) :
            tempOSVersion = platform.version()
        OSName = OSType

    # extract major release id from string like x.y.z
    # windows 10.0.19042
    # RH7.x - 3.10.z, RH8.x - 4.18.z
    # Ubuntu - 5.10.z
    OSVersion = re.search(r'\d+', tempOSVersion).group()
    if debugLevel > 0 :
        print("DEBUG-1 JAGetOSInfo() OSType:{0}, OSName:{1}, OSVersion:{2}".format(OSType, OSName, OSVersion) )

    return OSType, OSName, OSVersion
     

def JAGetOSType():
    """
        Returns values like Linux, Windows
    """
    return platform.system()

def JAWriteCPUUsageHistory( CPUUsage:int, logFileName=None, debugLevel=0):
    """
    Write CPU usage data to given file name
    Keep 10 sample values

    First line has the average value of max 10 samples 
    Rest of the lines have values of 10 samples, current CPUUsage passed as last line

    Returns True up on success, False if file could not be opened
    """
    historyCPUUsage, average = JAReadCPUUsageHistory() 
    if historyCPUUsage == None:
        # first time, start with empty list
        historyCPUUsage = []
    else:
        if len( historyCPUUsage ) == 10:
            # history has 10 samples, drop the oldest sample
            historyCPUUsage.pop(0)

    # append current CPU Usage to the list
    historyCPUUsage.append( float(CPUUsage) )
    average = sum(historyCPUUsage) / len( historyCPUUsage)

    try:
        with open( JACPUUsageFileName, "w") as file:
            file.write( '{:.2f}\n'.format( average) )
            for value in historyCPUUsage:
                file.write('{:.2f}\n'.format( value ))
            file.close()
            return True

    except OSError as err:
        errorMsg = 'ERROR - JAWriteCPUUsageStats() Can not open file: {0} to save CPU usage info, error:{1}\n'.format(
             JACPUUsageFileName, err)
        print(errorMsg)
        if logFileName != None:
            LogMsg( errorMsg, logFileName, True)
        return False

def JAReadCPUUsageHistory( logFileName=None, debugLevel=0):
    """
    Read CPU usage data from a file
    Return CPUUsage values in list form, return avarge value separtely
    Return None if file could not be read

    """
    try:
        if os.path.exists( JACPUUsageFileName ) == False:
            return [0], 0
        with open( JACPUUsageFileName, "r") as file:
            tempLine = file.readline().strip()
            if len(tempLine) > 0 :
                average = float( tempLine )
                CPUUsage = []
                while True:
                    tempLine = file.readline()
                    if not tempLine:
                        break
                    if tempLine != '\n':
                        CPUUsage.append( float( tempLine.strip() ) )
                file.close()
                return CPUUsage, average 
            else:
                return [0], 0
    except OSError as err:
        errorMsg = 'ERROR - JAReadCPUUsageStats() Can not open file: {0} to read CPU usage info, error:{1}\n'.format( 
            JACPUUsageFileName, err)
        print(errorMsg)
        if logFileName != None:
            LogMsg( errorMsg, logFileName, True)
        return [0], 0

def JAGetAverageCPUUsage( ):
    tempCPUUsage, average = JAReadCPUUsageHistory()
    return average

def JAWriteTimeStamp(fileName:str, currentTime=None):
    """
    This function writes current time to given filename
    If currentTime is not passed, current time is taken and written to the file
    """
    import time
    if currentTime == None:
        currentTime = time.time()
    
    try:
        with open (fileName, "w") as file:
            file.write( '{0:.2f}\n'.format( currentTime) )
            file.close()
            return True

    except OSError as err:
        errorMsg = 'ERROR - JAWriteTimeStamp() Can not open file: {0} to save current time, error:{1}\n'.format( 
            fileName, err)
        print(errorMsg)
        return False

def JAReadTimeStamp( fileName:str):
    """
    This function reads the time stamp from a given file
    """
    prevTime = 0
    try:
        if os.path.exists(fileName) == False:
            return 0
        with open (fileName, "r") as file:
            tempLine = file.readline().strip()
            if len(tempLine) > 0:
                prevTime = float( tempLine )
            file.close()
            return prevTime

    except OSError as err:
        errorMsg = 'INFO JAReadTimeStamp() Can not open file: {0} to save current time, error:{1}\n'.format( 
            fileName, err)
        print(errorMsg)
        return 0

def JAGetUptime(OSType:str):
    """
    returns uptime in number of seconds
    if can't be computed, returns 0
    """
    if OSType == 'Linux':
        with open('/proc/uptime', 'r') as f:
            uptime_seconds = float(f.readline().split()[0])
    elif OSType == 'Windows':
        uptime_seconds = 0
    else:
         uptime_seconds = 0
    return uptime_seconds

def JAExecuteCommand(command:str, debugLevel:int):
    """
    Execute given command

    Return status
        returnResult - True on success, False on failure
        returnOutput - command execution result
        errorMsg - message indicating the success or failure condition

    """
    import subprocess
    returnResult = False
    returnOutput = ''

    if debugLevel > 2:
        print("DEBUG-3 JAExecuteCommand() command:{0}".format(command))

    try:
        result = subprocess.run( command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        returnOutput = result.stdout.decode('utf-8').split('\n')
        errorMsg = 'INFO JAExecuteCommand() result of executing the command:{0}\n{1}'.format(command,returnOutput)
        returnResult = True
    except (subprocess.CalledProcessError) as err :
        errorMsg = "ERROR JAExecuteCommand() failed to execute command:{0}".format(command, err)
      
    except ( FileNotFoundError ) as err:
        errorMsg = "INFO JAExecuteCommand() File not found, while executing the command:{0}".format(command, err)
        
    except Exception as err:
        errorMsg = "ERROR JAExecuteCommand() failed to execute command:{0}".format(command, err)

    if debugLevel > 0 :
        print("DEBUG-1 JAExecuteCommand() command output:{0}, errorMsg:{1}".format(returnOutput, errorMsg))
    returnOutput = str(returnOutput)
    return returnResult, returnOutput, errorMsg

def JAGetProfile(fileName:str, paramName:str):
    """
    Searches for the paramName in given profile file having the values in the format
        paramName: paramValue 
    
    Parameters passed:
        fileName - profile file name
        paramName - parameter name to search

    Returns
       returnStatus - True if value found, else False
       paramValue - value if value found, else None

    """
    returnStatus = False
    paramValue = None
    if os.path.exists(fileName) :
        with open(fileName, "r") as file:
            while True:
                line = file.readline()
                if not line:
                    break
                line = line.strip()
                fieldParts = line.split(':')
                if len(fieldParts) > 1:
                    if fieldParts[0] == paramName:
                        paramValue = fieldParts[1]
                        paramValue = paramValue.lstrip()
                        returnStatus = True
                        break
            file.close()
    else:
        print("ERROR JAGetProfile() Profile file:{0} is not present".format(fileName))

    return returnStatus, paramValue

def JASetProfile(fileName:str, paramName:str, paramValue:str):
    """
    Searches for the paramName in given profile file having the values in the format
        paramName: paramValue 
    Replaces the maching line with new paramValue passed

    Parameters passed:
        fileName - profile file name
        paramName - parameter name to search
        paramValue - parameter value

    Returns
       returnStatus - True if value found, else False
       
    """
    returnStatus = True
    fileContents = ''
    lineFound = False
    replaceLine = "{0}:{1}\n".format(paramName,paramValue)
    if os.path.exists(fileName) :
        with open(fileName, "r") as file:
            while True:
                line = file.readline()
                if not line:
                    break
                fieldParts = line.split(':')
                if len(fieldParts) > 1:
                    if fieldParts[0] == paramName:
                        ### make new line with new param value
                        fileContents += replaceLine
                        lineFound = True
                    else:
                        ### store original line as is
                        fileContents += (line + '\n')
            if lineFound == False:
                ### add new line
                fileContents += replaceLine
            file.close()
        
        with open(fileName, "w") as file:
            file.write(fileContents)
            file.close()

    else:
        ### write new file
        with open(fileName, "w") as file:
            file.write(replaceLine)
            file.close()

    return returnStatus

def JADeriveHistoryFileName( subsystem:str, operation:str, defaultParameters):
    historyFileName = "{0}/JAAudit.{1}.{2}.PrevStartTime".format(defaultParameters['LogFilePath'], operation,subsystem)
    return historyFileName

def JAUpdateHistoryFileName(subsystem:str, operation:str, defaultParameters ):
    """
    Write current time to history file indicating last time when this operation was performed
    """
    historyFileName = JADeriveHistoryFileName(subsystem, operation, defaultParameters )
    with open(historyFileName,"w") as file:
        file.write(UTCDateTime())
    
    return True

def JAIsItTimeToRunOperation(currentTime:int, subsystem:str, operation:str, defaultParameters, debugLevel:int):
    """
    This function derives the history filename baesd on subsystem and operation 
    Gets the last modified time of that history filename.
    If the time difference between modified time and current time is greater than
        the operation window defined in defaultParameters[],
        return True
    else
        return False

    If operation window is not defined for the current operation or it is zero (disabled), 
        return False

    Parameters passed:
        currentTime, subsystem, operation, defaultParameters, debugLevel

    Returned values:
        True - if it is time to run the operation
        False - not time yet

    """

    returnStatus = False

    ### derive history file name using current operation
    historyFileName = JADeriveHistoryFileName(subsystem, operation, defaultParameters)
    import os.path
    if os.path.exists(historyFileName) == True:
        ### history file exists, checks it's modified time, if delta time is greater than defined period,
        ###   it is time to run the operation
        modifiedTimeStamp = os.path.getmtime(historyFileName)
        deltaTime = currentTime - modifiedTimeStamp

        if operation in defaultParameters:
            if defaultParameters[operation] > 0:
                if  deltaTime > defaultParameters[operation]:
                    returnStatus = True
    else:
        ### history file not present, no indication of this operation ran before, 
        ###     it is time to run the operation
        returnStatus = True

    return returnStatus

def JADeriveConfigFileName( pathName1:str, pathName2:str, subsystem:str, baseConfigFileName:str, version:str, debugLevel:int ):
    """
    Prepare operation specific configuration file
    <path>/<subsystem><baseConfigFileName>[.<version>].<fileType>
    
    if subsystem passed is empty, 'App' subsystem is used by default
    if version is not empty, it is added to the filename
    
    """

    returnStatus = True
    errorMsg = ''
    
    if debugLevel > 1:
        print("DEBUG-2 JADeriveConfigFileName() pathName1:{0}, pathName2:{1}, subsystem:{2}, baseConfigFileName:{3}, version:{4}".format(
                pathName1, pathName2, subsystem, baseConfigFileName, version))

    # remove file type from baseConfigFileName
    baseConfigFileNameWithoutFileType, fileType = baseConfigFileName.split('.')

    ### use App subsystem as default 
    if subsystem == '' or subsystem == None:
        subsystem = 'App'
    
    ### first try under pathName1
    tempConfigFileName = '{0}/{1}{2}.{3}.{4}'.format(
        pathName1, subsystem, baseConfigFileNameWithoutFileType, version, fileType)
    if os.path.exists( tempConfigFileName ) == False:
        tempConfigFileName = '{0}/{1}{2}.{3}'.format(
            pathName1, subsystem, baseConfigFileNameWithoutFileType, fileType)
        if os.path.exists( tempConfigFileName ) == False:
            ### Now try under pathName2
            tempConfigFileName = '{0}/{1}{2}.{3}.{4}'.format(
                pathName2, subsystem, baseConfigFileNameWithoutFileType, version, fileType)
            if os.path.exists( tempConfigFileName ) == False:
                tempConfigFileName = '{0}/{1}{2}.{3}'.format(
                    pathName2, subsystem, baseConfigFileNameWithoutFileType, fileType)
                if os.path.exists( tempConfigFileName ) == False:
                    ### file does exist, return error
                    errorMsg = "ERROR JADeriveConfigFileName() config file:{0} not present for path1:{1}, path2:{2}, subsystem:{3}, AppConfig:{4}, version:{5}".format(
                        tempConfigFileName, pathName1, pathName2, subsystem, baseConfigFileName, version)
                    returnStatus = False
                    tempConfigFileName = ''

    if debugLevel > 1:
        print("DEBUG-2 JADeriveConfigFileName() derived config file:{0}".format(tempConfigFileName))
    return returnStatus, tempConfigFileName, errorMsg

def JACheckConnectivity( 
    hostName:str, port:str, protocol:str, command:str, tcpOptions:str, udpOptions:str, 
    OSType:str, OSName:str, OSVersion:str, debugLevel:int):
    """
    This function executes given command to check connectivity to local or remote host
    For TCP protocol, uses tcpOptions
    For UDP protocol, uses udpOptions

    Parameters passed:
        hostName, port, protocol, command, tcpOptions, udpOptions, OSType, OSName, OSVersion, debugLevel

    Returns the command output as is
        returnStatus - True when command executed successfully
        returnOutput - command output
        errorMsg - error message when commad execution fails
    """
    returnStatus = True
    errorMsg = ''

    if protocol == "TCP":
        options = tcpOptions
    else:
        options = udpOptions

    if OSType == "Windows":
        finalCommand = "{0} -ComputerName {1} -Port {2}".format(command, hostName, port)
    elif OSType == 'Linux':
        ###
        finalCommand = "{0} {1} {2} {3}".format(command, options,  hostName, port)
    elif OSType == 'SunOS':
        finalCommand = "{0} {1} {2} {3}".format(command, options,  hostName, port)
    returnStatus, returnOutput, errorMsg = JAExecuteCommand(finalCommand, debugLevel)
    
    if OSType == 'Windows':
        ### translate returnOutput to Linux output format
        if re.findall(r'TcpTestSucceeded(.+):(.+)True', returnOutput, re.MULTILINE):
            returnOutput = "succeeded"
        elif (re.findall(r'RemoteAddress(.+):\$', returnOutput, re.MULTILINE) and 
            re.findall(r'PingSucceeded(.+):(.+)False', returnOutput, re.MULTILINE) ):
            returnOutput = "Could not resolve hostname"
        elif (re.findall(r'TcpTestSucceeded(.+):(.+)False', returnOutput, re.MULTILINE) and 
            re.findall(r'PingSucceeded(.+):(.+)True', returnOutput, re.MULTILINE) ):
            returnOutput = "Connection timed out"
    return returnStatus, returnOutput, errorMsg


def JACheckConnectivityToHosts( 
    defaultParameters, connectivitySpec,
    OSType:str, OSName:str, OSVersion:str, printResults:int, debugLevel:int): 

    """
    Checks connectivity to the hosts given in connectivitySpec
    If CommandConnCheck is defined in JAEnvironment.yml for the current host, it will be used
    Else, it will use default command based on OSType of current host.

    Parameters passed
        defaultParameters, connectivitySpec, OSType, OSName, OSVersion, printResults, debugLevel

    Returned values
        returnStatus, passCount, failureCount, detailedResults

    """
    returnStatus = True
    failureCount = passCount = 0
    detailedResults = ''

    if OSType == 'Linux':
        if OSVersion < 6:
            tcpOptions = "-vz -w 8"
            udpOptions = "-u"
        else:
            tcpOptions = "-i 1 -v -w 8"
            udpOptions = "-u"
    else:
        tcpOptions = udpOptions = ''

    connectionErrors = "Connection timed out|timed out: Operation now in progress|No route to host"
    hostNameErrors = "host lookup failed|Could not resolve hostname|Name or service not known"
    connectivityPassed = "succeeded|Connected to| open"
    connectivityUnknown = "Connection refused"

    if 'CommandConnCheck' in defaultParameters:
        command = defaultParameters['CommandConnCheck']
    else:
        if OSType == 'Linux':
            # connection check command not defined, use nc by default
            command = 'nc'
        elif OSType == 'windows':
            command = 'Test-NetConnection'
        elif OSType == 'SunOS':
            command = 'telnet'
        if debugLevel > 0:
            print( 'DEBUG-1 JACheckConnectivityToHosts() CommandConnCheck parameter not defined in environment spec, using default command:{0}, tcpOptions:{1}, udpOptions:{2}'.format(
                    command, tcpOptions, udpOptions))

    for hostSpec in connectivitySpec:
        hostName = hostSpec[0]
        protocol = hostSpec[1]
        port = hostSpec[2]
        tempReturnStatus,returnOutput, errorMsg = JACheckConnectivity( 
            hostName, port, protocol, command, tcpOptions, udpOptions, OSType, OSName, OSVersion, debugLevel)
        if tempReturnStatus == False:
            failureCount += 1
            print("ERROR JACheckConnectivityToHosts() Error executing command:{0}, error msg:{1}".format(
                    command,  errorMsg  ))
        else:
            # parse the returnOutput or command output
            if re.match(connectivityPassed, returnOutput):
                passCount += 1
            elif re.match(connectivityUnknown, returnOutput):
                failureCount += 1
            elif re.match(connectionErrors, returnOutput):
                failureCount += 1
            elif re.match(hostNameErrors, returnOutput):
                failureCount += 1
    if failureCount > 0:
        returnStatus = False    
    return returnStatus, passCount, failureCount, detailedResults
    

    