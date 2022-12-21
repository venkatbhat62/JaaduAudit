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
    """
    JAGlobalLib.JAConvertStringTimeToTimeInMicrosec( dateTimeString, format:str)

    Converts date time string to time in microsec using the format string. 
    If successful, returns time in microseconds
    Else, returns 0

    """
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
    """
    JAGlobalLib.JAParseArgs(argsPassed)

    Parses the command level arguments in sys.argv[] to the list argsPassed
    Returns argument count

    """
    args = sys.argv[1:]
    argc = len(args)
    for index in range(0,argc,2):
        argument = args[index]
        argsPassed[argument] = args[index+1]
            
    return argc

def JAIsYamlModulePresent():
    """
    JAGlobalLib.JAIsYamlModulePresent()

    This function checks whether yaml module is present.
    If present, returns True
    Else, returns False

    """
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
    """
    JAGlobalLib.JAGetTime( deltaSeconds:int )

    This function takes current time, subtracts the given time in seconds and 
       returns the resulting time in HH:MM:SS format.

    """
    tempTime = datetime.datetime.now()
    deltaTime = datetime.timedelta(seconds=deltaSeconds)
    newTime = tempTime - deltaTime
    return newTime.strftime("%H:%M:%S")

def JAGetDateTime( deltaSeconds:int ):
    """
    JAGlobalLib.JAGetDateTime( deltaSeconds:int )
    This function takes current time, subtracts the given time in seconds and 
       returns the resulting time in YYYY-MM-DDTHH:MM:SS.mmmmmmZ format.

    """
    tempTime = datetime.datetime.now()
    deltaTime = datetime.timedelta(seconds=deltaSeconds)
    newTime = tempTime - deltaTime
    return newTime.strftime("%Y-%m-%dT%H:%M:%S.%f%Z")

def JAGetDayOfMonth( deltaSeconds:int ):
    """
    JAGlobalLib.JAGetDayOfMonth( deltaSeconds:int )
    This function takes current time, subtracts the given time in seconds and 
        returns day of the month

    """
    tempTime = datetime.datetime.now()
    deltaTime = datetime.timedelta(seconds=deltaSeconds)
    newTime = tempTime - deltaTime
    newTimeString = newTime.strftime("%d")
    return newTimeString 

def LogMsg(logMsg:str, fileName:str, appendDate=True, prefixTimeStamp=True):
    """"
    JAGlobalLib.LogMsg(logMsg:str, fileName:str, appendDate=True, prefixTimeStamp=True)

    Logs the given message to a log file in append mode, 
      if appendDate is True, file name ending with YYYYMMDD is assumed.
      If prefixTimeStamp is True, current dateTime string is prefixed to the log line before logging

    """
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

def LogLine(myLines, tempPrintLine, myColors, colorIndex:int, outputFile:str, HTMLBRTag:str,  diffLine=False, OSType='Linux'):
    """
    JAGlobalLib.LogLine(myLines, tempPrintLine, myColors, colorIndex:int, outputFile:str, HTMLBRTag:str,  diffLine=False, OSType='Linux')

    This function logs the lines passed in myLines to terminal with colors based on first word seen in first line
    If tempPrintLine passed is True, formatted line will be printed to the terminal
    While printing first line, current timestamp is printed as first two words

    Formatting applied to all lines when first word is
    ^ERROR |^ERROR, - red
    ^DIFF - blue
    ^PASS |^ PASS - gren
    ^INFO - no color
    ^FAIL |^WARN - yellow

    If subsequent lines start with 
    < - printed in blue color
    > - printed in cyan color
    These lines are considerd as output of diff command

    Parameters passed:
        myLines - line to print
        tempPrintLine - True or False, if True, formatted line will be printed to the terminal

    """

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
        elif re.match('^WARN |^FAIL ', line) :
            line = myColors['yellow'][colorIndex] + currentTime + line + myColors['clear'][colorIndex]   
        if outputFile != None:
            outputFile.write( HTMLBRTag + line + '\n')
        if tempPrintLine == True:
            print( line )

