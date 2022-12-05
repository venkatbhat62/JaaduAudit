#!/usr/bin/python3

"""
This Web Service saves the file contents posted as text or binary 
Parameters passed
    hostName - mandatory - host that is posting the data
    savePath - path to save the file under, this needs to be relative path to document root on web server
    debugLevel - 0 no debug, 1,2,3, 3 highest level
    fileName - save data with this file name

Return Result
    200 - on success
    400 - bad request
    401 - unauthorized
    403 - can't save data on save path given, permission denied
    404 - savePath not found
    411 - content length 0 or not passed
    413 - payload too large, exceeded the max file size limit
    500 - internal server error
    507 - insufficient storage, can't save fille on server

"""

import time, threading, socket, socketserver 
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn

import os,sys,json,re
from datetime import datetime
import yaml
import requests
import JAGlobalLib 
from collections import defaultdict
from urllib.parse import urlparse
from urllib.parse import parse_qs
import random

### max size set to 20GB
JAMaxContentLength = 1024 * 1000000 * 20
JAListenPortNumber = 9061
JANumberOfThreads = 100
### root path on web server, posted savePath is appended to store the file on Web server
JADocumentRoot = '/var/www/JaaduAudit/'
JALogFileName = ''
SaveStatsStartTime = datetime.now()

def JAUploadWSExit(self, reason, statusCode, JAUploadWSStartTime):
    if re.match('^ERROR ', reason):
        message='ERROR JASaveWS.py() {0} <Response [500]>'.format(reason)
        print("ERROR {0}\n".format( reason ))

    elif re.match('^PASS ', reason):
        message='PASS  JASaveWS.py() {0} <Response [200]>'.format(reason)
    else:
        message='      JASaveWS.py() {0}'.format(reason)

    self.send_response(statusCode)
    self.end_headers()
    JAUploadWSEndTime = datetime.now()
    JAUploadWSDuration = JAUploadWSEndTime - JAUploadWSStartTime
    JAUploadWSDurationInSec = JAUploadWSDuration.total_seconds()
    message = r'{0}, response time:{1} sec'.format( message, JAUploadWSDurationInSec)

    JAGlobalLib.LogMsg(message, JALogFileName, True)
    self.wfile.write(message.encode())
    return

def JAUploadWSError(self, reason, statusCode,JAUploadWSStartTime ):
    JAUploadWSExit(self, str('ERROR Could not save the file:{0}'.format(reason)), statusCode, JAUploadWSStartTime)
    return

