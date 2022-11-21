""" 
This script supports many functions to run audit of host covering application environment, OS environment, 
  connectivity check, get certificate and license details, run self-tests, run tasks, gather application log stats,
  collect system health, take heal action, collect software release information etc. For full details, refer to JAHelp()

Parameters passed: Review the JAHelp() for details.
    
Note - did not add python interpreter location at the top intentionally so that
    one can execute this using python or python3 depending on python version on target host

Author: havembha@gmail.com, 2022-10-29

Execution flow
   Get OSType, OSName, OSVersion
   Based on python version, check for availability of yml module
   Read JAEnvironment.yml and allow commands config file
   If base yml file not passed, derive the file name 
   Delete log files older than 7 days (not supported on windows yet)

"""

import os
import sys
import re
import datetime
import time
import subprocess
import signal
import platform
from collections import defaultdict
import JAGlobalLib

import JAReadEnvironmentConfig
import JAExecuteOperations

### define global variables
JAVersion = "JA01.00.00"
H2HDiffSedCmd = "H2HDiff.SedCmd"
skipH2HFileNameExtension = ".SkipH2H"
# this config file has environment specific definitions
environmentFileName = "JAEnvironment.yml"
# this config file has list of commands allowed to be executed by JAAudit
allowCommandsFileName = "JAAllowCommmands.conf"

# web server URL to post the OS stats data, per environment
SCMHostName = ''
debugLevel = 3
auditLogFileName  = 'JAAudit.log'

# default parameters read from app config file name
defaultParameters = {}

### define subprocess.run so as to make it work on hosts with python 2
try:
    from subprocess import CompletedProcess
except ImportError:
    # Python 2
    class CompletedProcess:

        def __init__(self, args, returncode, stdout=None, stderr=None):
            self.args = args
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

        def check_returncode(self):
            if self.returncode != 0:
                err = subprocess.CalledProcessError(
                    self.returncode, self.args, output=self.stdout)
                raise err
                return self.returncode

        def sp_run(*popenargs, **kwargs):
            input = kwargs.pop("input", None)
            check = kwargs.pop("handle", False)
            if input is not None:
                if 'stdin' in kwargs:
                    raise ValueError(
                        'stdin and input arguments may not both be used.')
                kwargs['stdin'] = subprocess.PIPE
            process = subprocess.Popen(*popenargs, **kwargs)
            try:
                outs, errs = process.communicate(input)
            except:
                process.kill()
                process.wait()
                raise
            returncode = process.poll()
            if check and returncode:
                raise subprocess.CalledProcessError(
                    returncode, popenargs, output=outs)
            return CompletedProcess(popenargs, returncode, stdout=outs, stderr=errs)

        subprocess.run = sp_run
        # ^ This monkey patch allows it work on Python 2 or 3 the same way

def JAAuditExit(reason):
    """
    convenient functoin print & log error and exit.
    """
    print(reason)
    JAGlobalLib.LogMsg(reason, auditLogFileName, True, True)
    sys.exit()

