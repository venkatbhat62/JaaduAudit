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

"""
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
def JAGatherEnvironmentSpecs(storeCurrentValue, values, debugLevel, defaultParameters, integerParameters, floatParameters):
    for myKey, myValue in values.items():
        if debugLevel > 1:
            print('DEBUG-2 JAGatherEnvironmentSpecs() key: {0}, value: {1}'.format(myKey, myValue))

        if myKey not in defaultParameters or storeCurrentValue == True:
            if myKey in integerParameters:
                defaultParameters[myKey] = int(myValue)
            elif myKey in floatParameters:
                defaultParameters[myKey] = float(myValue)
            else:
                # string value, store as is.
                defaultParameters[myKey] = myValue
    return True

"""
This function reads environment config file

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
def JAReadEnvironmentConfig( fileName, defaultParameters, yamlModulePresent, debugLevel, auditLogFileName, thisHostName, OSType):

    # this list contains the parameter names in JAEnvornment.yml file that needs to be converted to integer and store
    #  in defaultParameters{}
    integerParameters = [
        'SitePrefixLength', 'DebugLevel','DeltaTimeForStatsInMin','DueInDaysForCert',
        'DueInDaysForLicence', 'HealIntervalInSec', 'HealAfterTimeInSec', 
        'RandomizationWindowForHealthInSec', 'RandomizationWindowForOtherInSec',
        'RandomizationWindowForTaskInSec', 'FileRetencyDurationInDays'
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

    # use limited yaml reader when yaml is not available
    if yamlModulePresent == True:
        try:
            import yaml
            with open(fileName, "r") as file:
                defaultParametersSpec = yaml.load(file, Loader=yaml.FullLoader)
                file.close()
        except OSError as err:
            errorMsg = "ERROR JAReadEnvironmentConfig() Can not open configFile:|{0}|, OS error: {1}\n".format(fileName, err)
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
                JAGatherEnvironmentSpecs(
                        False, # store value if not present already
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)

            # store definitions matching to current OSType
            if key == OSType:
                # read all parameters defined for this environment
                JAGatherEnvironmentSpecs(
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
                JAGatherEnvironmentSpecs(
                        False, # store value if not present already
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)

            # match current hostname to hostname specified within each environment to find out
            #   which environment spec is to be applied for the current host
            if value.get('HostName') != None:
                if re.match(value['HostName'], thisHostName):
                    # current hostname match the hostname specified for this environment
                    # read all parameters defined for this environment
                    JAGatherEnvironmentSpecs(
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
                JAGatherEnvironmentSpecs(
                        False, # store value if not present already
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)

            # match current hostname to hostname specified within each environment to find out
            #   which environment spec is to be applied for the current host
            if value.get('HostName') != None:
                if re.match(value['HostName'], thisHostName):
                    # current hostname match the hostname specified for this environment
                    # read all parameters defined for this environment
                    JAGatherEnvironmentSpecs(
                        True, # store current value if prev value is present, parameters under Environment takes precedence
                        value, debugLevel, defaultParameters, integerParameters, floatParameters)
                    defaultParameters['Environment']  = key

    # set default behavior if environment config does not include a value for it.
    if 'OperationSync' not in defaultParameters:
        defaultParameters['OperationSync'] = 0
        if debugLevel > 0:
            errorMsg += "DEBUG-1 JAReadEnvironmentConfig() Disabled OperationSync, enable it in {0} if needed\n".format(fileName) 

    if 'OperationHeal' not in defaultParameters:
        defaultParameters['OperationHeal'] = 0
        if debugLevel > 0:
            errorMsg += "DEBUG-1 JAReadEnvironmentConfig() Disabled OperationHeal, enable it in {0} if needed\n".format(fileName) 

    if 'RandomizationWindowInSec' not in defaultParameters:
        defaultParameters['RandomizationWindowInSec'] = 600
        if debugLevel > 0:
            errorMsg += "DEBUG-1 JAReadEnvironmentConfig() Using default value: {0} for RandomizationWindowInSec, set it in {1} if needed\n".format(
                defaultParameters['RandomizationWindowInSec'],
                fileName) 

    if 'KITSHostName1' not in defaultParameters:
        errorMsg += "ERROR JAReadEnvironmentConfig() Mandatory parameter KITSHostName1 not specified in {0}\n".format(fileName)
        returnStatus = False
    elif 'KITSHostName2' not in defaultParameters:
        errorMsg += "WARN JAReadEnvironmentConfig() KITSHostName2 hostname not specified in {0}, make sure KITSHostName1:{1} is load balancer URL with high availability\n".format(fileName, defaultParameters['KITSHostName1'])

    if 'MaxWaitTime' not in defaultParameters:
        defaultParameters['MaxWaitTime'] = 600

    if debugLevel > 1:
        print('DEBUG-2 JAReadEnvironmentConfig() Content of config file: {0}, read to auditEnvironment: {1}'.format(fileName, defaultParameters))
    if errorMsg != '':
        print(errorMsg)
        JAGlobalLib.LogMsg(errorMsg, auditLogFileName, True, True)


    return returnStatus
    
