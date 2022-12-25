"""
This module reads yml config file and assigns the values to passed defaultParameters dictionary

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


def JAReadEnvironmentConfig( 
    fileName, defaultParameters, yamlModulePresent, debugLevel, auditLogFileName, thisHostName, OSType):
    """
    This function reads environment config file
    If JAAudit.profile exists, the environment file location is read from that file.
    If JAAudit.profile does not exist, and environment file is read from ./Custom direcotry if present

    # Parameter name needs to be unique across all sections - OS, Component, and Environment
    # Parameters can be defined under OS, Component or Environment.
    # Parameter value can be redefined in other sections to override previous value.
    # Parameters under OS will be read first, under Component next and under Environment last.
    # While reading parameters under Component, if a value is present under specific component, 
    #   it will be stored as latest desired value, overriding the value previously defined under OS
    # While reading parameters under Environment, if a value is present under specific environment, 
    #   it will be stored as latest desired value, overriding the value previously defined under OS or Component
    # In all cases (OS, Component, Environment sections), value under 'All' will be stored 
    #   if the value is not yet stored before in any prior section.

    Before exiting, store the current location of environment file in JAAudit.profile

    Parameters passed: 
        config file name - yml file name containing parameter spec
        defaultParameters dictionary to update with values read
        yamlModulePresent = True or False
        debugLevel - 0 to 3, 3 being max
        auditLogFileName - log file to log messages
        thisHostName - current host name, used to match the hostname spec
        OSType - current host's OS type

    Returned value
        True if success, False if file could not be read

    """

    # this list contains the parameter names in JAEnvornment.yml file that needs to be converted to integer and store
    #  in defaultParameters{}
    integerParameters = [
        'BackupRetencyDurationInDays',
        'DebugLevel','DeltaTimeForStatsInMin','DueInDaysForCert', 'FileRetencyDurationInDays','FileExecPermission', 
        'DueInDaysForLicence', 'HealIntervalInSec', 'HealAfterTimeInSec', 
        'RandomizationWindowForHealthInSec', 'RandomizationWindowForOtherInSec',
        'RandomizationWindowForTaskInSec', 'SitePrefixLength',
        ]
    # this list contains the parameter names in JAEnvornment.yml file that needs to be converted to float and store
    #  in defaultParameters{}
    floatParameters = [
        'OperationCert', 'OperationConn', 'OperationConnOS',
        'OperationCompare', 'OperationHeal', 'OperationHealth', 'OperationInventory', 'OperationLicense', 
        'OperationPerfStatsApp', 'OperationPerfStatsOS', 'OperationSave', 'OperationStats', 'OperationSync', 
        'OperationTask', 'OperationTest', 'OperationUpload'
        ]

    returnStatus = True

    ### first check whether profile is present in current working directory
    returnStatus, localRepositoryCustom = JAGlobalLib.JAGetProfile("JAAudit.profile", 'LocalRepositoryCustom')
    if returnStatus == True:
        ### localReposistoryCustom is available, environment file may be under that folder.
        ###   if present, update file to that location
        tempFileName = '{0}/{1}'.format(localRepositoryCustom, fileName)

        if os.path.exists(tempFileName) == True:
            fileName = tempFileName
        if debugLevel > 0:
            print("DEBUG-1 JAReadEnvironmentConfig() Using environment spec file:{0} from JAAudit.profile".format(fileName))
    elif os.path.exists('./Custom/{0}'.format(fileName)):
        ### use the file in ./Custom/ if present
        fileName = './Custom/{0}'.format(fileName)
        if debugLevel > 0:
            print("DEBUG-1 JAReadEnvironmentConfig() Using environment spec file:{0}".format(fileName))

    elif os.path.exists(fileName) == False:
        print("ERROR JAReadEnvironmentConfig() Not able to find {0} in current directory, or in ./Custom directory.\n\
            Get the file from SCM, place it in directory as specified for environment 'LocalRepositoryCustom' or default location ./Custom directory\n".format(fileName))
        return False

    # use limited yaml reader when yaml is not available
    if yamlModulePresent == True:
        try:
            import yaml
            with open(fileName, "r") as file:
                defaultParametersSpec = yaml.load(file, Loader=yaml.FullLoader)
                file.close()
        except OSError as err:
            errorMsg = "ERROR JAReadEnvironmentConfig() Can not open configFile:|{0}|, OS error: {1}\n".format(
                fileName, err)
            print(errorMsg)
            JAGlobalLib.LogMsg(errorMsg, auditLogFileName, True, True)
            return False
    else:
        defaultParametersSpec = JAGlobalLib.JAYamlLoad(fileName)

    errorMsg = ''

    # Get global definitions (not environment specific)
    if 'LogFilePath' in defaultParametersSpec:
        defaultParameters['LogFilePath'] = defaultParametersSpec['LogFilePath']

    if 'Platform' in defaultParametersSpec:
        defaultParameters['Platform'] = defaultParametersSpec['Platform']

    # read OS section first
    if 'OS' in defaultParametersSpec:
        for key, value in defaultParametersSpec['OS'].items():
            if key == 'All' or key == 'ALL':
                # if parameters are not yet defined, read the values from this section
                # values in this section work as default if params are defined for
                # specific environment
                JAGlobalLib.JAGatherEnvironmentSpecs(
                        False, # store value if not present already
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)

            # store definitions matching to current OSType
            if key == OSType:
                # read all parameters defined for this environment
                JAGlobalLib.JAGatherEnvironmentSpecs(
                    True, # store current value if prev value is present
                    value, debugLevel, defaultParameters, integerParameters, floatParameters)
                defaultParameters['OS']  = key

    # read Component section next
    if 'Component' in defaultParametersSpec:
        for key, value in defaultParametersSpec['Component'].items():
            if key == 'All' or key == 'ALL':
                # if parameters are not yet defined, read the values from this section
                # values in this section work as default if params are defined for
                # specific environment
                JAGlobalLib.JAGatherEnvironmentSpecs(
                        False, # store value if not present already
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)

            # match current hostname to hostname specified within each environment to find out
            #   which environment spec is to be applied for the current host
            if value.get('HostName') != None:
                if re.match(value['HostName'], thisHostName):
                    # current hostname match the hostname specified for this environment
                    # read all parameters defined for this environment
                    JAGlobalLib.JAGatherEnvironmentSpecs(
                        True, # store current value if prev value is present
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)
                    defaultParameters['Component'] = key

    # read Environment section last
    if 'Environment' in defaultParametersSpec:
        for key, value in defaultParametersSpec['Environment'].items():
            if key == 'All' or key == 'ALL':
                # if parameters are not yet defined, read the values from this section
                # values in this section work as default if params are defined for
                # specific environment
                JAGlobalLib.JAGatherEnvironmentSpecs(
                        False, # store value if not present already
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)

            # match current hostname to hostname specified within each environment to find out
            #   which environment spec is to be applied for the current host
            if value.get('HostName') != None:
                if re.match(value['HostName'], thisHostName):
                    # current hostname match the hostname specified for this environment
                    # read all parameters defined for this environment
                    JAGlobalLib.JAGatherEnvironmentSpecs(
                        True, # store current value if prev value is present, parameters under Environment takes precedence
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)
                    defaultParameters['Environment']  = key

    # set default behavior if environment config does not include a value for it.
    if 'OperationSync' not in defaultParameters:
        defaultParameters['OperationSync'] = 0
        if debugLevel > 0:
            errorMsg += "DEBUG-1 JAReadEnvironmentConfig() Disabled OperationSync, enable it in {0} if needed\n".format(
                fileName) 

    if 'OperationHeal' not in defaultParameters:
        defaultParameters['OperationHeal'] = 0
        if debugLevel > 0:
            errorMsg += "DEBUG-1 JAReadEnvironmentConfig() Disabled OperationHeal, enable it in {0} if needed\n".format(
                fileName) 

    if 'BinaryFileTypes' not in defaultParameters:
        defaultParameters['BinaryFileTypes'] = '(\.jar)|(\.war)|(\.)tar|(\.).gz|(\.)zip|(\.)gzip|logfilter(.*)'

    if 'RandomizationWindowInSec' not in defaultParameters:
        defaultParameters['RandomizationWindowInSec'] = 600
        if debugLevel > 0:
            errorMsg += "DEBUG-1 JAReadEnvironmentConfig() Using default value: {0} for RandomizationWindowInSec, set it in {1} if needed\n".format(
                defaultParameters['RandomizationWindowInSec'],
                fileName) 

    if 'SCMHostName1' not in defaultParameters:
        errorMsg += "ERROR JAReadEnvironmentConfig() Mandatory parameter SCMHostName1 not specified in {0}\n".format(
            fileName)
        returnStatus = False
    elif 'SCMHostName2' not in defaultParameters:
        errorMsg += "WARN JAReadEnvironmentConfig() SCMHostName2 hostname not specified in {0}, make sure SCMHostName1:{1} is load balancer URL with high availability\n".format(
            fileName, defaultParameters['SCMHostName1'])

    if 'MaxWaitTime' not in defaultParameters:
        defaultParameters['MaxWaitTime'] = 600

    if 'FilesToExcludeInWget' not in defaultParameters:
        ### default skip files
        defaultParameters['FilesToExcludeInWget'] = '(\.swp$)|(\.log$)|^__pycache__/$'
    
    ### make a list of files to copy to save directory if not specified
    if 'FilesToCompareAfterSync' not in defaultParameters:
        defaultParameters['FilesToCompareAfterSync'] = "*.exp *.yml *.py *.pl *.ksh *.bash *.Rsp* *.sql *.sedCmd"

    ### set up default files to have exec permission if not specified
    if 'FilesWithExecPermission' not in defaultParameters:
        defaultParameters['FilesWithExecPermission'] = '(\.exp$)|(\.py$)|(\.pl$)|(\.ksh$)|(\.bash$)|^logfilter(\d+)$'

    ### set default permission if not specified
    if 'FileExecPermission' not in defaultParameters:
        defaultParameters['FileExecPermission'] = '750'

    ### set default retenc periods
    # delete log files, report files after this time
    if 'FileRetencyDurationInDays' not in defaultParameters:
        defaultParameters['FileRetencyDurationInDays'] = 7
    # delete backup directory after this time
    if 'BackupRetencyDurationInDays' not in defaultParameters:
        defaultParameters['BackupRetencyDurationInDays'] = 60

    if OSType == "Windows":
        if 'CommandShell' not in defaultParameters:
            ### chekc if powershell 7 is present
            if os.path.exists('C:/Program Files/PowerShell/7/pwsh.exe'):
                defaultParameters['CommandShell'] = 'C:/Program Files/PowerShell/7/pwsh.exe -NonInteractive -command'
            else:
                defaultParameters['CommandShell'] ="TBD"

    ### setup default compare commands based on OSType
    if 'CompareCommand' not in defaultParameters:
        if OSType == "Windows":
            defaultParameters['CompareCommand'] = defaultParameters['CommandShell'] + " compare-object -SyncWindow 10"
        elif OSType == 'Linux':
            ### ignore blank lines
            defaultParameters['CompareCommand'] = 'diff -B'
 
    ### exand any environment variables used in path definitions
    if 'LocalRepositoryHome' in defaultParameters:
        defaultParameters['LocalRepositoryHome'] = os.path.expandvars(defaultParameters['LocalRepositoryHome'])
    if 'LogFilePath' in defaultParameters:
        defaultParameters['LogFilePath'] = os.path.expandvars(defaultParameters['LogFilePath'])
    if 'ReportsPath' in defaultParameters:
        defaultParameters['ReportsPath'] = os.path.expandvars(defaultParameters['ReportsPath'])
    if 'JaaduVisionPath' in defaultParameters:
        defaultParameters['JaaduVisionPath'] = os.path.expandvars(defaultParameters['JaaduVisionPath'])

    ### SCMRepositoryBasePath is needed if rysnc command is present
    if 'SCMRepositoryBasePath' not in defaultParameters and 'CommandRsync' in defaultParameters:
        errorMsg = "ERROR JAReadEnvironmentConfig() Missing spec for 'SCMRepositoryBasePath', while rsync operation is enabled via 'CommandRsync':|{0}".format(
            defaultParameters['CommandRsync'])
        print( errorMsg)
        sys.exit(0)

    ### use defualt values for SCMRepositoryCommon and SCMRepositoryCustom if not defined
    if 'SCMRepositoryCommon' not in defaultParameters:
        defaultParameters['SCMRepositoryCommon'] = 'Common'
    if 'SCMRepositoryCustom' not in defaultParameters:
        defaultParameters['SCMRepositoryCustom'] = OSType
    if 'SCMUploadPath' not in defaultParameters:
        defaultParameters['SCMUploadPath'] = OSType

    ### create log file path if does not exist
    if 'LogFilePath' in defaultParameters:
        logFilePath = defaultParameters['LogFilePath']
    else:
        if 'LocalRepositoryHome' in defaultParameters:
            logFilePath = defaultParameters['LocalRepositoryHome'] + "/Logs"

    ### if logFilePath does not end with '/', add it
    if re.match(r'/$', logFilePath) == None:
        logFilePath = '{0}/'.format(logFilePath)
    defaultParameters['LogFilePath'] = logFilePath

    if os.path.exists(logFilePath) == False:
        try:
            os.mkdir(logFilePath)
        except OSError as err:
            errorMsg = "ERROR JAReadEnvironmentConfig() Could not create logs directory:{0}".format(
                logFilePath, err )
            print( errorMsg)
            sys.exit(0)

    ### create reports path if does not exist
    if 'ReportsPath' in defaultParameters:
        reportsFilePath = defaultParameters['ReportsPath']
    else:
        if 'LocalRepositoryHome' in defaultParameters:
            reportsFilePath = defaultParameters['LocalRepositoryHome'] + "/Reports"
        else:
            reportsFilePath = ''
    if os.path.exists(reportsFilePath) == False:
        try:
            os.mkdir(reportsFilePath)
        except OSError as err:
            errorMsg = "ERROR JAReadEnvironmentConfig() Could not create reports directory:{0}".format(
                reportsFilePath, err )
            print( errorMsg)
            sys.exit(0)


    ### write the LocalRepositoryCustom value to JAAudit.profile 
    if 'LocalRepositoryCustom' in defaultParameters:
        localReposistoryCustom = defaultParameters['LocalRepositoryCustom']
    else:
        localReposistoryCustom = "Custom"

    ### set default behavior for VerifyCertificate
    if 'VerifyCertificate' not in defaultParameters:
        defaultParameters['VerifyCertificate'] = True

    ### set default behavior for upload path
    if 'SCMUploadPath' not in defaultParameters:
        if 'Platform' in defaultParameters:
            defaultParameters['SCMUploadPath'] = defaultParameters['Platform']
        else:
            defaultParameters['SCMUploadPath'] = ''

    ### this default needs to match what was defined on SCM web server
    ###  this path is directly under <DocumentRoot>/UploadLocal/<platform>/<hostName>/<files>
    if 'DownloadBasePath' not in defaultParameters:
        defaultParameters['DownloadBasePath'] = 'UploadLocal'

    ### set report file names to empty list. This will be populated by various operation related modules
    ###   after executing the operation, if report upload to SCM is also opted
    ### this file list assumes report files are at path 'ReportsPath', only file names are listed in this list.
    defaultParameters['ReportFileNames'] = []

    ### set upload file names to empty list. This will be populated by save or download operation modules
    ### this file list assumes  files are at path 'SaveDir', only file names are listed in this list.
    defaultParameters['UploadFileNames'] = []

    ### operation name like save, upload, cert, conn... to Operation Interval spec variable in defaultParameters[]
    operationTranslation = {
        'cert': 'OperationCert',
        'conn': 'OperationConn',
        'compare': 'OperationCompare',
        'heal': 'OperationHeal',
        'health': 'OperationHealth',
        'inventory': 'OperationInventory',
        'license': 'OperationLicense',
        'perfStatsApp': 'OperationPerfStatsApp',
        'perfStatsOS': 'OperationPerfStatsOS',
        'save': 'OperationSave',
        'stats': 'OperationStats',
        'sync': 'OperationSync',
        'task': 'OperationTask',
        'test': 'OperationTest',
        'upload': 'OperationUpload',
    }
    ### convert OperationXXXX values in number of hours to number of seconds and save under <opration> key 
    for tempOperation, value in operationTranslation.items():
        defaultParameters[tempOperation] = defaultParameters[value] * 3600

    if 'SitePrefixLength' not in defaultParameters:
        defaultParameters['SitePrefixLength'] = 3

    JAGlobalLib.JASetProfile("JAAudit.profile", 'LocalReposistoryCustom', localReposistoryCustom)

    if debugLevel > 1:
        print('DEBUG-2 JAReadEnvironmentConfig() Content of config file: {0}, read to auditEnvironment: {1}'.format(
            fileName, defaultParameters))
    elif debugLevel > 0:
        print('DEBUG-1 JAReadEnvironmentConfig() Read environment config file:|{0}|'.format(fileName))

    if errorMsg != '':
        print(errorMsg)
        JAGlobalLib.LogMsg(errorMsg, auditLogFileName, True, True)

    return True
    