def JAYamlLoad(fileName:str ):
    """
    JAGlobalLib.JAYamlLoad(fileName:str )

    Basic function to read config file in yaml format
    Use this on host without python 3 or where yaml is not available

    Upon successful read, returns the yaml data in dictionary form

    """

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
    JAGlobalLib.JAFindModifiedFiles(fileName:str, sinceTimeInSec:int, debugLevel:int, thisHostName:str)

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
    JAGlobalLib.JAGetOSInfo(pythonVersion, debugLevel:int)

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
    JAGlobalLib.JAGetOSType()
        Returns values like Linux, Windows
    """
    return platform.system()

def JAWriteCPUUsageHistory( CPUUsage:int, logFileName=None, debugLevel=0):
    """
    JAGlobalLib.JAWriteCPUUsageHistory( CPUUsage:int, logFileName=None, debugLevel=0)

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
    JAGlobalLib.JAReadCPUUsageHistory( logFileName=None, debugLevel=0)

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
    """
    JAGlobalLib.JAGetAverageCPUUsage( )

    Return average cpu usage.

    """
    tempCPUUsage, average = JAReadCPUUsageHistory()
    return average

def JAWriteTimeStamp(fileName:str, currentTime=None):
    """
    JAGlobalLib.JAWriteTimeStamp(fileName:str, currentTime=None)

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
    JAGlobalLib.JAReadTimeStamp( fileName:str)

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
    JAGlobalLib.JAGetUptime(OSType:str)

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

def JAExecuteCommand(shell:str, command:str, debugLevel:int, OSType="Linux", timeoutPassed=30):
    """
    JAGlobalLib.JAExecuteCommand(shell:str, command:str, debugLevel:int, OSType="Linux", timeoutPassed=30)

    Execute given command
      If OSType is windows, replace \r with \n, remove [...], 
         normalize the output to standard multiline string similar to output from Unix host

    Return status
        returnResult - True on success, False on failure
        returnOutput - command execution result
        errorMsg - message indicating the success or failure condition

    """
    import subprocess
    returnResult = False
    returnOutput = ''

    if debugLevel > 2:
        print("DEBUG-3 JAExecuteCommand() shell:{0}, command:|{1}|".format(shell, command))

    try:
        if OSType == 'Windows':
            result = subprocess.run( shell + " " + command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,timeout=timeoutPassed)

        else:
            ### separate words of given shell command to list
            shell = re.split(' ', shell)
            shell.append( command )
            result = subprocess.run( args=shell, stdout=subprocess.PIPE, stderr=subprocess.PIPE,timeout=timeoutPassed)

        if result.returncode == 0:
            if OSType == 'Windows':
                ### takeout \r
                returnOutput = result.stdout.decode('utf-8').replace('\r\n', '\n')
                returnOutput = returnOutput.rstrip("\n")
                returnOutput = returnOutput.split('\n')

            else:
                returnOutput = result.stdout.decode('utf-8').rstrip("\n")
                returnOutput = returnOutput.split('\n')
            errorMsg = 'INFO JAExecuteCommand() result of executing the command:|{0} {1}|, result:\n{2}'.format(shell, command,returnOutput)
            returnResult = True
        else:
            ### execution failed
            if OSType == 'Windows':
                returnOutput = result.stdout.decode('utf-8').split('\r')
            else:
                returnOutput = result.stdout.decode('utf-8').split('\n')
            errorMsg = 'ERROR JAExecuteCommand() failed to execute command:|{0} {1}|, error:\n{2}'.format(shell, command,returnOutput)
            returnResult = False

    except (subprocess.CalledProcessError) as err :
        errorMsg = "ERROR JAExecuteCommand() failed to execute command:|{0} {1}|, called process error:|{2}|".format(shell, command, err)
      
    except ( FileNotFoundError ) as err:
        errorMsg = "INFO JAExecuteCommand() File not found, while executing the command:|{0} {1}|, error:|{2}|".format(shell, command, err)
        
    except Exception as err:
        errorMsg = "ERROR JAExecuteCommand() failed to execute command:|{0} {1}|, exception:|{2}|".format(shell, command, err)

    if debugLevel > 2 :
        print("DEBUG-3 JAExecuteCommand() command output:|{0}|, message:|{1}|".format(returnOutput, errorMsg))
    # returnOutput = str(returnOutput)
    return returnResult, returnOutput, errorMsg

def JAGetProfile(fileName:str, paramName:str):
    """
    JAGlobalLib.JAGetProfile(fileName:str, paramName:str)

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
    JAGlobalLib.JASetProfile(fileName:str, paramName:str, paramValue:str)

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
                        fileContents += (line )
            if lineFound == False:
                ### add new line
                fileContents += (replaceLine)
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
    """
    JAGlobalLib.JADeriveHistoryFileName( subsystem:str, operation:str, defaultParameters)

    """
    historyFileName = "{0}/JAAudit.{1}.{2}.PrevStartTime".format(defaultParameters['LogFilePath'], subsystem, operation)
    return historyFileName

