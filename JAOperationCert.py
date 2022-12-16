"""
This file contains the functions to cert check
Author: havembha@gmail.com, 2022-12-16

Execution Flow
    Read certificate check spec yml file to buffer
    Extract cert  specific parametrs from yml buffer
    Decode cert, check validity dates
    If interactive mode, display results
    Else, store the results to a JAAudit.cert.log.YYYYMMDD file
    If upload is enabled, add report file to upload file list
    Create JAAudit.cert.history file

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

def JAReadConfigCert( 
        baseConfigFileName, 
        subsystem, 
        version, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        certParameters, allowedCommands ):
        
    """
   Parameters passed:
        baseConfigFileName - Vaue of 'AppConfig' parameter defined in JAEnvironment.yml for that host or component for that environment
        subsystem - if not empty, it will be Prefixed to derive config file
        version - if not empty, suffixed to the baseConfigFileName to find release specific config file
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel, 
        certSpec - full details, along with default parameters assigned, are returned in this dictionary

    Returned Values:
        returnStatus - True on success, False upon file read error
        numberOfItems - number of items read


    Cert spec format: refer to WindowsAPP.Apps.cert.yml and LinuxAPP.Apps.cert.yml for details.

    """
    returnStatus = False
    errorMsg = ''
    numberOfItems = 0
    numberOfErrors = 0
    numberOfWarnings = 0

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigCert() AppConfig:{0}, subsystem:{1}, version:{2} ".format(
                baseConfigFileName, subsystem, version),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    baseConfigFileNameParts = baseConfigFileName.split('.')
    if len(baseConfigFileNameParts) != 2:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigCert() AppConfig name not in expected format, no . (dot) in filename:|{0}|".format(baseConfigFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

        return returnStatus, numberOfItems

    ### derive the save compare spec file, first check under LocalRepositoryCustom, next under LocalRepositoryCommon
    returnStatus, certSpecFileName, errorMsg = JAGlobalLib.JADeriveConfigFileName( 
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCustom']),
          '{0}/{1}'.format(defaultParameters['LocalRepositoryHome'], defaultParameters['LocalRepositoryCommon']),
          baseConfigFileName, subsystem, 'cert', version, debugLevel )
    if returnStatus == False:
        JAGlobalLib.LogLine(
            "ERROR JAReadConfigCert() AppConfig:|{0}| not present, error:|{1}|".format(baseConfigFileName, errorMsg),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        return returnStatus, numberOfItems
        
    if debugLevel > 1:
        JAGlobalLib.LogLine(
            "DEBUG-2 JAReadConfigCert() Derived AppConfig file name using subsystem and version as part of file name:|{0}|".format(certSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    ### Now read the yml file
    # use limited yaml reader when yaml is not available
    if yamlModulePresent == True:
        try:
            import yaml
            with open(certSpecFileName, "r") as file:
                certSpec = yaml.load(file, Loader=yaml.FullLoader)
                file.close()
        except OSError as err:
            errorMsg = "ERROR JAReadConfigCert() Can not open configFile:|{0}|, OS error:|{1}|\n".format(
                certSpecFileName, err)
            JAGlobalLib.LogLine(
                "ERROR JAReadConfigCert() AppConfig:|{0}| not present, error:|{1}|".format(certSpecFileName, errorMsg),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    else:
        certSpec = JAGlobalLib.JAYamlLoad(certSpecFileName)

    errorMsg = ''

    saveParameter = False  
    overridePrevValue = False

    for key, value in certSpec.items():
             
        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-2 JAReadConfigCert() processing key:|{0}|, value:{1}".format(key, value),
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

        if value.get('Certs') != None:
            ### expect variable definition to be in dict form
            for certName, certParams in value['Certs'].items():
                numberOfItems += 1 
                """ service params can have below attributes 
                    certAttributes = [
                        'Alias',
                        'Cert',
                        'Command',
                        'Condition',
                        ]
                """
                if overridePrevValue == False:
                    if certName in certParameters:
                        if 'Cert' in certParameters[certName]:
                            ### value present for this service already, SKIP current definition
                            ###  this is valid, DO NOT warn for this condition
                            ### spec may be present under individual environment and later in All section
                            continue

                ### If any of Command or Condion is present, other one needs to be present.
                if 'Command' in certParams and 'Condition' not in certParams:
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigCert() Cert name:{0}, 'Condition' not present, need 'Condition' attribute when 'Command' attribute is specified, Skipped this definition".format(
                            certName ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue
                if 'Command' not in certParams and 'Condition' in certParams:
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigCert() Cert name:{0}, 'Command' not present, need 'Command' attribute when 'Condition' attribute is specified, Skipped this definition".format(
                            certName ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue

                if 'Cert' not in certParams:
                    JAGlobalLib.LogLine(
                        "WARN JAReadConfigCert() Cert name:{0}, 'Cert' attribute is specified, Skipped this definition".format(
                            certName ),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                    numberOfWarnings += 1
                    continue
                
                ### store current cert details
                certParameters[certName] = certParams

                if 'Alias' not in certParams:
                    ### set default protocol
                    certParameters[certName]['Alias'] = None

                ### put default value of None for command and condition if not present
                if 'Condition' not in certParams:
                    certParameters[certName]['Condition'] = None
                if 'Command' not in certParams:
                    certParameters[certName]['Command'] = None

                if debugLevel > 1:
                    JAGlobalLib.LogLine(
                        "DEBUG-2 JAReadConfigCert() Cert name:{0}, attributes:{1}".format(
                            certName, certParameters[certName]),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                
        else:
            JAGlobalLib.LogLine(
                "ERROR JAReadConfigCert() Unsupported key:{0}, value:{1}, skipped this object".format(
                    key, value),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            numberOfErrors += 1

    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAReadConfigCert() Read {0} items with {1} warnings, {2} errors from AppConfig:{3}".format(
                numberOfItems, numberOfWarnings, numberOfErrors, certSpecFileName),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return returnStatus, numberOfItems


def JAOperationCert(
    baseConfigFileName, subsystem, myPlatform, appVersion,
    OSType, OSName, OSVersion,   
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime, allowedCommands, operation ):

    returnStatus = True
    errorMsg = ''

    ### derive cert spec file using subsystem and application version info
        
    if debugLevel > 0:
        JAGlobalLib.LogLine(
            "DEBUG-1 JAOperationConn() Cert spec:{0}, subsystem:{1}, appVersion:{2}, interactiveMode:{3}".format(
            baseConfigFileName, subsystem, appVersion, interactiveMode),
            interactiveMode,
            myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
    
    ### dictionary to hold object definitions
    certParameters = defaultdict(dict)

    ### read the object spec file contents
    returnStatus, numberOfItems = JAReadConfigCert( 
        baseConfigFileName, 
        subsystem, 
        appVersion, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, operations, thisHostName, yamlModulePresent,
        defaultParameters, debugLevel,
        certParameters, allowedCommands )
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
    numberOfCertChecks = 0

    reportFileNameWithoutPath = "JAAudit.cert.{0}".format( JAGlobalLib.UTCDateForFileName() )
    reportFileName = "{0}/{1}".format( defaultParameters['ReportsPath'], reportFileNameWithoutPath )
    with open( reportFileName, "w") as reportFile:

        ### write report header
        reportFile.write(
"TimeStamp: {0}\n\
Platform: {1}\n\
HostName: {2}\n\
Environment: {3}\n\
Certs:\n\
".format(JAGlobalLib.UTCDateTime(), defaultParameters['Platform'], thisHostName, defaultParameters['Environment']) )

        ### save or compare information of each object
        for certName in certParameters:
            numberOfItems += 1
            certAttributes = certParameters[certName]

            if debugLevel > 2:
                JAGlobalLib.LogLine(
                    "DEBUG-3 JAOperationConn() Processing cert name:|{0}|, cert attributes:|{1}|".format(
                    certName, certAttributes),
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            """
            Cert attributes are:
                'Command',
                'Condition',
                'Cert',
                'Alias'
            """
            conditionPresent, conditionMet = JAGlobalLib.JAEvaluateCondition(
                                certName, certAttributes, defaultParameters, debugLevel,
                                interactiveMode, myColors, colorIndex, outputFileHandle, HTMLBRTag, OSType)

            if conditionPresent == True:
                if conditionMet == False:
                    ### SKIP connectivity test, condition not met
                    numberOfConditionsNotMet += 1
                    continue
                else:
                    numberOfConditionsMet += 1

            reportFile.write(
"   {0}:\n\
        Command: {1}\n\
        Condition: {2}\n\
        Cert: {3}\n\
        Alias: {4}\n\
        Results:\n".format(
            certName,
            certAttributes['Command'],
            certAttributes['Condition'],
            certAttributes['Cert'],
            certAttributes['Alias'],
        ))


        JAGlobalLib.LogLine(
            "INFO JAOperationCert() Total Certs:{0}, conditions met:{1}, conditions NOT met:{2}, \
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