def JAHelp():
    helpString1 = """
    python JAAudit.py -o <operations> [-s <subsystem>] [-p <repositoryName>] [-k <SCMHostName>] [-H <downloadHostName>] 
       [-d <saveDirectory>] [-D <debugLevel>] [-f <baseConfigFile>] [-l <logFileName>]  [-F <reportFormat>]
       [-fT <fromTime in YYYY-MM-DD hh:mm:ss>] [-tT <toTime in YYYY-MM-DD hh:mm:ss>] [-dT <deltaTimeInMin>] 
       [-i <ignoreHostNameIPDifference>]
    
    -o <operations> - can have one or more operations in CSV format. operations supported are -
          cert,compare,conn,default,discover,download,heal,health,inventory,license,perfStatsOS,perfStatsApp,save,stats,sync,task,test,upload
          
        If called with operation 'cert'
            Checks the start and end dates, DNS alias of certificates specified in cert<baseConfigFile><subsystem>.yml file.
            The spec can include commands to connect to a running process, get the cert being used by that process
                and display desired attributes.

        If called with operation 'compare'
            Takes the environment snapshot by carrying out instructions in save<baseConfigFile><subsystem>.yml,
              compares the snapshot with the snapshot saved before at JAAudit/<saveDir>
            Typically used after applying change to the environment like OS update, application code/config update
                to audit the changes to the environment.

        If called with operation 'conn'
            Check connectivity from current host to other (local or remote) hosts by using the connectivity
                definition file conn<baseConfigFile><subsystem>.yml
            It uses operating system specific command or custom command specified in environment config file 
                to run connectivity check. For UDP type of protocol, it just sends the packets, need to capture the
                packets on other end to confirm the packets received on other end.

        If called with operation 'default'
            Executes all operations enabled in environment spec file based on periodicity specified. 
            Typically used by the non-interactive jobs like crontab to execute many operations periodically.
            This approach allows single crontab entry to run diverse set of operations. Those operations
                spec can be changed in a single source on SCM or git type of source repository and make the 
                change apply to all hosts in one or more environments.

        If called with operation 'discover'
            Runs the discover commands specified in save<baseConfigFile><subsystem>.yml, and creates save<baseConfigFile><subsystem>.yml.discover
                Displays the difference between save<baseConfigFile><subsystem>.yml and save<baseConfigFile><subsystem>.yml.disc
            Typically used to replace previous file references in save<baseConfigFile><subsystem>.yml with current file references
              seen on a host pertaining to latest application environment. This operation simplies the task of
              manually collecting file names and adding those to spec file. The content of discovered file can be used to
              update the spec file on SCM or git type of repository.

        If called with operation 'download'
            If rsync is enabled for that host, it will sync files from SCM host to local host from specified path.
            If not, uses wget to get latest files from SCM host to local host from specified path.
            Typically used during host to host compare, or to restore the files backed up before on SCM host. 

        If called with operation 'heal'
            Executes heal instructions in health<baseConfigFile><subsystem>.yml to automatically correct anomalies in system health.
            Actions are recorded in HealHistory.log.<YYYYMMDD>
            If heal action count exceeds the threshold, sends email alert.

        If called with operation 'health'
            Collects current health of a host covering OS, DB, application, services, connections etc by acting on 
                specification in health<baseConfigFile><subsystem>.yml.

        If called with operation 'inventory'
            Collects the S/W version information by carrying out instructions in inventory<baseConfigFile><subsystem>.yml
            Typically used after applying change to the environment like OS update, application code/config update
                to collect latest version information.

        If called with operation 'license'
            Executes license display commands specified in license<baseConfigFile><subsystem>.yml and displays the results

        If called with operation 'perfStatsOS'
            Invokes JAGatherOSStats.py along with host specific parameters.

        If called with operation 'perfStatsApp'
            Invokes JAGatherLogStats.py along with host specific parameters.

        If called with operation 'save'
            Takes the environment snapshot by carrying out instructions in save<baseConfigFile><subsystem>.yml,
              Saves the collected snapshot in JAAudit/<saveDir>
            Typically done before applying change to the environment like OS update, application code/config update

        If called with operation 'stats'
            Parse log file(s) specified in stats<baseConfigFile><subsystem>.yml and print stats in CSV format

        If called with operation 'sync'
            Syncs the code & config (all spec files) from SCM to local host. rsync will be used if specified
                in environment spec file. Else, wget will be used to sync the files.
            Can enable periodic sync operation via non-interactive scheduling like crontab so as to 
                achieve continuous deployment of audit tool to all desired environments automatically.

        If called with operation 'task'
            Runs the tasks specified in task<baseConfigFile><subsystem>.yml
            Typically used to manage tasks to be run on many hosts of one or more environments by using
                single definition source on SCM or git type of repository. This task approach eliminates the
                need to manage the crontab on each individual host.

        If called with operation 'test'
            Runs the tests specified in test<baseConfigFile><subsystem>.yml, compare current result to the <ExpectedResult>
                If <ExpectedResult>.sedCmd file is present, first translate the contents of <ExpectedResult> and 
                   current result by applying those sed commands before comparing to ignore dynamic contents.
            Typically used before a change is made to the environment to record behavior of the application before a change
               and after the change is completed to ensure behavior is no worse than previous behavior.

        If called with operation 'upload'
            Uploads the files from JAAudit/<saveDir> to SCM host and saved under 
                <WebServerMainDir>/<platform>/<hostName>/
                <WebServerAltDir>/<platform>/<hostName>/
            Typically done for host to host compare or to take backup of files from target host on SCM host
            Operations like inventory, cert, conn, stats, health, test do implicit upload to upload the data collected
               to SCM host for further processing when such operations are executed via non-interactive session.

    [-s <subsystem>] - subsystem name to be used to derive the config file name containing specifications
        to be used to run the operations like conn, cert, stats etc. 
        The subsystem name  can be OS, DB, App, OSS, Vendor etc.
        Defaut subsystem is 'App'.
    
    [-p <repositoryName>] - platform name to be sent to SCM host while doing rsync or wget so that
        platform specific files are downloaded to current host. This platform name is also used
        while uploading the file to SCM so that the file is placed under platform specific path on SCM host.
        The directory or folder path on SCM is computed using <WebServerMain>/<platform>/<hostname> and
            <WebServerAlt>/<platform>/<hostname>
        Default value is picked up from environment configuration file for the current host.

    [-k <SCMHostName>] - SCM hostname used for upload and download operations.
        Default values per component per environment is picked up from environment definition config file.
    
    [-H <downloadHostName>] - Typically used while running 'download,compare' operations.
        This hostname refers to the host whose environment is to be compared to current host's environment.
    """

    helpString2 = """
    [-d <saveDirectory>] - Directory where files will be saved if operation is 'save' or 'download'.
        Directory from where files will be uploaded to SCM if operation is 'upload'
        Files under this directory will be compared with source files if operation is 'compare'
        If value is not passed for 'download' operation and -H <downloadHostName> is passed
            downloaded info is saved under JAAudit/otherHost
        Else if value is not passed for the operations 'save' 'compare', 'upload', 'download'
            If subsystem is OS, use the OS version id as directory name (JAAudit/<OSVersion>).
            Else if the application version spec is defined in environment config file, use that application version
                id as the directory name (JAAudit/<AppVersion>)
            Else use JAAudit/old as directory name

    [-D <debugLevel>] - 0 no debug, 1, 2, 3, 3 being max level
        default is 0, no debug

    [-f <baseConfigFile>] typically in the form Audit<Platform><component>
        Default file name is picked up environment config file per component.
        Base config file or spec file used per component to derive operation specific config file or spec file.
        For operations like 'save', 'compare', 'save' is prefixed to this file name to derive spec file
        For 'cert', 'conn', 'heal', 'health', 'inventory', 'license', 'task', 'test', the operation word is prefixed to this file name
          to derive spec file.
        For 'perfStatsOS', and 'perfStatsApp' operations, the operation word is prefixed to this file 
          to derive the spec file to be passed to the python script that collects stats.
        
    [-l <logFileName>] - log comparison outout to a log file
        Defaults to the terminal in the interactive mode

    [-F <reportFormat>] - color or HTML or none
        If color, ERROR text will be displayed in RED color. Escape characters are logged to the log file
            so that when that log file is typed (cat), the lines are displayed in color.
        If HTML, HTML color tags are used to highlight the lines.
        If none, no special formatting of output.
        Defauts to color.

    [-fT <fromTime in YYYY-MM-DD hh:mm:ss>] - applicable for 'stats' operation.
        Process the log lines from this time onwards.

    [-tT <toTime in YYYY-MM-DD hh:mm:ss>] - applicable for 'stats' operation.
        Process the log lines till this time.
    
    [-dT <deltaTimeInMin>] - applicable for 'stats' operation.
        Compute fromTime by subtracting these number of minutes from current time.
        Use current time as toTime.
    
    [-i <ignoreHostNameIPDifference>] - If 'yes', ignore hostname and host's IP while doing host to host compare.
        Defaults to 'no'

    """

    helpString3 = """
    Examples:
        python JAAudit.py -o save <-- save current environment, typically done before code install. 
            Default <saveDir> is used. (see <saveDir> for more details)
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o save -s OS <-- save current OS environment, typically done before OS updates. 
            Default <saveDir> applicable to OS vesion is used. (see <saveDir> for more details)
            OS <subsystem> is used
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o save -s DB <-- save current DB (database) environment, typically done before DB updates. 
            Default <saveDir> is used. (see <saveDir> for more details)
            DB <subsystem> is used
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o save -d PreReleaseX.Y <-- save current environment in PreReleaseX.Y directory
               as a pre-upgrade step, before installing ReleaseX.Y
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o compare <-- compare current environment to previously saved snapshot, 
                typically done aafter the code install. 
            Default <saveDir> is used to compare the files under that directory. (see <saveDir> for more details)
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o compare -s OS <-- compare current OS environment to previously saved snapshot, 
                typically done after OS updates. 
            Default <saveDir> applicable to OS vesion is used. (see <saveDir> for more details)
            OS <subsystem> is used
            Default base config file name specified in environment config file is used for the current hostname
        
        python JAAudit.py -o compare -d PreReleaseX.Y <-- compare current environment to snapshot saved in 
                PreReleaseX.Y directory. Typically used after the upgrade. 
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o save,upload <-- save current environment and upload to SCM host, 
                typically done before code install. 
            Default <saveDir> is used. (see <saveDir> for more details)
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname
            Default SCM hostname is used (see <SCMHostName> for more details)

        python JAAudit.py -o save,upload -D 2 <-- save current environment and upload to SCM host, 
                typically done before code install. 
            Default <saveDir> is used. (see <saveDir> for more details)
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname
            Default SCM hostname is used (see <SCMHostName> for more details)
            DebugLevel of 2 is used.

        python JAAudit.py -o download,compare -k SCM1 -H RefHostName <-- download environment from SCM1 
                for the hostname RefHostName and compare to current host, typically done to perform host to host complare. 
            Default <saveDir> is used. (see <saveDir> for more details)
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o download,compare -k SCM1 -H RefHostName -i yes <-- download environment from SCM1 
                for the hostname RefHostName and compare to current host while ignoring the hostname and IP differences, 
                typically done to perform host to host complare. 

        python JAAudit.py -o sync <-- sync code and config from SCM to current host
                Typically used to update the Audit tool artifact on a host where periodic sync is not enabled

        python JAAudit.py -o inventory,upload -k SCM1 <-- take inventory and upload to SCM1 

        python JAAudit.py -o stats <-- parse log files and print stats
                Typically used to monitor the host's performance
                Default duration of last 10 min is used.
                
        python JAAudit.py -o stats -dT 60 <-- parse log files and print stats covering last one hour log lines
                Typically used to monitor the host's performance
                
        python JAAudit.py -o stats -fT "2022-11-05 00:00:00" -tT "2022-11-05 13:00:00" <-- parse log lines with timestamp
                given in fromTime and toTome.

        python JAAudit.py -o conn <-- run connectivity test from current host to other host(s)
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o conn,upload <-- run connectivity test from current host to other host(s) and 
                upload results to SCM host.

        python JAAudit.py -o conn -s OS <-- run connectivity test from current host to other host(s)
            OS <subsystem> is used to formulate the connectivity spec file name.
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o cert <-- check certificats on current host and certs used by running processes
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o cert,upload <-- check certificats on current host, certs used by running processes and
                upload results to SCM host
            Default <subsystem> of 'App' is used (see <subsystem> for more details)
            Default base config file name specified in environment config file is used for the current hostname

        python JAAudit.py -o health,upload <-- collect health and upload to SCM

        python JAAudit.py -o heal <-- take heal action on current host

        python JAAudit.py -o license <-- display license information

        python JAAudit.py -o test <-- run self tests

        python JAAudit.py -o task <-- execute tasks

        python JAAudit.py -o discover <-- discover files and display delta.

    """
    print(helpString1)
    print(helpString2)
    print(helpString3)
    return None