def JAUpdateHistoryFileName(subsystem:str, operation:str, defaultParameters ):
    """
    JAGlobalLib.JAUpdateHistoryFileName(subsystem:str, operation:str, defaultParameters )

    Write current time to history file indicating last time when this operation was performed
    """
    historyFileName = JADeriveHistoryFileName(subsystem, operation, defaultParameters )
    with open(historyFileName,"w") as file:
        file.write(UTCDateTime())
    
    return True

def JAIsItTimeToRunOperation(currentTime:int, subsystem:str, operation:str, defaultParameters, debugLevel:int):
    """
    JAGlobalLib.JAIsItTimeToRunOperation(currentTime:int, subsystem:str, operation:str, defaultParameters, debugLevel:int)

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
        currentTime, subsystem, operation, defaultParameters, duration debugLevel

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

def JADeriveConfigFileName( pathName1:str, pathName2:str, baseConfigFileName:str, subsystem:str, operation:str, version:str, debugLevel:int ):
    """
    JAGlobalLib.JADeriveConfigFileName( pathName1:str, pathName2:str, baseConfigFileName:str, subsystem:str, operation:str, version:str, debugLevel:int )

    Prepare operation specific configuration file
    <path>/<baseConfigFileName>.<subsystem>.<operation>.[.<version>].<fileType>
    
    if subsystem passed is empty, 'Apps' subsystem is used by default
    if version is not empty, it is added to the filename
    
    """

    returnStatus = False
    errorMsg = ''
    
    if debugLevel > 1:
        print("DEBUG-2 JADeriveConfigFileName() pathName1:|{0}|, pathName2:|{1}|, baseConfigFileName:|{2}|, subsystem:|{3}|, operation:|{4}|, version:|{5}|".format(
                pathName1, pathName2, baseConfigFileName, subsystem, operation, version))

    # remove file type from baseConfigFileName
    baseConfigFileNameWithoutFileType, fileType = baseConfigFileName.split('.')

    ### use Apps subsystem as default 
    if subsystem == '' or subsystem == None:
        subsystem = 'Apps'
    
    ### first try with version, if version is passed
    if version != '':
        ### first try under path1
        tempConfigFileName = '{0}/{1}.{2}.{3}.{4}.{5}'.format(
            pathName1, baseConfigFileNameWithoutFileType, subsystem, operation, version, fileType)
        if os.path.exists( tempConfigFileName ) == False:
            ### Now try under pathName2
            tempConfigFileName = '{0}/{1}.{2}.{3}.{4}.{5}'.format(
                pathName2, baseConfigFileNameWithoutFileType, subsystem, operation, version, fileType)
            if os.path.exists( tempConfigFileName ) == False:
                returnStatus = False
            else:
                returnStatus = True
        else:
            returnStatus = True

    if returnStatus == False:
        ### try without the version string
        tempConfigFileName = '{0}/{1}.{2}.{3}.{4}'.format(
            pathName1, baseConfigFileNameWithoutFileType, subsystem, operation, fileType)
        if os.path.exists( tempConfigFileName ) == False:
            tempConfigFileName = '{0}/{1}.{2}.{3}.{4}'.format(
                pathName2, baseConfigFileNameWithoutFileType, subsystem, operation, fileType)
            if os.path.exists( tempConfigFileName ) == False:
                ### file does exist, return error
                errorMsg = "ERROR JADeriveConfigFileName() config file:|{0}| not present in path1:|{1}|, path2:|{2}|, AppConfig:|{3}|, subsystem:|{4}|, operation:|{5}|, version:|{6}|".format(
                    tempConfigFileName, pathName1, pathName2,  baseConfigFileName, subsystem, operation, version)
                returnStatus = False
                tempConfigFileName = ''
            else:
                returnStatus = True
        else:
            returnStatus = True

    if debugLevel > 1:
        print("DEBUG-2 JADeriveConfigFileName() derived config file:|{0}|".format(tempConfigFileName))
    return returnStatus, tempConfigFileName, errorMsg

def JACheckConnectivity( 
    hostName:str, port:str, protocol:str, command:str, tcpOptions:str, udpOptions:str, 
    OSType:str, OSName:str, OSVersion:str, debugLevel:int, shell):
    """
    JAGlobalLib.JACheckConnectivity( 
    hostName:str, port:str, protocol:str, command:str, tcpOptions:str, udpOptions:str, 
    OSType:str, OSName:str, OSVersion:str, debugLevel:int)

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

    if re.search(r'curl', command):
        ### curl syntax is common for all OS
        finalCommand = "{0} {1}:{2}".format(command, hostName, port)
    elif OSType == "Windows":
        if re.search('Test-NetConnection', command):
            finalCommand = "{0} -ComputerName {1} -Port {2}".format(command, hostName, port)
        else:
            returnOutput = "ERROR JACheckConnectivity() Unknown command to do connectivity test"
            return False, returnOutput, ""

    elif OSType == 'Linux':
        ### let the error message also be put in stdout
        finalCommand = "{0} {1} {2} {3} 2>&1".format(command, options,  hostName, port)
    elif OSType == 'SunOS':
        ### let the error message also be put in stdout
        finalCommand = "{0} {1} {2} {3} 2>&1".format(command, options,  hostName, port)

    returnStatus, returnOutput, errorMsg = JAExecuteCommand(
        shell,
        finalCommand, debugLevel, OSType)
    
    if OSType == 'Windows':
        if len(returnOutput) > 5:
            if re.findall(r'TcpTestSucceeded(.+):(.+)True', returnOutput[6], re.MULTILINE):
                returnOutput = "succeeded"
                errorMsg = ''
            elif (re.findall(r'WARNING: Name resolution of(.*)failed', returnOutput[0], re.MULTILINE)):
                returnOutput = "Could not resolve hostname"
                errorMsg = ''
            elif (re.findall(r'TcpTestSucceeded(.+):(.+)False', returnOutput[6], re.MULTILINE) and 
                re.findall(r'PingSucceeded(.+):(.+)True', returnOutput, re.MULTILINE) ):
                returnOutput = "Connection timed out"
                errorMsg = ''
        elif re.findall(r'timed out after', errorMsg, re.MULTILINE):
            returnOutput = "Connection timed out"
            errorMsg = ''
            returnStatus = True
    elif OSType == 'Linux' or OSType == 'SunOS':
        ### result is a 0th index of the list
        returnOutput = returnOutput[0]

    return returnStatus, returnOutput, errorMsg