class Handler(BaseHTTPRequestHandler):
    # def do_GET(self):
    def do_POST(self):

        #if self.path != '/':
        #    self.send_error(404, "Object not found")
        #    return
        #self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')

        returnResult=''
        JAUploadWSStartTime = datetime.now()

        contentLength = int(self.headers['Content-Length'])
        contentType = self.headers['Content-Type']
        if contentLength > 0:
            if contentLength > JAMaxContentLength:
                JAUploadWSError(self, 
                    'ERROR content length:{0} exceeded max size:{1}'.format(contentLength, JAMaxContentLength), 
                    413, JAUploadWSStartTime) 
                return   
        else:
            JAUploadWSError(self, 'ERROR zero content posted', 411, JAUploadWSStartTime)
            return

        postedData = parse_qs(urlparse(self.path).query)

        ### hostName - mandatory - host that is posting the data
        ### savePath - path to save the file under, this needs to be relative path to document root on web server
        ### debugLevel - 0 no debug, 1,2,3, 3 highest level
        ### fileName - save data with this file name

        if postedData['savePath'] == None:
            ### savePath is mandatory 
            JAUploadWSError(self, 'ERROR savePath not passed', 400, JAUploadWSStartTime)
            return
        else:
            savePath = postedData['savePath']
            fullSavePath = "{0}/{1}".format( JADocumentRoot, savePath)
            if not os.path.exits(fullSavePath):
                JAUploadWSError(
                    self, 
                    'ERROR savePath {0} not present on web server, DocumentRoot/savePath:{1}'.format(savePath, fullSavePath), 
                    404, JAUploadWSStartTime)
                return
        if postedData['hostName'] == None:
            JAUploadWSError(self, 'ERROR hostName not passed', 400, JAUploadWSStartTime)
            return
        else:
            hostName = postedData['hostName']
            ### if hostName folder not present, create it
            if not os.path.exists():
                try:
                    os.mkdir()
                except OSError as err:
                    JAUploadWSError(
                        self, 
                        "ERROR can't create folder:{0}/{1}/{2}".format(JADocumentRoot, savePath, hostName), 
                        403, JAUploadWSStartTime)    
        if postedData['fileName'] == None:
            ### if valid JADirStats is present, expect fileName to be passed to save the data locally 
            JAUploadWSError(self, 'ERROR fileName not passed', 400, JAUploadWSStartTime)
            return
        else:
            ### TBD add code to deal with multiple files
            fileNames = postedData['fileName']

        if postedData['debugLevel'] == None:
            debugLevel = 0
        else:
            debugLevel = int(postedData['debugLevel'])
    
        for fileName in fileNames:
            WSFileName = "{0}/{1}/{2}/{3}".format( JADocumentRoot, savePath, hostName, fileName)

            ### open the file in append mode and save data
            ###   only one posting expected at a time from a given host.
            ###   since fileName is hostName specific, this will not be an issue while multiple threads are running
            try:
                ### save data locally if fileName is specified
                with open( WSFileName, 'wb') as fpo:
                    fpo.write(fileName.file.read())
                    fpo.close()
            except OSError as err:
                fpo = None
                JAUploadWSError(
                    self, 
                    'ERROR Not able to open file to write:{0}'.format(WSFileName), 
                    403, JAUploadWSStartTime)
                return
        returnResult='PASS - Saved file at (full path):{0}, relative path:{1}/{2}/{3}, contentLength:{4}'.format(
            fileName, savePath, hostName, postedData['fileName'], contentLength )

        ### print status and get out
        JAUploadWSExit(self, str(returnResult), 200, JAUploadWSStartTime )
        return

class ThreadingSimpleServer(ThreadingMixIn, HTTPServer):
    pass

### read config parameters
with open('JAAudit.yml','r') as file:
    JAGlobalVars = yaml.load(file, Loader=yaml.FullLoader)
    if 'JALogDir' in JAGlobalVars:
        JALogDir = JAGlobalVars['JALogDir']
    if 'JAUploadWS' in JAGlobalVars:
        if 'LogFileName' in JAGlobalVars['JAUploadWS']:
            JALogFileName = JALogDir + "/" + JAGlobalVars['JAUploadWS']['LogFileName']

        if 'NumberOfThreads' in JAGlobalVars['JAUploadWS']:
            ### read configured number of threads value
            JANumberOfThreads = int(JAGlobalVars['JAUploadWS']['NumberOfThreads'])

        if 'Port' in JAGlobalVars['JAUploadWS']:
            JAListenPortNumber = JAGlobalVars['JAUploadWS']['Port'] 

        if 'DocumentRoot' in JAGlobalVars['JAUploadWS']:
            JADocumentRoot = JAGlobalVars['JAUploadWS']['DocumentRoot'] 

    else:
        JALogFileName = JALogDir + "/" + "JAUploadWS.log"
    file.close() 

# Create ONE socket.
addr = ('', JAListenPortNumber)
sock = socket.socket (socket.AF_INET, socket.SOCK_STREAM)
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

### set receive buffer size to 32K
RECV_BUF_SIZE = 32768
sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUF_SIZE) 
sock.bind(addr)
sock.listen(5)
                                                                                                                   
# Launch listener threads.
class Thread(threading.Thread):
    def __init__(self, i):
        threading.Thread.__init__(self)
        self.i = i
        self.daemon = True
        self.start()
        
    def run(self):
        httpd = ThreadingSimpleServer(addr, Handler, False)
        # Prevent the HTTP server from re-binding every handler.
        # https://stackoverflow.com/questions/46210672/
        httpd.socket = sock
        httpd.server_bind = self.server_close = lambda self: None
        
        httpd.serve_forever()

# start threads
print("DEBUG creating :{0} threads\n".format(JANumberOfThreads))

[Thread(i) for i in range(0,JANumberOfThreads,1)]
time.sleep(9e9)