### install signal handler to exit upon ctrl-C
def JASignalHandler(sig, frame):
    JAAuditExit("Control-C pressed")

signal.signal(signal.SIGINT, JASignalHandler)


### display help if no arg passed
if len(sys.argv) < 2:
    JAHelp()
    sys.exit()

### parse arguments passed
# this dictionary will have argument pairs
# to find the value of an arg, use argsPassed[argName]
argsPassed = {}

JAGlobalLib.JAParseArgs(argsPassed)

if '-D' in argsPassed:
    debugLevel = int(argsPassed['-D'])
    
if debugLevel > 0 :
    print("JAAudit.py Version {0}\nParameters passed: {1}".format(JAVersion, argsPassed))

baseConfigFileName = None
if '-f' in argsPassed:
    # config file name passed.
    baseConfigFileName = argsPassed['-f']
    if debugLevel > 0:
        print("DEBUG-1 baseConfigFileName passed: {0}".format(baseConfigFileName))
        
if '-o' in argsPassed:
    operations = argsPassed['-o']
else:
    print("ERROR mandatory parameter operations is not passed")
    JAHelp()
    sys.exit()

if '-l' in argsPassed:
    try:
        # log file requested
        outputFileHandle = open ( argsPassed['-l'], "w")
    except OSError as err:
        errorMsg = "ERROR - Can not open configFile:|{0}|, OS error: {1}\n".format(argsPassed['-l'], err)
        JAAuditExit(errorMsg)