def JACheckConnectivityToHosts( 
    defaultParameters, connectivitySpec,
    OSType:str, OSName:str, OSVersion:str, printResults:int, debugLevel:int): 

    """
    JAGlobalLib.JACheckConnectivityToHosts( 
    defaultParameters, connectivitySpec,
    OSType:str, OSName:str, OSVersion:str, printResults:int, debugLevel:int)

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

    tcpOptions = udpOptions = ''

    connectionErrors = r'Connection timed out|timed out: Operation now in progress|No route to host'
    hostNameErrors = r'host lookup failed|Could not resolve hostname|Name or service not known'
    connectivityPassed = r'succeeded|Connected to| open'
    connectivityUnknown = r'Connection refused'

    if 'CommandConnCheck' in defaultParameters:
        command = defaultParameters['CommandConnCheck']
    else:
        if OSType == 'Linux':
            # connection check command not defined, use nc by default
            command = 'nc'
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
        if debugLevel > 0:
            print( 'DEBUG-1 JACheckConnectivityToHosts() CommandConnCheck parameter not defined in environment spec, using default command:{0}, tcpOptions:{1}, udpOptions:{2}'.format(
                    command, tcpOptions, udpOptions))

    for hostSpec in connectivitySpec:
        hostName = hostSpec[0]
        protocol = hostSpec[1]
        port = hostSpec[2]
        tempReturnStatus,returnOutput, errorMsg = JACheckConnectivity( 
            hostName, port, protocol, command, tcpOptions, udpOptions, OSType, OSName, OSVersion, debugLevel,
            defaultParameters['CommandShell'])
        if tempReturnStatus == False:
            failureCount += 1
            print("ERROR JACheckConnectivityToHosts() Error executing command:{0}, error msg:{1}".format(
                    command,  errorMsg  ))
        else:
            ### parse the returnOutput or command output in the list
            ### 1st item of the list has the result text
            if re.search(connectivityPassed, returnOutput):
                passCount += 1
            elif re.search(connectivityUnknown, returnOutput):
                failureCount += 1
            elif re.search(connectionErrors, returnOutput):
                failureCount += 1
            elif re.search(hostNameErrors, returnOutput):
                failureCount += 1
    if failureCount > 0:
        returnStatus = False    
    return returnStatus, passCount, failureCount, detailedResults
    
def JAGatherEnvironmentSpecs(storeCurrentValue, values, debugLevel, defaultParameters, integerParameters, floatParameters):
    """
    JAGlobalLib.JAGatherEnvironmentSpecs(storeCurrentValue, values, debugLevel, defaultParameters, integerParameters, floatParameters)

    Read environment spec for a given environment
    This function can be called recursively

    Parameters passed:
        storeCurrentValue - True or False. If True, even if previous value was present for that parameter name,
                new value will be stored in defaultParameters{}
        values - parameter key,value pairs
        debugLevel - 0 to 3, 3 being max level
        defaultParameters - dictionary where values are to be stored
        integerParameters - if current parameter name is in this list, value read will be converted to integer and stored
        floatParameters - if current parameter name is in this list, value read will be converted to float and stored

    Returned value:
        True

    """

    for myKey, myValue in values.items():
        if debugLevel > 2:
            print('DEBUG-3 JAGatherEnvironmentSpecs() key: {0}, value: {1}'.format(myKey, myValue))

        if myKey not in defaultParameters or storeCurrentValue == True:
            if myKey in integerParameters:
                defaultParameters[myKey] = int(myValue)
            elif myKey in floatParameters:
                defaultParameters[myKey] = float(myValue)
            else:
                # string value, store as is.
                defaultParameters[myKey] = myValue
    return True

def JAIsSupportedCommand( paramValue:str, allowedCommands, OSType:str ):
    """
    JAGlobalLib.JAIsSupportedCommand( paramValue:str, allowedCommands, OSType:str )

    searches for the given command in allowed commands list
    If not found, returns False,
    If found, returns True
    """
    returnStatus = True

    errorMsg = ''

    ### first mask the contents inside '' and "" so that command separator characters
    ###  inside that string/word is not interpretted as command separators
    commands = re.sub(r'\'(.+)\'|\"(.+)\"', "__JAString__", paramValue)

    ### separate command words in param value. commands may be separated by ; or |
    commands = re.split(r';|\||&', commands)
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
            ### look for commands inside (), search for contents inside the braket
            tempCommand =  re.search(r'\((.+)\)', command)
            if tempCommand != None:
                if tempCommand.group() not in allowedCommands:
                    returnStatus = False
            else:
                returnStatus = False
            errorMsg += 'Unsupported command:|{0}|,'.format(command)

    return returnStatus,errorMsg


def JAEvaluateCondition(serviceName, serviceAttributes, defaultParameters, debugLevel:int,
    interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType):

    """
    JAGlobalLib.JAEvaluateCondition(serviceName, serviceAttributes, defaultParameters, debugLevel:int,
    interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)
    
    Executes the serviceAttributes['Command'], and compares the result to the value specified in 
      serviceAttributes['Condition'] 

    The condition spec can be > | < | = and a value 
        The value can be integer or string

    """
    numberOfErrors = 0

    tempCommand = serviceAttributes['Command']
    ### if command spec is present, run the command
    if tempCommand == None:
        conditionPresent = False
        conditionMet = False
    else: 
        conditionPresent = True
        conditionMet = False

        ### now execute the command to get result 
        ###   command was checked for allowed command while reading the config spec
        if OSType == "Windows":
            tempCommandToEvaluateCondition = '{0} {1}'.format(
                defaultParameters['CommandShell'], tempCommand) 
        else:
            tempCommandToEvaluateCondition =  tempCommand
        tempCommandToEvaluateCondition = os.path.expandvars( tempCommandToEvaluateCondition ) 

        if debugLevel > 2:
            LogLine(
                "DEBUG-3 JAEvaluateCondition() name:|{0}|, executing command:|{1}|".format(
                    serviceName, tempCommandToEvaluateCondition),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        returnResult, returnOutput, errorMsg = JAExecuteCommand(
                                            defaultParameters['CommandShell'],
                                            tempCommandToEvaluateCondition, debugLevel, OSType)
        if returnResult == False:
            numberOfErrors += 1
            if re.match(r'File not found', errorMsg) != True:
                LogLine(
                    "ERROR JAEvaluateCondition() name:{0}, File not found, error evaluating the condition by executing command:|{1}|, error:|{2}|".format(
                            serviceName, tempCommandToEvaluateCondition, errorMsg), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            else:
                LogLine(
                    "ERROR JAEvaluateCondition() name:{0}, error evaluating the condition by executing command:|{1}|, error:|{2}|".format(
                            serviceName, tempCommandToEvaluateCondition, errorMsg), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            conditionMet = False
        else:
            if len(returnOutput) > 0:
                ### take the value from 2nd line
                conditionResult = returnOutput[1]    
                ### assign all lines
                conditionResults = returnOutput
            else:
                conditionResult = ''
                conditionResults = []

            ### separate the condition field spec ( >|<|=) (value)
            conditionSpecParts = serviceAttributes['Condition'].split(' ')
            if len(conditionSpecParts) > 0:

                ### if condition result is multiline string, compute the number of lines and compare that to the condition number
                lengthOfConditionResults = len(conditionResults)
                if  lengthOfConditionResults > 1:
                    if re.search('>', conditionSpecParts[0]):
                        if int(lengthOfConditionResults) > int( conditionSpecParts[1]):
                            ### condition met
                            conditionMet = True
                    elif re.search('<', conditionSpecParts[0]):
                        if int(lengthOfConditionResults) < int( conditionSpecParts[1]):
                            ### condition met
                            conditionMet = True
                    elif re.search('=', conditionSpecParts[0]):
                        if int(lengthOfConditionResults) == int( conditionSpecParts[1]):
                            ### condition met
                            conditionMet = True
                elif isinstance(conditionResult, int) :
                    ### numeric string
                    if re.search('>', conditionSpecParts[0]):
                        if int(conditionResult) > int( conditionSpecParts[1]):
                            ### condition met
                            conditionMet = True
                    elif re.search('<', conditionSpecParts[0]):
                        if int(conditionResult) < int( conditionSpecParts[1]):
                            ### condition met
                            conditionMet = True
                    elif re.search('=', conditionSpecParts[0]):
                        if int(conditionResult) == int( conditionSpecParts[1]):
                            ### condition met
                            conditionMet = True
                else:
                    ### string comparison
                    if conditionResult == conditionSpecParts[1] :
                        conditionMet = True              
                if conditionMet == False:
                    if debugLevel > 1:
                        LogLine(
                            "DEBUG-2 JAEvaluateCondition() name:|{0}|, condition not met, command response:|{1}|, condition:|{2}|, skipping the connectivity test".format(
                                serviceName, conditionResults, serviceAttributes['Condition']),
                            interactiveMode,
                            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            else:
                LogLine(
                    "WARN JAEvaluateCondition() name:|{0}|, invalid condition:|{1}|, expecting spec in the form: (> | < | =) (value), example: > 5".format(
                        serviceName, serviceAttributes['Condition']),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return conditionPresent, conditionMet

def JADatamaskMaskLine(line, datamaskSpec, debugLevel, interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType):
    """
    JAGlobalLib.JADatamaskMaskLine(line, datamaskSpec, debugLevel, interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)
    
    if curent line has any of the search string defined in datamask spec,
    replace those strings withe replace strings defined in datamask spec
    
    return line

    """

    if debugLevel > 2:
            LogLine(
                'DEBUG-3 JADatamaskMaskLine() initial input line:|{0}\n'.format(line),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 

    for search, replace in datamaskSpec.items():

        if debugLevel > 3:
            LogLine(
                'DEBUG-4 JADatamaskMaskLine() input:|{0}|, search:|{1}|, replace:|{2}|\n'.format(
                    line, search, replace),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 
        line = re.sub(r'{}'.format(search), r'{}'.format(replace),line )

        if debugLevel > 3:
            LogLine(
                'DEBUG-4 JADatamaskMaskLine() output line :|{0}\n'.format(line),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 
    if debugLevel > 2:
        LogLine(
            'DEBUG-3 - JADatamaskMaskLine() final output line:|{0}\n'.format(line),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 

    return line

def JADataMaskFile(fileName, datamaskSpec, debugLevel, interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType):
    """
    JADatamaskMaskFile(fileName, logFilePath, datamaskSpec, debugLevel, interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)

    This function applies datamask, translates given file to a temporary file with xlated strings.

    """
    returnStatus = True
    newFileName = "{0}.datamasked".format(fileName)
    try:
        with open(newFileName, "w") as newFile:
            try:
                with open( fileName, "r") as origFile:
                    while True:
                        ### reach each line from origFile, xlate the string and write to new file
                        oldLine = line = origFile.readline()
                        if not line:
                            break

                        for datamaskWord in datamaskSpec:
                            line = re.sub(r'{0}'.format(datamaskWord), '__JADatamask__', line)

                        newFile.write(line)

                        if debugLevel > 3:
                            LogLine(
                                "DEBUG-4 JADatamaskMaskFile() oldLine:|{0}\n, datamased line:|{1}|".format( oldLine, line ),
                                interactiveMode,
                                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 

                    origFile.close()
            except OSError as err:
                LogLine(
                    "ERROR JADatamaskMaskFile() Can't open file:|{0}|, OSError:{1}".format( fileName, err ),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 
                returnStatus = False
            newFile.close()

    except OSError as err:
        LogLine(
            "ERROR JADatamaskMaskFile() Can't write new file:|{0}|, OSError:{1}".format( newFileName, err ),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 
        returnStatus = False
    
    return returnStatus, newFileName

def JAComparePatterns(
        comparePatterns:dict, fileName:str,
        interactiveMode, debugLevel,
        myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType):
    """
    JAComparePatterns(
        comparePatterns, saveFileName,
        interactiveMode, debugLevel,
        myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)

    This function searches for a presence of compare patterns in line(s) within a file.
    If all patterns are found, returns True
    If any pattern is not found, returns False

    """
    returnStatus = True
    errorMsg = ''

    lines = []
    try:
        with open( fileName, "r") as file:
            lines = file.readlines()
            file.close()

    except OSError as err:
        LogLine(
            "ERROR JAComparePatterns() Can't open file:|{0}|, OSError:{1}".format( fileName, err ),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 
        returnStatus = False

    if returnStatus == True:
        numberOfPatternsToFind = len(comparePatterns)
        numberOfPatternsFound = 0
        ### now search for compare patterns in the lines read
        for line in lines:
            ### search for each pattern in each line   
            for comparePattern, conditions in comparePatterns.items():
                myResults =  re.findall(r'{0}'.format(comparePattern), line)
                if len(myResults) > 0:
                    numberOfMatchedPatterns = len(myResults[0])
                    myResults = myResults[0]
                else:
                    numberOfMatchedPatterns = 0
                if numberOfMatchedPatterns > 0:
                    ### for group values matching to the patterns,
                    ###    check conditions one by one in the conditions list
                    conditionsMet = 0
                    numberOfConditions = len(conditions)
                    for findAllGroupNumber, compareValue in conditions.items():
                        if numberOfMatchedPatterns >= findAllGroupNumber:
                            if isinstance(compareValue,int) == True:
                                if int(myResults[findAllGroupNumber]) == int(compareValue):
                                    conditionsMet += 1
                            else:
                                if str(myResults[findAllGroupNumber]) == str(compareValue):
                                    conditionsMet += 1
                    if conditionsMet == numberOfConditions:
                        ### all patterns found in current conditions
                        numberOfPatternsFound += 1
                        
            if numberOfPatternsToFind == numberOfPatternsFound:
                ### found all items, get out of the loop
                break

        if numberOfPatternsToFind != numberOfPatternsFound:
            LogLine(
                "WARN  JAComparePatterns() fileName:|{0}|, ComparePatterns:|{1}|, expected pattern matches:{2}, actual pattern matches:{3}".format(
                    fileName, comparePatterns, numberOfPatternsToFind, numberOfPatternsFound  ),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType) 
            returnStatus = False

    return returnStatus, errorMsg
