import logging
import shutil
import signal
import threading
import humanize
import http.server
import socketserver
import time
from functools import cached_property
from pathlib import Path
from limits import storage, strategies, parse
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import Timer

log = logging.getLogger(__name__)

@Service
class EsmSharedDataServer:

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config

    def start(self):
        scenarioName = self.config.dedicatedConfig.GameConfig.CustomScenario
        pathToScenarioFolder = Path(f"{self.config.paths.install}/Content/Scenarios/{scenarioName}").resolve()

        log.info(f"Creating new shared data zip file from the current configured scenario at '{pathToScenarioFolder}'")
        resultZipFilePath = self.createSharedDataZipFile(pathToScenarioFolder)
        wwwrootZipFilePath = self.moveSharedDataZipFileToWwwroot(resultZipFilePath)
        self.prepareIndexHtml()

        zipFileSize = Path(wwwrootZipFilePath).stat().st_size
        log.info(f"Created SharedData zip file as '{wwwrootZipFilePath}' using the cache folder name '{self.config.downloadtool.cacheFolderName}' with a size of {humanize.naturalsize(zipFileSize, gnu=True)}.")

        # start webserver on configured port and serve the zip and also the index.html that explains how to handle the shared data
        myHostIp = "127.0.0.1"
        servingUrl = f"http://{myHostIp}:{self.config.downloadtool.serverPort}/{self.config.downloadtool.zipName}.zip"
        log.info(f"Server configured to allow max {humanize.naturalsize(self.config.downloadtool.maxGlobalBandwith, gnu=False)}/s in total network bandwidth.")
        log.info(f"Server configured to allow max {humanize.naturalsize(self.config.downloadtool.maxClientBandwith, gnu=False)}/s network bandwith per connection.")
        log.info(f"Started download server. Shared data zip file can be downloaded at: '{servingUrl}'")
        def NoOp(*args):
            raise KeyboardInterrupt()
        try:
            signal.signal(signal.SIGINT, NoOp)
            log.info(f"Press CTRL+C to stop the server.")
            self.serve(zipFileSize)
        except KeyboardInterrupt:
            log.info(f"SharedData server shutting down.")
        finally:
            log.info(f"SharedData server stopped serving.")

    def prepareIndexHtml(self):
        # copy the index.template.html into the wwwroot folder and replace $SHAREDDATAZIPFILENAME with the name of the zip file
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        indexTemplateFilePath = Path("index.template.html").resolve()
        content = indexTemplateFilePath.read_text()
        newContent = content.replace("$SHAREDDATAZIPFILENAME", self.config.downloadtool.zipName)
        indexFilePath = wwwroot.joinpath("index.html").resolve()
        if indexFilePath.exists():
            FsTools.deleteFile(indexFilePath)
        indexFilePath.write_text(newContent)
        log.debug(f"Created index.html at '{indexFilePath}'")

    def moveSharedDataZipFileToWwwroot(self, resultZipFilePath: Path) -> Path:
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        if not wwwroot.exists():
            FsTools.createDir(wwwroot)

        wwwrootZipFilePath = wwwroot.joinpath(self.config.downloadtool.zipName).resolve()
        if wwwrootZipFilePath.exists():
            log.debug(f"Deleting old zip file at '{wwwrootZipFilePath}'")
            FsTools.deleteFile(wwwrootZipFilePath)
        log.debug(f"Moving zip file '{resultZipFilePath}' to '{wwwroot}'")
        shutil.move(resultZipFilePath, wwwroot)
        log.debug(f"result of zip creation: '{wwwrootZipFilePath}'")
        return wwwrootZipFilePath

    def createSharedDataZipFile(self, pathToScenarioFolder: Path) -> Path:
        # just using something smaller for debugging
        pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData/Content/Extras")
        #pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData")

        if not pathToSharedDataFolder.exists():
            log.warning(f"Path to the shared data in the games scenario folder '{pathToSharedDataFolder}' does not exist. Please check the configuration.")
            return
        
        tempFolder = Path(self.config.downloadtool.tempFolder).resolve()
        if tempFolder.exists():
            log.debug(f"deleting old temporary folder '{tempFolder}'")
            FsTools.deleteDir(tempFolder, True)
        FsTools.createDir(tempFolder)
        cacheFolder = tempFolder.joinpath(self.config.downloadtool.cacheFolderName)
        FsTools.createDir(cacheFolder)
        
        log.debug(f"Copying files from '{pathToSharedDataFolder}' to cachefolder '{cacheFolder}'")
        FsTools.copyDir(source=pathToSharedDataFolder, destination=cacheFolder)
        
        # create zip from the cacheFolder
        log.debug(f"Creating zip from cachefolder '{cacheFolder}' with name '{self.config.downloadtool.zipName}'")
        # remove the extension from the filename to get the name of the zip file
        zipNameNoExtension = self.config.downloadtool.zipName.split(".")[0]
        result = shutil.make_archive(zipNameNoExtension, 'zip', tempFolder)
        resultZipFilePath = Path(result)
        return resultZipFilePath
    
    def serve(self, zipFileSize: int):
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        serverPort = self.config.downloadtool.serverPort
        handler = ThrottledHandler
        ThrottledHandler.rootDirectory = wwwroot.resolve() # this is the root of the webserver
        ThrottledHandler.globalBandwidthLimit = self.config.downloadtool.maxGlobalBandwith
        ThrottledHandler.clientBandwidthLimit = self.config.downloadtool.maxClientBandwith
        ThrottledHandler.rateLimit = parse(self.config.downloadtool.rateLimit)
        ThrottledHandler.zipFileName = self.config.downloadtool.zipName
        ThrottledHandler.zipFileSize = zipFileSize
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

    # the name of the relevant download, used to log, and be able to count them
    zipFileName = None
    # the size of the relevant download, for logging purposes
    zipFileSize = 0

    # allowed default assets for downloads
    defaultAssets = ['index.html', 'favicon.ico', 'style.css']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ThrottledHandler.rootDirectory, **kwargs)

    def do_GET(self) -> None:
        client_ip = self.client_address[0]

        # rate limit check, send 429 if the client is trying to make too many requests
        if not self.rateLimiter.hit(self.rateLimit, "global", client_ip):
            self.send_error(429, f"Rate limit exceeded. Go away.")
            log.warn(f"client ip {client_ip} exceeded the rate limit, requested path '{self.path}'")
            return
        
        filename = self.path[1:]
        if filename == "":
            self.send_response_only(301)
            self.send_header("Location", "/index.html")
            self.end_headers()
            return

        if filename not in ThrottledHandler.defaultAssets and filename != ThrottledHandler.zipFileName:
            #self.send_error(404, "There's nothing else to see here. Go away.")
            self.send_response_only(404, "There's nothing else to see here. Go away.")
            self.end_headers()
            self.log_request(404)
            return

        file = self.directory + self.path
        if not Path(file).exists():
            #self.send_error(404, "Didn't find a thing.")
            self.send_response_only(404, "Didn't find a thing.")
            self.end_headers()
            self.log_request(404)
            log.warn(f"file '{file}' not found, but is listed as default asset, make sure its still there.")
            return
        
        try:
            return super().do_GET()
        except Exception as ex:
            log.warning(f"Error while serving file {file}: {ex}")

        
    def copyfile(self, source, outputfile) -> None:
        # we'll only limit the speed of the zip file, not the rest of the files
        if ThrottledHandler.zipFileName not in self.path:
            return super().copyfile(source, outputfile)

        log.info(f"Client {self.client_address} started downloading the file '{self.zipFileName}'.")
        with Timer() as timer:
            self.throttle_copy(source, outputfile, self.clientBandwidthLimit)
        downloadspeed = ThrottledHandler.zipFileSize / timer.elapsedTime.total_seconds()
        with ThrottledHandler.globalPropertyLock:
            ThrottledHandler.globalZipDownloads += 1
        log.info(f"Client {self.client_address} successfully downloaded the file '{self.zipFileName}', speed {humanize.naturalsize(downloadspeed, gnu=True)}/s. ({ThrottledHandler.globalZipDownloads} total)")


    def throttle_copy(self, source, outputfile, limit):
        bufsize = 4096 # the smaller, the more often we'll iterate through here
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