else:
    outputFileHandle = None

if '-s' in argsPassed:
    # substem name passed
    subsystem = argsPassed['-s']
else:
    subsystem = ''

if '-p' in argsPassed:
    # substem name passed
    myPlatform = argsPassed['-p']
else:
    myPlatform = ''

if '-k' in argsPassed:
    # SCM host name passed
    SCMHostName = argsPassed['-k']
else:
    SCMHostName = ''

### get current hostname, OSType, OSName, OSVersion
thisHostName = platform.node()
# if hostname has domain name, strip it
hostNameParts = thisHostName.split('.')
thisHostName = hostNameParts[0]

# get OSType, OSName, and OSVersion. These are used to execute different python
# functions based on compatibility to the environment
OSType, OSName, OSVersion = JAGlobalLib.JAGetOSInfo(sys.version_info, debugLevel)

errorMsg  = "JAAudit.py Version:{0}, OSType: {1}, OSName: {2}, OSVersion: {3}".format(
    JAVersion, OSType, OSName, OSVersion)
print(errorMsg)
JAGlobalLib.LogMsg(errorMsg,auditLogFileName, True)

### check whether yaml module is present
yamlModulePresent = JAGlobalLib.JAIsYamlModulePresent()
    
# uncomment below to test local parsing of yaml file where pythin 3 is not present
# yamlModulePresent = False


