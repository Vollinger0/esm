import logging
import socket
import urllib.request
import humanize
import http.server
import threading
import time
import urllib

from typing import Dict
from urllib.error import URLError
from limits import parse, storage, strategies
from pathlib import Path
from esm import Tools
from esm.Tools import Timer

log = logging.getLogger(__name__)

class EsmHttpThrottledHandler(http.server.SimpleHTTPRequestHandler):

    # limit requests / time window per client ip
    rateLimit = parse("10 per minute")
    rateLimiter = strategies.MovingWindowRateLimiter(storage.MemoryStorage())
    rateLimitExceptions = []

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
    redirects: Dict[str, str] = None

    # allowed default assets for downloads
    defaultAssets = ['/index.html', '/favicon.ico', '/styles.css']

    # dynamic whitelist
    whitelist = [] 

    # special services where the handler will be proxying requests to the given url, e.g. {"src": "/chatlog/chatlog.json", "dst": "https://haimsterhost.com/chatlog/chatlog.json"}
    proxiedPaths = []

    # keep track of the active connections so we can close them once the application shuts down
    activeConnections: set[socket.socket] = set()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=EsmHttpThrottledHandler.rootDirectory, **kwargs)

    def handle(self) -> None:
        """
            wrap any errors that might occur while handling the request, we don't want stack traces, unless we're in debug mode
        """
        self.activeConnections.add(self.request)
        
        if log.getEffectiveLevel() == logging.DEBUG:
            try:
                return super().handle()
            finally:
                self.activeConnections.discard(self.request)
        
        try:
            return super().handle()
        except Exception as e:
            log.warning(f"error initializing http server: {e}. Probably some bots knocking on the door.")
        finally:
            self.activeConnections.discard(self.request)

    def hitRateLimit(self):
        if self.path in EsmHttpThrottledHandler.rateLimitExceptions: return False
        client_ip = self.client_address[0]
        # rate limit check, send 429 if the client is trying to make too many requests
        if not self.rateLimiter.hit(self.rateLimit, "global", client_ip):
            self.send_error(429, f"Rate limit exceeded. Go away.")
            log.warning(f"client ip {client_ip} exceeded the rate limit, requested path '{self.path}'")
            return True
        return False

    def handleRedirects(self):
        """
        check if the requested path equals any of the configured redirects and redirect to the destination.
        """
        if self.redirects is None: return False
        if len(self.redirects) == 0: return False
        for redirect in self.redirects:
            source = redirect['source']
            destination = redirect['destination']
            code = redirect['code']
            if source == self.path:
                log.debug(f"redirecting {self.path} to {destination} with code {code}")
                self.send_response_only(code)
                self.send_header("Location", f"{destination}")
                self.end_headers()
                self.log_request(code)
                return True
        return False

    def redirectToIndex(self):
        filename = self.path[1:]
        if filename == "":
            log.debug(f"redirecting {self.path} to /index.html")
            self.send_response_only(301)
            self.send_header("Location", "/index.html")
            self.end_headers()
            self.log_request(301)
            return True
        return False

    def pathInWhitelist(self):
        filename = self.path
        if filename in EsmHttpThrottledHandler.defaultAssets:
            #log.debug(f"serving default asset {filename}")
            return True
        
        if filename in EsmHttpThrottledHandler.whitelist:
            #log.debug(f"serving whitelisted asset {filename}")
            return True

        zipFileNames = [f"/{x.name}" for x in EsmHttpThrottledHandler.zipFiles]
        if filename in zipFileNames:
            #log.debug(f"serving zip file {filename}")
            return True

        for proxiedPath in EsmHttpThrottledHandler.proxiedPaths:
            if filename.startswith(proxiedPath['path']):
                log.info(f"serving proxied path {filename}")
                return True
            
        log.debug(f"not serving {filename}")
        self.send_response_only(404, "There's nothing else to see here. Go away.")
        self.end_headers()
        self.log_request(404)
        return False

    def fileDoesNotExist(self):
        file = self.directory + self.path
        if not Path(file).exists():
            self.send_response_only(404, "Didn't find a thing.")
            self.end_headers()
            self.log_request(404)
            log.warning(f"file '{file}' not found, but is listed as default asset, make sure its still there.")
            return True
        return False

    def do_HEAD(self) -> None:
        if self.handleRedirects(): return
        if not self.pathInWhitelist(): return
        if self.fileDoesNotExist(): return

        self.send_response_only(200, "OK")
        self.end_headers()
        self.log_request(200)

    def do_GET(self) -> None:
        if self.redirectToIndex(): return
        if self.hitRateLimit(): return
        if self.handleRedirects(): return
        if not self.pathInWhitelist(): return
        if self.handleProxiedPath(): return
        if self.fileDoesNotExist(): return

        try:
            log.debug(f"Client {self.client_address} requested file '{self.path}'.")
            return super().do_GET()
        except Exception as ex:
            log.warning(f"Error while serving file {self.path}: {ex}")

    def handleProxiedPath(self):
        # get the entry that matches the self.path from the proxiedPaths
        for proxiedPath in EsmHttpThrottledHandler.proxiedPaths:
            if self.path.startswith(proxiedPath['path']):
                # get the line query parameter after the requested path
                query = self.path[len(proxiedPath['path']):].strip("/")
                targetUrl = proxiedPath['target']
                targetUrl += f"{query}"
                #log.debug(f"Client {self.client_address} requested file '{self.path}', proxying to '{targetUrl}'.")
                # Make request to remote server
                try:
                    response = urllib.request.urlopen(targetUrl)
                    # Copy status code and headers
                    self.send_response(response.status)
                    for header, value in response.headers.items():
                        self.send_header(header, value)
                    self.end_headers()
                    
                    # Stream the response body
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                except URLError as e:
                    self.send_error(502, f"Proxy error: {str(e)}")
                except Exception as e:
                    self.send_error(500, f"Internal server error: {str(e)}")                
                return True
        return False
       

    def copyfile(self, source, outputfile) -> None:
        # we'll only limit the speed of the zip file, not the rest of the files
        zipFile = Tools.findZipFileByName(EsmHttpThrottledHandler.zipFiles, containedIn=self.path)
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
