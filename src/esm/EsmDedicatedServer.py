from enum import Enum
import time
import logging
import psutil
import re
import requests
from functools import cached_property
from pathlib import Path, PurePath
from datetime import datetime
from esm.ConfigModels import MainConfig
from esm.exceptions import AdminRequiredException
from esm.EsmConfigService import EsmConfigService
from esm.EsmEmpRemoteClientService import EsmEmpRemoteClientService
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

class StartMode(str, Enum):
    DIRECT = "direct" # will bypass the launcher and use the dedicated exe directly. Use this mode if you need to run multiple instances of the server on one machine.
    LAUNCHER = "launcher" # will use the launcher to start the game

@Service
class EsmDedicatedServer:
    """
    Represents the dedicated server (executable), with the ability to start, stop, check if its running, etc.

    contains constants for the different startmodes and gfxmodes
    """
    process = None
    gfxMode: bool = None

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config

    @cached_property
    def ramdiskManager(self) -> EsmRamdiskManager:
        return ServiceRegistry.get(EsmRamdiskManager)

    @cached_property
    def emprcClient(self) -> EsmEmpRemoteClientService:
        return ServiceRegistry.get(EsmEmpRemoteClientService)
    
    def __init__(self):
        self.gfxMode = self.config.server.gfxMode

    def startServer(self, checkForRamdisk=True, checkForDiskSpace=True):
        """
        Start the server with the configured mode.
        The called methods will wait until the respective process is started

        If the server started successfully, the psutil process is returned.
        """
        if checkForRamdisk:
            self.ramdiskManager.existsRamdisk()
        if checkForDiskSpace:
            self.assertEnoughFreeDiskspace()

        self.assertSharedDataURLIsAvailable()

        if (self.config.server.startMode == StartMode.DIRECT):
            log.debug(f"startMode is {StartMode.DIRECT}")
            return self.startServerDirectMode()
        else:
            log.debug(f"startMode is {StartMode.LAUNCHER}")
            return self.startServerLauncherMode()
        
    def startServerDirectMode(self):
        """
        Starts the server using the dedicated exe, bypassing the launcher. This enables us to be able to identify the process id directly
        This, in turn, allows that there can be multiple instances of the dedicated exe running on the same machine

        Method returns as soon as the process is started and its process info is returned.
        """
        arguments = self.getCommandForDirectMode()
        arguments2String = lambda arguments: " ".join(str(element) if isinstance(element, Path) else element for element in arguments)
        log.info(f"Starting server with: '{arguments2String(arguments)}' in directory '{self.config.paths.install}'")
        if not self.config.general.debugMode:
            # we do not use subprocess.run here, since we'll need the PID later and only psutil.Popen provides that. <- unless you just keep the process object, since it provides all methods.           
            process = psutil.Popen(args=arguments)
        else:
            log.debug(f"debug mode enabled!")
        log.debug(f"Process returned: {process}")
        self.process = process
        return process

    def getCommandForDirectMode(self):
        pathToExecutable = Path(f"{self.config.paths.install}/{self.config.foldernames.dedicatedserver}/{self.config.filenames.dedicatedExe}").resolve()
        arguments = [pathToExecutable]
        if self.gfxMode:
            log.debug(f"gfxMode is true")
        else:
            log.debug(f"gfxMode is false")
            arguments.append("-batchmode")
            arguments.append("-nographics")
        arguments.append("-dedicated")
        arguments.append(self.config.server.dedicatedYaml)
        arguments.append("-logFile")
        arguments.append(self.createLogFileName())
        return arguments
    
    def startServerLauncherMode(self):
        """
        Start the game using the default empyrion launcher, returns the psutil process of the dedicated exe if successful

        Method returns as soon as the process of the dedicated server was found and its process info is returned, otherwise exceptions are passed.
        """
        arguments = self.getCommandForLauncherMode()
        arguments2String = lambda arguments: " ".join(str(element) if isinstance(element, Path) else element for element in arguments)
        log.info(f"Starting server with: '{arguments2String(arguments)}' in directory '{self.config.paths.install}'")
        if not self.config.general.debugMode:
            # we do not use subprocess.run here, since we use this in the direct mode too and we want the process field to be of the same type.
            process = psutil.Popen(args=arguments, cwd=self.config.paths.install)
            # wait for the *launcher* process to end, not the dedicated server.
            process.wait()
        else:
            log.debug(f"debug mode enabled!")
        log.debug(f"launcher returned: {process}")
        
        # give the dedicated process a few seconds before we start to look for it
        time.sleep(3)
        # find the dedicated process and remember its process info
        self.process = self.findDedicatedExeProcess(timeoutInSeconds=self.config.server.launcherMaxStartupTimeout, checkIntervalInSeconds=3, raiseException=True)
        log.debug(f"found process of dedicated server: {self.process}")
        return self.process

    def findDedicatedExeProcess(self, timeoutInSeconds=None, raiseException=False, checkIntervalInSeconds=None):
        """
        will actually search for the dedicated exe process and return that
        """
        if timeoutInSeconds is not None and timeoutInSeconds > 0:
            return self.findProcessByNameWithTimeout(self.config.filenames.dedicatedExe, timeout=timeoutInSeconds, raiseException=raiseException, checkIntervalInSeconds=checkIntervalInSeconds)
        else:
            return self.findProcessByName(self.config.filenames.dedicatedExe, raiseException=raiseException)

    def getCommandForLauncherMode(self):
        launcherExeFileName = self.config.filenames.launcherExe
        pathToExecutable = self.config.paths.install.joinpath(launcherExeFileName).resolve()
        if self.gfxMode:
            log.debug(f"gfxMode is true")
            startDedi = "-startDediWithGfx"
        else:
            log.debug(f"gfxMode is false")
            startDedi = "-startDedi"
        arguments = [pathToExecutable, startDedi, "-dedicated", self.config.server.dedicatedYaml]
        return arguments
    
    def createLogFileName(self):
        """ 
        reproduce a logfile name like ../Logs/$buildNumber/Dedicated_YYMMDD-HHMMSS-xx.log. 
        xx is unknown, so it can be omited for now

        Since the PF-Servers will always use "../Logs/", no matter what working dir you call the dedicated exe from, we'll hard code this here!
        """
        buildNumber = self.getBuildNumber()
        formattedDate = self.getFormattedDate()
        logFileName = f"../Logs/{buildNumber}/Dedicated_{formattedDate}.log"
        return logFileName
    
    def getBuildNumber(self):
        """
        get the numeric build number from the first line in the file 'BuildNumber.txt' in the installdir
        """
        buildNumberFilePath = self.config.paths.install.joinpath(self.config.filenames.buildNumber).resolve()
        if not buildNumberFilePath.exists() or not buildNumberFilePath.is_file():
            raise FileNotFoundError(f"BuildNumber.txt not found at '{buildNumberFilePath}'")
        with open(buildNumberFilePath, "r") as buildNumberFilePath:
            firstLine = buildNumberFilePath.readline()
            cleanedString = re.sub(r'[^a-zA-Z0-9]', '', firstLine)
            return cleanedString
        
    def getFormattedDate(self, date=None):
        if date is None:
            date = datetime.now()
        formattedDate = date.strftime("%y%m%d-%H%M%S")
        return formattedDate

    def findProcessByName(self, processName, raiseException=False):
        """
        will search for a process that contains or is like the provided processName
        """
        processes = self.getProcessByName(processName)
        processCount = len(processes)
        if processCount == 1:
            process = processes[0]
            log.debug(f"found process by name '{processName}': {process}")
            return process
        elif processCount > 1:
            # exit the script with an error to avoid further breaking
            #log.warn(f"found {processCount} named {processName}. This might be bad at this point.")
            if raiseException:
                raise Exception(f"Found {processCount} processes named {processName}. This will probably break this script. If you want to run multiple instances of the game, use the startmode 'direct'. Otherwise you'll probably want to stop or kill the remaining process first.")
            else:
                return None
        else:
            log.debug("no process found")
            return None

    def findProcessByNameWithTimeout(self, processName, timeout, checkIntervalInSeconds, raiseException=True):
        """
        will search for a process that contains or is like the provided processName
        It will do that every few seconds in a loop until either a process was found
        or the the timeout is reached, raising a TimeoutError
        """
        timePassed = 0
        while timePassed < timeout:
            process = self.findProcessByName(processName, raiseException)
            if process is None:
                time.sleep(checkIntervalInSeconds)
                timePassed=timePassed + checkIntervalInSeconds
            else:
                return process
        # at this point the timeout was reached and we didn't find any processes.
        if raiseException:
            # exit the script with an error to avoid more errors
            raise TimeoutError(f"Found no process named {processName} after waiting for {timeout} seconds.")
        else:
            return None
        
    def getProcessByName(self, processName):
        """ 
        get the list of processes that somehow match the provided processname.
        checks the process name, commandline and exe
        """
        assert processName, "no process name provided"
        list = []
        for process in psutil.process_iter():
            name, exe, cmdline = "", "", []
            try:
                name = process.name()
                cmdline = process.cmdline()
                exe = process.exe()
            except (psutil.AccessDenied, psutil.ZombieProcess):
                pass
            except psutil.NoSuchProcess:
                continue
            if name == processName or PurePath(exe).name == processName or (len(cmdline) > 0 and cmdline[0] == processName):
                list.append(process)
        return list
    
    def sendExitRetryAndWait(self, stoptimeout=0, additionalTimeout=120, interval=5):
        """
        sends a "saveandexit $stoptimeout" to the server via empremoteclient, then checks every $interval seconds if it actually stopped
        and retries doing until the stoptimeout*60+additionalTimeout is reached, in which case it raises a TimeOutError
        returns True when successful
        """
        # stoptimeout is in minutes, so we need to add that to the waiting timeout
        maxTime = additionalTimeout
        if (stoptimeout > 0):
            maxTime += (stoptimeout * 60)
        waitedTime = 0
        while waitedTime < maxTime:
            if self.isRunning():
                if waitedTime > 0:
                    # don't show this the first time
                    log.debug(f"server didn't stop yet, retrying after {waitedTime} seconds")
                self.emprcClient.sendExit(stoptimeout)
                time.sleep(interval)
                waitedTime = waitedTime + interval
            else:
                if waitedTime > 0:
                    # don't show this the first time
                    log.debug(f"server stopped after {waitedTime} seconds")
                return True
        raise TimeoutError(f"server did not stop after {maxTime} seconds, you may need to kill it with force")
    
    def kill(self):
        if not self.process:
            log.debug("process info does not exist, need to find the process from the task list")
            self.process = self.findDedicatedExeProcess(raiseException=False)
            if not self.process:
                raise Exception("Could not find a running server process. Did you forget to start the server?")
        log.info(f"Will send the server process {self.process.pid} the kill signal")
        # on windows there's only the possibility to kill :/
        self.process.terminate()
        
    def killAndWait(self, timeout=15):
        if not self.process:
            log.debug("process info does not exist, need to find the process from the task list")
            self.process = self.findDedicatedExeProcess(raiseException=False)
            log.debug(f"process info found {self.process}")
            if not self.process:
                raise Exception("Could not find a running server process. Did you forget to start the server?")
        self.process.kill()
        self.waitForEnd(timeout)

    def isRunning(self):
        """
        returns true if the server process is still running. if for some reason the process is unknown, will look for it in the process list.
        """
        if not self.process:
            self.process = self.findDedicatedExeProcess()
            if not self.process:
                return False
        return self.process.is_running()
        
    def waitForEnd(self, timeout=60):
        """
        basically the same as #isRunning(), but this wait until the found process waits or exit with after a timeout
        """
        if not self.process:
            self.process = self.findDedicatedExeProcess()
            if not self.process:
                raise Exception("Could not find a running server process. Did you forget to start the server?")
        return self.process.wait(timeout=timeout)
    
    def assertEnoughFreeDiskspace(self):
        """
        make sure there is enough space on the drive where the savegame resides, raise an error if not
        """
        driveToCheck = None
        if self.config.general.useRamdisk:
            driveToCheck = Path(self.config.ramdisk.drive)
        else:
            driveToCheck = Path(self.config.paths.install).drive

        minimumSpaceHuman = self.config.server.minDiskSpaceForStartup
        log.debug(f"Checking space on drive {driveToCheck}. Configured minimum for startup is {minimumSpaceHuman}")
        hasEnough, freeSpace, freeSpaceHuman = FsTools.hasEnoughFreeDiskSpace(driveToCheck, minimumSpaceHuman)
        log.debug(f"Free space on drive {driveToCheck} is {freeSpaceHuman}. Configured minimum for startup is {minimumSpaceHuman}")
        if not hasEnough:
            log.error(f"The drive {driveToCheck} has not enough free disk space, the minimum required to start up is configured to be {minimumSpaceHuman}")
            raise AdminRequiredException("Space on the drive is running out, will not start up the server to prevent savegame corruption")
        return True
    
    def assertSharedDataURLIsAvailable(self):
        """
        make sure the shared data url is available, raise an error if not because this will break the game
        """
        # invalidate configuration, since it might be outdated if the shared data server is running within the same process.
        del self.config
        url = self.config.dedicatedConfig.GameConfig.SharedDataURL
        if url is not None:
            if not re.match(pattern="_?https?://", string=url):
                raise AdminRequiredException(f"The shared data url {url} must start with (_)http:// or (_)https:// - an invalid URL could break the game clients. Will not start the server.")
            if url.startswith("_"):
                url = url[1:]
            if self.isUrlAvailable(url):
                log.info(f"There is a valid shared data url configured at '{url}' and it is available.")
                return True
            else:
                raise AdminRequiredException(f"The configured shared data url '{url}' is not reachable. Make sure the url is correct and reachable, use the shareddata-server-tool or remove the SharedDataURL from the config.")
        else:
            log.debug(f"The shared data url is not configured, everything is fine.")

    def isUrlAvailable(self, url):
        """
        check that a given url responds with a valid status code (following redirects, if there are any)
        """
        try:
            response = requests.head(url, timeout=10, allow_redirects=True)
            if response.status_code == 200:
                return True
        except Exception as ex:
            return False
        return False