### read environment definitions from JAEnvironment.yml
if JAReadEnvironmentConfig.JAReadEnvironmentConfig( 
        environmentFileName, defaultParameters, yamlModulePresent, 
        debugLevel, auditLogFileName, thisHostName, OSType ) == False:
    JAAuditExit('Fatal ERROR, exiting')

### if base config file not passed as argument, use the one from environment config
if baseConfigFileName == None:
    if 'AppConfig' in defaultParameters:
        baseConfigFileName = defaultParameters['AppConfig']

### if SCM hostname is passed, use that for sync, download, upload operations
if SCMHostName != '':
    defaultParameters['SCMHostName'] = defaultParameters['SCMHostName1'] = defaultParameters['SCMHostName2']  \
        = SCMHostName

### define colors to print messages in different color
myColors = {
    'red':      ['',"\033[31m",'<font color="red">'], 
    'green':    ['',"\033[32m",'<font color="green">'], 
    'yellow':   ['',"\033[33m",'<font color="yellow">'], 
    'blue':     ['',"\033[34m",'<font color="blue">'], 
    'magenta':  ['',"\033[35m",'<font color="magenta">'], 
    'cyan':     ['',"\033[36m",'<font color="cyan">'], 
    'clear':    ['',"\033[0m",'</font>'], 
    }

