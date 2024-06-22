import glob
import logging
import os
import re
import shutil
import signal
import socket
import threading
from typing import List
import humanize
import http.server
import socketserver
import time
from functools import cached_property
from pathlib import Path
from limits import storage, strategies, parse
from esm import Tools
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import Timer

log = logging.getLogger(__name__)

class ZipFile:
    name: str = None
    path: str = None
    size: int = 0
    downloads: int = 0
    wwwrootPath: Path = None

    def __init__(self, name: str, path: str, size: int, downloads: int, wwwrootPath: Path):
        self.name = name
        self.path = path
        self.size = size
        self.downloads = downloads
        self.wwwrootPath = wwwrootPath

@Service
class EsmSharedDataServer:

    @cached_property
    def config(self) -> MainConfig:
        return self.configService.config
    
    @cached_property
    def configService(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    def dedicatedServer(self) -> EsmDedicatedServer:
        return ServiceRegistry.get(EsmDedicatedServer)

    def start(self):
        scenarioName = self.config.dedicatedConfig.GameConfig.CustomScenario
        pathToScenarioFolder = Path(f"{self.config.paths.install}/Content/Scenarios/{scenarioName}").resolve()

        log.info(f"Creating new manual shared data zip file from the current configured scenario at '{pathToScenarioFolder}' for manual download.")
        zipFiles = self.createSharedDataZipFiles(pathToScenarioFolder)
        zipFiles = self.moveSharedDataZipFilesToWwwroot(zipFiles)

        for zipFile in zipFiles:
            log.info(f"Created SharedData zip file as '{zipFile.wwwrootPath}' with a size of '{humanize.naturalsize(zipFile.size, gnu=False)}'.")

        self.prepareIndexHtml()
        # start webserver on configured port and serve the zip and also the index.html that explains how to handle the shared data
        myHostIp = Tools.getOwnIp(self.config)
        servingUrlRoot = f"http://{myHostIp}:{self.config.downloadtool.serverPort}"
        
        log.info(f"Server configured to allow max {humanize.naturalsize(self.config.downloadtool.maxGlobalBandwith, gnu=False)}/s in total network bandwidth.")
        log.info(f"Server configured to allow max {humanize.naturalsize(self.config.downloadtool.maxClientBandwith, gnu=False)}/s network bandwith per connection.")
        log.info(f"Started download server")

        # get the manual zipfile from the zipfiles list
        manualZipFile = list(filter(lambda x: x.name == self.config.downloadtool.manualZipName, zipFiles))[0]

        servingUrlManualZip = f"{servingUrlRoot}/{manualZipFile.name}"
        log.info(f"Shared data zip file for manual download is at: '{servingUrlManualZip}' (instructions: '{servingUrlRoot}')")

        if self.config.downloadtool.useSharedDataURLFeature:
            autoZipFile = list(filter(lambda x: x.name != self.config.downloadtool.manualZipName, zipFiles))[0]
            sharedDataUrl = f"{servingUrlRoot}/{self.config.downloadtool.autoZipName}"
            sharedDataUrlRedirectTarget = f"{servingUrlRoot}/{autoZipFile.name}"
            log.info(f"Shared data zip file for server is at: '{sharedDataUrl}' which points to '{sharedDataUrlRedirectTarget}'")

            # actually alter the dedicated.yaml, changing or adding the shareddataurl to what we just created
            sharedDataUrl = f"_{sharedDataUrl}"
            # check if the configuration of the dedicated yaml (we will not make any changes to it) has the auto zip url configured properly
            self.checkDedicatedYamlHasAutoZipUrl(sharedDataUrl)

        def NoOp(*args):
            raise KeyboardInterrupt()
        try:
            signal.signal(signal.SIGINT, NoOp)
            log.info(f"Press CTRL+C to stop the server.")
            self.serve(zipFiles)
        except KeyboardInterrupt:
            log.info(f"SharedData server shutting down.")
        finally:
            log.info(f"SharedData server stopped serving. Total downloads: {ThrottledHandler.globalZipDownloads}")

    def checkDedicatedYamlHasAutoZipUrl(self, expectedConfiguration):
        """
        check that the dedicated yaml has the auto zip url configured properly, and warn about it if not
        """
        if self.config.dedicatedConfig.GameConfig.SharedDataURL == expectedConfiguration:
            log.debug(f"The dedicated yaml has the correct SharedDataURL configuration: '{self.config.dedicatedConfig.GameConfig.SharedDataURL}'.")
        else:
            dedicatedYamlPath = Path(self.config.paths.install).joinpath(self.config.server.dedicatedYaml).resolve()
            log.warn(f"The dedicated yaml '{dedicatedYamlPath}' has an incorrect SharedDataURL configuration: '{self.config.dedicatedConfig.GameConfig.SharedDataURL}'. Expected: '{expectedConfiguration}'")
    
    def replaceInTemplate(self, content: str, placeholder, value):
        if value:
            return content.replace(placeholder, str(value))
        else:
            return content.replace(placeholder, "")
    
    def prepareIndexHtml(self):
        # copy the index.template.html into the wwwroot folder and replace placeholders
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        indexTemplateFilePath = Path("index.template.html").resolve()
        content = indexTemplateFilePath.read_text()
        content = self.replaceInTemplate(content, "$SHAREDDATAZIPFILENAME", self.config.downloadtool.manualZipName)
        content = self.replaceInTemplate(content, "$CACHEFOLDERNAME", self.getCacheFolderName())
        content = self.replaceInTemplate(content, "$SRV_NAME", self.config.dedicatedConfig.ServerConfig.Srv_Name)
        content = self.replaceInTemplate(content, "$SRV_DESCRIPTION", self.config.dedicatedConfig.ServerConfig.Srv_Description)
        content = self.replaceInTemplate(content, "$SRV_PASSWORD", self.config.dedicatedConfig.ServerConfig.Srv_Password)
        content = self.replaceInTemplate(content, "$SRV_MAXPLAYERS", self.config.dedicatedConfig.ServerConfig.Srv_MaxPlayers)
        content = self.replaceInTemplate(content, "$SRV_PORT", self.config.dedicatedConfig.ServerConfig.Srv_Port)
        content = self.replaceInTemplate(content, "$SRV_IP", Tools.getOwnIp(self.config))
        content = self.replaceInTemplate(content, "$MAXALLOWEDSIZECLASS", self.config.dedicatedConfig.ServerConfig.MaxAllowedSizeClass)
        content = self.replaceInTemplate(content, "$PLAYERLOGINPARALLELCOUNT", self.config.dedicatedConfig.ServerConfig.PlayerLoginParallelCount)
        content = self.replaceInTemplate(content, "$PLAYERLOGINFULLSERVERQUEUECOUNT", self.config.dedicatedConfig.ServerConfig.PlayerLoginFullServerQueueCount)
        
        indexFilePath = wwwroot.joinpath("index.html").resolve()
        if indexFilePath.exists():
            FsTools.deleteFile(indexFilePath)
        indexFilePath.write_text(content)
        log.debug(f"Created index.html at '{indexFilePath}'")

    def moveSharedDataZipFilesToWwwroot(self, zipFiles: List[ZipFile]) -> List[ZipFile]:
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        if not wwwroot.exists():
            FsTools.createDir(wwwroot)

        for zipFile in zipFiles:
            wwwrootZipFilePath = wwwroot.joinpath(zipFile.name).resolve()
            if wwwrootZipFilePath.exists():
                log.debug(f"Deleting old zip file at '{wwwrootZipFilePath}'")
                FsTools.deleteFile(wwwrootZipFilePath)
            log.debug(f"Moving zip file '{zipFile.path}' to '{wwwroot}'")
            shutil.move(zipFile.path, wwwroot)
            log.debug(f"result of zip creation: '{wwwrootZipFilePath}'")
            zipFile.wwwrootPath = wwwrootZipFilePath
        return zipFiles
    
    def findUniqueGameId(self):
        """
        return the unique game id from the first found log file that contains that string.

        This is the line in Logs/4243/Dedicated_*.log
        16-19:45:13.388 21_45 -LOG- Mode=currentId, GameSeed=42069420, UniqueId=1519611569, EntityId=5001
        """
        # find gameserver logfile and extract unique game id
        buildNumber = self.dedicatedServer().getBuildNumber()
        logFilePattern = "Dedicated_*.log"
        logFileDirectoryPath = self.config.paths.install.joinpath(f"Logs").joinpath(buildNumber).resolve()
        log.debug(f"Trying to extract unique game id from logfiles in '{logFileDirectoryPath}' with pattern '{logFilePattern}'")
        for possiblePath in glob.glob(root_dir=logFileDirectoryPath, pathname=logFilePattern, recursive=True):
            logFilePath = Path(logFileDirectoryPath).joinpath(possiblePath).resolve()
            if logFilePath.exists():
                log.debug(f"Trying to extract unique game id from logfile '{logFilePath}'")
                with open(logFilePath, 'r') as f:
                    for line in f:
                        if "UniqueId" in line:
                            # extract unique game id from logline, which is the number after the 'UniqueId=' string
                            uniqueGameId = re.search(r"UniqueId=(\d+)", line).group(1)
                            return uniqueGameId
        log.debug(f"Did not find unique game id in any of the {logFilePattern} files in '{logFileDirectoryPath}'. You may need to start the server at least once so esm can find out the id.")
        return None
    
    def getUniqueGameId(self):
        """
        return the unique game id from context, or find it via #findUniqueGameId()
        """
        if not self.config.context.get("uniqueGameId"):
            self.config.context["uniqueGameId"] = self.findUniqueGameId()
        return self.config.context.get("uniqueGameId")
    
    def getCacheFolderName(self):
        """
        constructs the cache folder name with following pattern {gamename}_{serverip}_{unique game id}
        Unless the cache folder name override is active, then just return what has been configured
        """
        if self.config.downloadtool.useCustomCacheFolderName:
            return self.config.downloadtool.customCacheFolderName

        gameName = self.config.dedicatedConfig.GameConfig.GameName
        serverIp = Tools.getOwnIp(self.config)
        uniqueGameId = self.getUniqueGameId()
        if uniqueGameId:
            cacheFolderName = f"{gameName}_{serverIp}_{uniqueGameId}"
            log.debug(f"Generated cache folder name '{cacheFolderName}'")
            return cacheFolderName
        else:
            log.debug(f"Could not determine unique game id. Using default cache folder name '{self.config.downloadtool.customCacheFolderName}'")
            return self.config.downloadtool.customCacheFolderName

    def createSharedDataZipFiles(self, pathToScenarioFolder: Path) -> List[ZipFile]:
        # just using something smaller for debugging
        #pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData/Content/Extras")
        pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData")

        if not pathToSharedDataFolder.exists():
            log.warning(f"Path to the shared data in the games scenario folder '{pathToSharedDataFolder}' does not exist. Please check the configuration.")
            return
        
        tempFolder = Path(self.config.downloadtool.tempFolder).resolve()
        if tempFolder.exists():
            log.debug(f"deleting old temporary folder '{tempFolder}'")
            FsTools.deleteDir(tempFolder, True)
        FsTools.createDir(tempFolder)

        cacheFolderName = self.getCacheFolderName()
        cacheFolder = tempFolder.joinpath(cacheFolderName)

        FsTools.createDir(cacheFolder)
        log.debug(f"Copying files from '{pathToSharedDataFolder}' to cacheFolder '{cacheFolder}'")
        FsTools.copyDir(source=pathToSharedDataFolder, destination=cacheFolder)
        log.debug(f"Created cachefolder '{cacheFolder}'")

        # increase the modification timestamps of all files by 12 hours
        self.increaseModificationTimestamps(cacheFolder)
        
        # create manual zip from the cacheFolder
        log.debug(f"Creating manual zip from tempFolder '{tempFolder}' with name '{self.config.downloadtool.manualZipName}'")
        manualZipFile = self.createZipFile(tempFolder, self.config.downloadtool.manualZipName)
        zipFiles = [manualZipFile]

        if self.config.downloadtool.useSharedDataURLFeature:
            # create auto zip from the folder
            subFolder = tempFolder.joinpath(cacheFolderName)
            autoZipName = f"{self.config.downloadtool.autoZipName.split(".")[0]}_{time.strftime('%Y%m%d_%H%M%S')}.zip"
            log.debug(f"Creating auto zip from folder '{subFolder}' with name '{autoZipName}'")
            autoZipFile = self.createZipFile(subFolder, autoZipName)
            zipFiles = [manualZipFile, autoZipFile]
        return zipFiles

    def createZipFile(self, folder: Path, zipFileName):
        # remove the extension from the filename to get the name of the zip file
        zipNameNoExtension = zipFileName.split(".")[0]
        zipResult = shutil.make_archive(zipNameNoExtension, 'zip', folder)
        zipPath = Path(zipResult).resolve()
        zipfileSize = zipPath.stat().st_size
        return ZipFile(zipFileName, zipPath, zipfileSize, 0, None)

    def increaseModificationTimestamps(self, cacheFolder):
        """
        increase the modification timestamps of all files in cachefolder by whatever value was set in the config
        """
        timeDifference = self.config.downloadtool.timeToAddToModificationTimestamps
        for root, dirs, files in os.walk(cacheFolder):
            for file in files:
                path = os.path.join(root, file)
                currentMTime = os.path.getmtime(path)
                newMTime = currentMTime + timeDifference
                os.utime(path, (newMTime, newMTime))
        timeDiffHuman = humanize.naturaldelta(timeDifference)
        log.debug(f"Altered all files in cachefolder '{cacheFolder}', added {timeDiffHuman} to their last modified timestamps.")
    
    def serve(self, zipFiles: List[ZipFile]):

        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        serverPort = self.config.downloadtool.serverPort
        handler = ThrottledHandler
        ThrottledHandler.rootDirectory = wwwroot.resolve() # this is the root of the webserver
        ThrottledHandler.globalBandwidthLimit = self.config.downloadtool.maxGlobalBandwith
        ThrottledHandler.clientBandwidthLimit = self.config.downloadtool.maxClientBandwith
        ThrottledHandler.rateLimit = parse(self.config.downloadtool.rateLimit)
        ThrottledHandler.autoZipPath = self.config.downloadtool.autoZipName
        ThrottledHandler.zipFiles = zipFiles
        try:
            with socketserver.ThreadingTCPServer(("", serverPort), handler) as httpd:
                httpd.serve_forever()        
        except Exception as e:
            log.debug(e)


class ThrottledHandler(http.server.SimpleHTTPRequestHandler):

    # limit requests / time window per client ip
    rateLimit = parse("10 per minute")
    rateLimiter = strategies.MovingWindowRateLimiter(storage.MemoryStorage())

    # default bandwith limits
    clientBandwidthLimit = 30*1024*1024 # default to 30MB/s
    globalBandwidthLimit = 50*1024*1024 # default to 50MB/s

    # global properties
    globalStartTime = time.time()
    globalBytesSent = 0
    globalZipDownloads = 0
    
    # Lock for thread safety when accessing the global properties
    globalPropertyLock = threading.Lock()

    # www root
    rootDirectory = None

    # contains the list zip files to handle
    zipFiles = []

    # path that will redirect to the autozip
    autoZipPath = "SharedData.zip"

    # allowed default assets for downloads
    defaultAssets = ['index.html', 'favicon.ico', 'styles.css']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ThrottledHandler.rootDirectory, **kwargs)

    def hitRateLimit(self):
        client_ip = self.client_address[0]
        # rate limit check, send 429 if the client is trying to make too many requests
        if not self.rateLimiter.hit(self.rateLimit, "global", client_ip):
            self.send_error(429, f"Rate limit exceeded. Go away.")
            log.warn(f"client ip {client_ip} exceeded the rate limit, requested path '{self.path}'")
            return True
        return False
    
    def redirectSharedDataUrlToAutozip(self):
        filename = self.path[1:]
        if filename == self.autoZipPath:
            zipFileNameNoExt = self.autoZipPath.split(".")[0]
            autoZipFile = list(filter(lambda x: x.name.startswith(zipFileNameNoExt), self.zipFiles))[0]
            #self.send_response_only(302)
            self.send_response_only(301)
            self.send_header("Location", f"/{autoZipFile.name}")
            self.end_headers()
            return True
        return False
    
    def redirectToIndex(self):
        filename = self.path[1:]
        if filename == "":
            self.send_response_only(301)
            self.send_header("Location", "/index.html")
            self.end_headers()
            return True
        return False
    
    def pathNotInWhitelist(self):
        filename = self.path[1:]
        zipFileNames = [x.name for x in ThrottledHandler.zipFiles]
        if filename not in ThrottledHandler.defaultAssets and filename not in zipFileNames:
            self.send_response_only(404, "There's nothing else to see here. Go away.")
            self.end_headers()
            self.log_request(404)
            return True
        return False
    
    def fileDoesNotExist(self):
        file = self.directory + self.path
        if not Path(file).exists():
            self.send_response_only(404, "Didn't find a thing.")
            self.end_headers()
            self.log_request(404)
            log.warn(f"file '{file}' not found, but is listed as default asset, make sure its still there.")
            return True
        return False
    
    def do_HEAD(self) -> None:
        if self.redirectSharedDataUrlToAutozip(): return
        if self.pathNotInWhitelist(): return
        if self.fileDoesNotExist(): return
        
        self.send_response_only(200, "OK")
        self.end_headers()
        self.log_request(200)

    def do_GET(self) -> None:
        if self.redirectToIndex(): return
        if self.redirectSharedDataUrlToAutozip(): return
        if self.hitRateLimit(): return
        if self.pathNotInWhitelist(): return
        if self.fileDoesNotExist(): return

        file = self.directory + self.path
        try:
            return super().do_GET()
        except Exception as ex:
            log.warn(f"Error while serving file {file}: {ex}")

    def getMatchingZipFile(self, path, zipFileList: List['ZipFile']) -> ZipFile:
        """
        returns the according object of the list if the name is in the path
        """
        for zipFile in zipFileList:
            if zipFile.name in path:
                return zipFile
        return None

    def copyfile(self, source, outputfile) -> None:
        # we'll only limit the speed of the zip file, not the rest of the files
        zipFile = self.getMatchingZipFile(self.path, ThrottledHandler.zipFiles)
        if zipFile is None:
            return super().copyfile(source, outputfile)
        
        log.info(f"Client {self.client_address} started downloading the file '{zipFile.name}'.")
        with Timer() as timer:
            self.throttle_copy(source, outputfile, self.clientBandwidthLimit)
        downloadspeed = zipFile.size / timer.elapsedTime.total_seconds()
        with ThrottledHandler.globalPropertyLock:
            ThrottledHandler.globalZipDownloads += 1
            zipFile.downloads += 1
        log.info(f"Client {self.client_address} successfully downloaded the file '{zipFile.name}' in '{humanize.naturaldelta(timer.elapsedTime)}', speed '{humanize.naturalsize(downloadspeed, gnu=False)}/s'. ({zipFile.downloads} specific downloads, {ThrottledHandler.globalZipDownloads} total downloads)")

    def throttle_copy(self, source, outputfile, limit):
        bufsize = 8192 # the smaller, the more often we'll iterate through here
        bytesSent = 0
        startTime = time.time()
        while True:
            buf = source.read(bufsize)
            if not buf:
                break
            outputfile.write(buf)
            bytesSent += len(buf)
            with ThrottledHandler.globalPropertyLock:
                ThrottledHandler.globalBytesSent += len(buf)

            # calculate if we need to sleep to conform the client bandwith limit
            elapsedTime = time.time() - startTime
            expectedTime = bytesSent / limit
            suggestedSleepTimeClient = max(0, expectedTime - elapsedTime)

            # calculate if we need to sleep to conform the client bandwith limit
            elapsedGlobalTime = time.time() - ThrottledHandler.globalStartTime
            expectedGlobalTime = ThrottledHandler.globalBytesSent / ThrottledHandler.globalBandwidthLimit
            suggestedSleepTimeglobal = max(0, expectedGlobalTime - elapsedGlobalTime)

            # sleep the bigger amount of both calculations
            sleepTime = max(suggestedSleepTimeClient, suggestedSleepTimeglobal)
            time.sleep(sleepTime)

    def log_message(self, format: str, *args) -> None:
        message = format % args
        log.debug(f"{self.address_string()} - - [{self.log_date_time_string()}] {message.translate(self._control_char_table)}")

