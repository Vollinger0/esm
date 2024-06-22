import logging
import humanize
import http.server
import threading
import time
from esm.DataTypes import ZipFile
from esm.Tools import Timer
from limits import parse, storage, strategies
from pathlib import Path
from typing import List

log = logging.getLogger(__name__)

class EsmHttpThrottledHandler(http.server.SimpleHTTPRequestHandler):

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

    # redirect definition, if set e.g. {"source": "GimmeTheSharedData", "destination": autoZipFile.name, "code": 301}
    redirect = None

    # allowed default assets for downloads
    defaultAssets = ['index.html', 'favicon.ico', 'styles.css']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=EsmHttpThrottledHandler.rootDirectory, **kwargs)

    def hitRateLimit(self):
        client_ip = self.client_address[0]
        # rate limit check, send 429 if the client is trying to make too many requests
        if not self.rateLimiter.hit(self.rateLimit, "global", client_ip):
            self.send_error(429, f"Rate limit exceeded. Go away.")
            log.warn(f"client ip {client_ip} exceeded the rate limit, requested path '{self.path}'")
            return True
        return False

    def redirectToDestination(self):
        """
        check if the requested path is the redirect source path and if so redirect to the corresponding destination
        """
        if self.redirect is None: return False
        source = self.redirect['source']
        destination = self.redirect['destination']
        code = self.redirect['code']
        if source == self.path[1:]:
            self.send_response_only(code)
            self.send_header("Location", f"/{destination}")
            self.end_headers()
            self.log_request(code)
            return True
        return False

    def redirectToIndex(self):
        filename = self.path[1:]
        if filename == "":
            self.send_response_only(301)
            self.send_header("Location", "/index.html")
            self.end_headers()
            self.log_request(301)
            return True
        return False

    def pathNotInWhitelist(self):
        filename = self.path[1:]
        zipFileNames = [x.name for x in EsmHttpThrottledHandler.zipFiles]
        if filename not in EsmHttpThrottledHandler.defaultAssets and filename not in zipFileNames:
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
        if self.redirectToDestination(): return
        if self.pathNotInWhitelist(): return
        if self.fileDoesNotExist(): return

        self.send_response_only(200, "OK")
        self.end_headers()
        self.log_request(200)

    def do_GET(self) -> None:
        if self.redirectToIndex(): return
        if self.hitRateLimit(): return
        if self.redirectToDestination(): return
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
        zipFile = self.getMatchingZipFile(self.path, EsmHttpThrottledHandler.zipFiles)
        if zipFile is None:
            return super().copyfile(source, outputfile)

        log.info(f"Client {self.client_address} started downloading the file '{zipFile.name}'.")
        with Timer() as timer:
            self.throttle_copy(source, outputfile, self.clientBandwidthLimit)
        downloadspeed = zipFile.size / timer.elapsedTime.total_seconds()
        with EsmHttpThrottledHandler.globalPropertyLock:
            EsmHttpThrottledHandler.globalZipDownloads += 1
            zipFile.downloads += 1
        log.info(f"Client {self.client_address} successfully downloaded the file '{zipFile.name}' in '{humanize.naturaldelta(timer.elapsedTime)}', speed '{humanize.naturalsize(downloadspeed, gnu=False)}/s'. ({zipFile.downloads} specific downloads, {EsmHttpThrottledHandler.globalZipDownloads} total downloads)")

    def throttle_copy(self, source, outputfile, limit):
        bufsize = 8192 # the smaller, the more often we'll iterate through here so don't use a too small value
        bytesSent = 0
        startTime = time.time()
        while True:
            buf = source.read(bufsize)
            if not buf:
                break
            outputfile.write(buf)
            bytesSent += len(buf)
            with EsmHttpThrottledHandler.globalPropertyLock:
                EsmHttpThrottledHandler.globalBytesSent += len(buf)

            # calculate if we need to sleep to conform the client bandwith limit
            elapsedTime = time.time() - startTime
            expectedTime = bytesSent / limit
            suggestedSleepTimeClient = max(0, expectedTime - elapsedTime)

            # calculate if we need to sleep to conform the client bandwith limit
            elapsedGlobalTime = time.time() - EsmHttpThrottledHandler.globalStartTime
            expectedGlobalTime = EsmHttpThrottledHandler.globalBytesSent / EsmHttpThrottledHandler.globalBandwidthLimit
            suggestedSleepTimeglobal = max(0, expectedGlobalTime - elapsedGlobalTime)

            # sleep the bigger amount of both calculations
            sleepTime = max(suggestedSleepTimeClient, suggestedSleepTimeglobal)
            time.sleep(sleepTime)

    def log_message(self, format: str, *args) -> None:
        message = format % args
        log.debug(f"{self.address_string()} - - [{self.log_date_time_string()}] {message.translate(self._control_char_table)}")