# reportFormat is passed, set the color index
HTMLBRTag = ''
if '-r' in argsPassed:
    if re.match('HTML|html', argsPassed['-r']) :
        # this index needs to match the index at HTML tags for diff colors are assigned in myColors dictionary
        colorIndex = 2
        HTMLBRTag = "<br>"
    elif re.match('color', argsPassed['-r']) :
        # this index needs to match the index at which VT100 terminal color codes are assigned in myColors dictionary
        colorIndex = 1
    else:
        # no color coding of lines
        colorIndex = 0
else:
    # defaults to color
    colorIndex = 1

if debugLevel > 2:
    # test LogLine() with test lines
    myLines = """ERROR - expect to see in red color
ERROR, - expect to see in red color
DIFF   - expect to see in cyan color
WARN   - expect to see in yellow color
PASS   - expect to see in green color
 PASS  - expect to see in green color
<      blue color line
>      magenta color line"""
    JAGlobalLib.LogLine(myLines, True, myColors, colorIndex, outputFileHandle, HTMLBRTag)

returnResult = "_JAAudit_PASS_" # change this to other errors when error is encountered


### determin current session type using the term environment value, sleep for random duration if non-interactive 
if os.getenv('TERM') == '' or os.getenv('TERM') == 'dumb':
    interactiveMode = True
else:
    interactiveMode = False
    # sleep for random time using RandomizationWindow spec
    if 'RandomizationWindowInSec' in defaultParameters:
        randomizationWindow = defaultParameters['RandomizationWindowInSec']
    else:
        # stagger the execution by 10 min or 600 seconds
        randomizationWindow = 600

    import random
    sleepTime = random.randint(0,randomizationWindow)
    print("INFO sleeping for :{0} sec, if this is interactive session, set TERM environment variable (export TERM=vt100) ".format(sleepTime))
    time.sleep(sleepTime)


### if PATH and LD_LIBRARY are defined, set those environment variables
if 'PATH' in defaultParameters:
    os.environ['PATH'] = defaultParameters['PATH']

if 'LD_LIBRARY_PATH' in defaultParameters:
    os.environ['LD_LIBRARY_PATH'] = defaultParameters['LD_LIBRARY_PATH']

### get current time in seconds
currentTime = time.time()

### delete log files and report files older than specified days
if 'FileRetencyDurationInDays' in defaultParameters:
    fileRetencyDurationInDays = defaultParameters['FileRetencyDurationInDays']
else:
    # default retency period - 7 days
    fileRetencyDurationInDays = 7

if OSType == 'Windows':
    ### get list of files older than retency period
    filesToDelete = JAGlobalLib.JAFindModifiedFiles(
            '{0}/JAAudit*.log.*'.format(defaultParameters['LogFilePath']), 
            currentTime - (fileRetencyDurationInDays*3600*24), ### get files modified before this time
            debugLevel, thisHostName)
    if filesToDelete != '':
        for fileName in filesToDelete:
            try:
                os.remove(fileName)
                if debugLevel > 3:
                    print("DEBUG-4 JAAudit() Deleting the file:{0}".format(fileName))
            except OSError as err:
                print("ERROR JAAudit() Error deleting old log file:{0}, errorMsg:{1}".format(fileName, err))
else:
    # delete log files covering logs of operations also.
    command = 'find {0} -name "JAAudit*.log.*" -mtime +{1} |xargs rm'.format(defaultParameters['LogFilePath'], fileRetencyDurationInDays)
    if debugLevel > 0:
        print("DEBUG-1 JAAudit() Executing command:{0} to purge files".format(command))

    returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(command, OSType, OSName, OSVersion, debugLevel)
    if returnResult == False:
        if re.match(r'File not found', errorMsg) != True:
            print("ERROR JAAudit() Error deleting old log files {0} {1}".format(returnOutput, errorMsg))
            JAGlobalLib.LogMsg(errorMsg, auditLogFileName, True)


