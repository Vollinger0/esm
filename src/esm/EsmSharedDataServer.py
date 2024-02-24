from functools import cached_property
import logging
from pathlib import Path
import shutil
import signal

from limits import RateLimitItem, RateLimitItemPerSecond
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
import http.server
import socketserver
from limits import storage, strategies, parse
import time

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
        log.info(f"Created SharedData zip file as '{wwwrootZipFilePath}' using the cache folder name '{self.config.downloadtool.cacheFolderName}'")

        # start webserver on configured port and serve the zip and also the index.html that explains how to handle the shared data
        servingUrl = f"http://127.0.0.1:{self.config.downloadtool.port}/{self.config.downloadtool.zipName}.zip"
        log.info(f"Started the download server now. You can now download the shared data from the webserver at '{servingUrl}'")
        def NoOp(*args):
            raise KeyboardInterrupt()
        try:
            signal.signal(signal.SIGINT, NoOp)
            log.info(f"Press CTRL+C to stop the server.")
            self.serve()
        except KeyboardInterrupt:
            log.info(f"SharedData server shutting down.")
            pass
        finally:
            log.info(f"SharedData server stopped serving.")

    def moveSharedDataZipFileToWwwroot(self, resultZipFilePath: Path) -> Path:
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        if not wwwroot.exists():
            FsTools.createDir(wwwroot)

        wwwrootZipFilePath = wwwroot.joinpath(f"{self.config.downloadtool.zipName}.zip").resolve()
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
        log.debug(f"Creating zip from cachefolder '{cacheFolder}' with name '{self.config.downloadtool.zipName}.zip'")
        result = shutil.make_archive(self.config.downloadtool.zipName, 'zip', tempFolder)
        resultZipFilePath = Path(result)
        return resultZipFilePath
    
    def serve(self):
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        zipFileName = f"{self.config.downloadtool.zipName}.zip"
        PORT = self.config.downloadtool.port
        handler = ThrottledHandler
        ThrottledHandler.root_directory = wwwroot.resolve()
        try:
            with socketserver.TCPServer(("", PORT), handler) as httpd:
                httpd.serve_forever()        
        except Exception as e:
            log.debug(e)


# Set the desired bandwidth limit per client (in bytes per second)
client_bandwidth_limit = 2*1024  # 10 KB/s
# Set the desired global server-wide bandwidth limit (in bytes per second)
global_bandwidth_limit = 1024  # 1 KB/s

limiter = strategies.MovingWindowRateLimiter(storage.MemoryStorage())
rateLimit = parse("10 per minute")

class ThrottledHandler(http.server.SimpleHTTPRequestHandler):

    root_directory = ""  # Class variable to store the root directory

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ThrottledHandler.root_directory, **kwargs)

    def do_GET(self) -> None:
        client_ip = self.client_address[0]

        # Rate limit check for the server
        if not limiter.hit(rateLimit, "global", client_ip):
            self.send_error(429, f"Rate limit exceeded. Go away.")
            log.warn(f"client ip {client_ip} exceeded the rate limit, requested path '{self.path}'")
            return

        file = self.directory + self.path
        filename = self.path[1:]
        if not Path(file).exists():
            self.send_error(404, "Nothing to see here. Go away.")
            return
        
        # Throttle the download globally
        with self.throttle_file(file, filename, global_bandwidth_limit):
            try:
                return super().do_GET()
            except Exception as ex:
                log.error(f"Error while serving file {file}: {ex}")
            self.send_error(500, "Here be errors. Go away.")
        
    def copyfile(self, source, outputfile) -> None:
        #return super().copyfile(source, outputfile)
        return self.throttle_copy(source, outputfile, client_bandwidth_limit)

    def throttle_copy(self, source, outputfile, limit):
        bufsize = 8192  # Adjust this value based on your desired bandwidth limit
        bytes_sent = 0
        start_time = time.time()

        while True:
            buf = source.read(bufsize)
            if not buf:
                break
            outputfile.write(buf)
            bytes_sent += len(buf)
            elapsed_time = time.time() - start_time
            expected_time = bytes_sent / limit
            sleep_time = max(0, expected_time - elapsed_time)
            time.sleep(sleep_time)

    def throttle_file(self, file, filename, limit):
        source = open(file, 'rb')
        self.send_response(200)
        self.send_header("Content-type", "application/octet-stream")
        self.send_header("Content-Disposition", f"attachment; filename={filename}")
        self.end_headers()
        return ThrottleContext(source, self.wfile, limit)

class ThrottleContext:
    def __init__(self, source, outputfile, limit):
        self.source = source
        self.outputfile = outputfile
        self.limit = limit

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.source.close()

    def read(self, size):
        return self.source.read(size)

    def write(self, data):
        self.outputfile.write(data)