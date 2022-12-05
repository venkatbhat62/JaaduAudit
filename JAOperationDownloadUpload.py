"""
This file contains the functions to download files from SCM or upload files to SCM
Author: havembha@gmail.com, 2022-12-04

Execution Flow
    for download operation,
        Make a file containing the URLs.
        pass the URL file name to wget with -i option to fetch all those files

    for upload operation,
        make a file containing the URLs, pass that to curl or reeuests.session() of python lib

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

def JAOperationUpload(
    OSType, OSName, OSVersion,   
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, 
    defaultParameters, debugLevel ):

    """
    This function posts the data to Source Code Manager URL passed.
    Uses native python requess.session if module is present, else, it will use curl to post the data.

    Parameters passed:
        defaultParameters['UploadFileNames'] - path/file names of data to be posted in list form
        defaultParameters['SCMUploadPath'] - web server path to append to the URL to post
        defaultParameters['SCMHostName'] - SCM host URL to be used to post the data 
        defaultParameters['SCMPortHTTPS'] - SCM web server port to be used in URL
        thisHostName - current host name, posted to SCM web server so that data can be stored under separate folder name
                    matching to hostname.
        debugLevel - used to print debug message locally as well as from SCM web server, this param will be posted to SCM web server
        OSType, OSName, OSVersion - used to formulate appropriate commands & options while posting data to SCM web server


    """
    # headers = {'Content-type': 'application/octet-stream', 'Accept': 'text/plain'}
    headers = {'Content-type': 'multipart/form-data'}
    requestSession = None
    useRequests = False
    try:
        if sys.version_info.major >= 3 and sys.version_info.minor >= 3:
            import importlib
            import importlib.util
            try:
                if importlib.util.find_spec("requests") != None:
                    useRequests = True
                    import requests
                    from urllib3.exceptions import InsecureRequestWarning
                    from urllib3 import disable_warnings

                    requestSession = requests.session()
                    if defaultParameters['DisableWarnings']  == True:
                        disable_warnings(InsecureRequestWarning)

                else:
                    useRequests = False

                importlib.util.find_spec("json")
                
            except ImportError:
                JAGlobalLib.LogLine(
                    "WARN JAOperationUpload() import error, NOT using requests to post",
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)    
    except:
        if useRequests == False:
            JAGlobalLib.LogLine(
                "WARN JAOperationUpload() not able to determin python release level, NOT using requests to post",
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    webServerURL = "https://{0}:{1}/cgi-bin/JAUploadFile.py".format(
        defaultParameters['SCMHostName'],
        defaultParameters['SCMPortHTTPS'],
          )
    verifyCertificate = defaultParameters['VerifyCertificate']
    platform = defaultParameters['SCMUploadPath']
    datamaskFileName = defaultParameters['SCMDataMaskSpec']

    numberOfFiles = sucessCount =  failureCount = localFileNotFound = 0
    uploadSuccess = True
    saveDir = defaultParameters['SaveDir']

    for shortFileName in defaultParameters['UploadFileNames']:
        numberOfFiles += 1

        params = {  'fileName':shortFileName,
                    'platform':platform,
                    'hostName': thisHostName,
                    'datamaskFileName':datamaskFileName,
                    'JADebugLevel': debugLevel }
        fileName = "{0}/{1}".format( saveDir, shortFileName)
        if not os.path.exists( fileName) :
            JAGlobalLib.LogLine(
                "ERROR JAOperationUpload() File not present:|{0}|".format( fileName), 
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
            uploadSuccess = False
            localFileNotFound += 1
            continue

        if useRequests == True:
            try:
                with open( fileName, "rb") as file:
                    try:
                        returnResult = requestSession.post(
                        # returnResult = requests.post(
                            url=webServerURL, 
                            files={'file':file}, 
                            data=params,
                            verify=verifyCertificate, 
                            timeout=300) 
                            
                        resultText = returnResult.text
                    except requestSession.exceptions.RequestException as err:
                        resultText += "<Response [500]> requestSession.post() Error posting data to web server {0}, exception raised","error:{1}\n".format(webServerURL, err)

                    file.close()
            except OSError as err:
                JAGlobalLib.LogLine(
                    "ERROR JAOperationUpload() Error opening upload file:|{0}|, error:|{1}|".format( fileName, err), 
                    interactiveMode,
                    myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
                uploadSuccess = False
                continue
        else:
            try:
                result = subprocess.run(
                    ['curl', '-k', '-X', 'POST', webServerURL, 
                        '-H', "Accept: text/plain", 
                        '-H', "Content-Type: application/octet-stream", 
                        '-d', "@{0}".format(fileName),
                        '-d', "fileName={0}&platform={1}&hostName={2}&datamaskFileName={3}".format(
                            fileName, platform, thisHostName, datamaskFileName  ) 
                        ], 
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                resultText = result.stdout.decode('utf-8').split('\n')
            except Exception as err:
                resultText = "<Response [500]> subprocess.run(curl) Error posting data to web server {0}, exception raised, error:{1}\n".format(webServerURL, err)

        resultLength = len(resultText)
        if resultLength > 1 :
            try:            
                if re.search(r'ERROR Could not save the file', resultText):
                    uploadSuccess = False 
                else:   
                    uploadSuccess = True
            except :
                uploadSuccess = False
        else:
            uploadSuccess = False

        if uploadSuccess == False:
            failureCount += 1
            JAGlobalLib.LogLine(
                "ERROR JAOperationUpload() Error uploading file:{0}, error:|{1}|".format( fileName, resultText ),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
        else:
            sucessCount += 1
            if debugLevel > 0:
                    JAGlobalLib.LogLine(
                        "DEBUG-1 JAOperationUpload() uploaded file:|{0}|, with result:|{1}|".format(fileName, resultText),
                        interactiveMode,
                        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    JAGlobalLib.LogLine(
        "INFO JAOperationUpload() Total number of files:{0}, successful upload:{1}, failures:{2}, local file not found:{3}".format(
            numberOfFiles, sucessCount, failureCount, localFileNotFound ),
        interactiveMode,
        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    return uploadSuccess,  ""

def JAOperationDownload(    
    baseConfigFileName, 
    subsystem, 
    myPlatform, 
    version,
    OSType, OSName, OSVersion,  
    outputFileHandle, colorIndex, HTMLBRTag, myColors,
    interactiveMode, operations, thisHostName, yamlModulePresent,
    defaultParameters, debugLevel, currentTime,
    allowedCommands,
    operation ):

    ### dictionary to hold object definitions
    saveCompareParameters = defaultdict(dict)

    ### read the object spec file contents
    returnStatus, numberOfItems = JAOperationSaveCompare.JAOperationReadConfig( 
        baseConfigFileName, 
        subsystem, 
        version, 
        OSType,
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode, yamlModulePresent,
        defaultParameters, debugLevel,
        saveCompareParameters, allowedCommands )
    if returnStatus == False:
        ### fatal error, can't proceed.
        return returnStatus, numberOfItems

    ### upload will follow, prepare upload file list
    JAOperationSaveCompare.JAPrepareUploadFileList(
        baseConfigFileName, 
        subsystem, 
        OSType, 
        outputFileHandle, colorIndex, HTMLBRTag, myColors,
        interactiveMode,
        defaultParameters, saveCompareParameters,
        debugLevel )

    numberOfFiles, sucessCount, failureCount = 0

    ### now download the files from SCM
    for fileName in defaultParameters['UploadFileNames']:
        numberOfFiles += 1
        if debugLevel > 1:
            JAGlobalLib.LogLine(
                "DEBUG-2 JAOperationDownload() downloading file:{0}".format( fileName ),
                interactiveMode,
                myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)

    JAGlobalLib.LogLine(
        "INFO JAOperationDownload() Total number of files:{0}, successful upload:{1}, failures:{2}".format(
            numberOfFiles, sucessCount, failureCount ),
        interactiveMode,
        myColors, colorIndex, outputFileHandle, HTMLBRTag, False, OSType)