### get application version, this is used to derive host/component specific specification file(s)
if 'CommandToGetAppVersion' in defaultParameters:
    commandToGetAppVersion = defaultParameters['CommandToGetAppVersion']
    returnResult, returnOutput, errorMsg = JAGlobalLib.JAExecuteCommand(
        commandToGetAppVersion, OSType, OSName, OSVersion, debugLevel)
    if returnResult == True:
        appVersion = returnOutput.rstrip("\n")
        appVersion = appVersion.lstrip()
    else:
        appVersion = ''
        print( errorMsg)
        JAGlobalLib.LogMsg(errorMsg, auditLogFileName, True)
else:
    appVersion = ''



### if operation is default, sync, download, or upload, need to connect to SCM. Check the connectivity
if re.match(r"sync|download|upload|default", operations):

    if 'SCMHostName1' in defaultParameters and 'SCMPortHTTPS' in defaultParameters:
        # check connectivity to SCM host
        connectivitySpec = [
            [defaultParameters['SCMHostName1'], 'TCP', defaultParameters['SCMPortHTTPS']],
            ]
        returnStatus, passCount, failureCount, detailedResults = JAGlobalLib.JACheckConnectivityToHosts( 
            defaultParameters, connectivitySpec, OSType, OSName, OSVersion, interactiveMode, debugLevel)
        if passCount > 0:
            prevSCMHostCheckStatus = True
            defaultParameters['SCMHostName'] = SCMHostName = defaultParameters['SCMHostName1']
            if debugLevel > 0:
                print("DEBUG-1 JAAudit() connectivity check to wget port:{0} on SCMHostName:{1} PASSED".format(
                        defaultParameters['SCMPortHTTPS'], SCMHostName
                    ))
        else:
            # check connectivity to SCMHostName2
            connectivitySpec = [
                [defaultParameters['SCMHostName2'], 'TCP', defaultParameters['SCMPortHTTPS']],
                ]
            returnStatus, passCount, failureCount, detailedResults = JAGlobalLib.JACheckConnectivityToHosts( 
               defaultParameters, connectivitySpec, OSType, OSName, OSVersion, interactiveMode, debugLevel)
            if passCount > 0:
                prevSCMHostCheckStatus = True
                defaultParameters['SCMHostName'] = SCMHostName = defaultParameters['SCMHostName2']
            else:
                # SCM hostname is not accessible
                defaultParameters['SCMHostName'] = SCMHostName = None

        # if operation is sync or default, check connectivity to rsync port if rsync port is specified
        if ( (re.match(r"sync", operations) != None and  
            re.match(r"nosync", operations) == None) or 
            re.match(r"default", operations) ):
            if 'SCMPortRsync' in defaultParameters:
                # check connectivity to SCM host
                connectivitySpec = [
                    [SCMHostName, 'TCP', defaultParameters['SCMPortRsync']],
                    ]
                returnStatus, passCount, failureCount, detailedResults = JAGlobalLib.JACheckConnectivityToHosts( 
                    defaultParameters, connectivitySpec, OSType, OSName, OSVersion, interactiveMode, debugLevel)
                if passCount != 1:
                    print("ERROR JAAudit() connectivity check to rsync port:{0} on SCMHostName:{1} FAILED".format(
                                defaultParameters['SCMPortRsync'], SCMHostName ))
                else:
                    if debugLevel > 0:
                        print("DEBUG-1 JAAudit() connectivity check to rsync port:{0} on SCMHostName:{1} PASSED".format(
                                defaultParameters['SCMPortRsync'], SCMHostName
                            ))


### if sync is opted, run it
if re.search("sync", operations) != None and re.match("nosync", operations) == None:
    JAExecuteOperations.JARun( "sync", defaultParameters['MaxWaitTime'],
        baseConfigFileName, subsystem, myPlatform, appVersion,
        OSType, OSName, OSVersion, defaultParameters['LogFilePath'], auditLogFileName, 
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel, currentTime
    )
    
### if conn operation is opted, read config file, run connn tests and if upload is opted,
###    upload results to SCM
if re.search("conn", operations):
    JAExecuteOperations.JARun( "conn", defaultParameters['MaxWaitTime'],
        baseConfigFileName, subsystem, myPlatform, appVersion,
        OSType, OSName, OSVersion, defaultParameters['LogFilePath'], auditLogFileName, 
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel, currentTime
    )