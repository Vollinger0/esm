from enum import Enum
from functools import cached_property
import subprocess
import time
import logging
import psutil
import re
from pathlib import Path, PurePath
from datetime import datetime
from esm import AdminRequiredException, RequirementsNotFulfilledError
from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import isDebugMode

log = logging.getLogger(__name__)

class StartMode(Enum):
    DIRECT = "direct" #"will bypass the launcher and use the dedicated exe directly. Use this mode if you need to run multiple instances of the server on one machine."]
    LAUNCHER = "launcher" #"will use the launcher to start the game"

class GfxMode(Enum):
    ON = True #"uses the '-startDediWithGfx' param in the launcher - which enables the server graphics overlay, you may want to use this when you have no other means of stopping the server."]
    OFF = False # "graphics overlay disabled, you probably want this if you're using EAH. You'll need to stop the server via EAH or other means."]

@Service
class EsmDedicatedServer:
    """
    Represents the dedicated server (executable), with the ability to start, stop, check if its running, etc.

    contains constants for the different startmodes and gfxmodes
    """
    def __init__(self, config=None):
        if config:
            self.config = config
        self.process = None

    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    @cached_property
    def gfxMode(self) -> GfxMode:
        return GfxMode(self.config.server.gfxMode)
    
    @cached_property
    def startMode(self) -> StartMode:
        return StartMode(self.config.server.startMode)
    
    def startServer(self):
        """
        Start the server with the configured mode.
        The called methods will wait until the respective process is started

        If the server started successfully, the psutil process is returned.
        """
        self.assertRamdiskExists()
        self.assertEnoughFreeDiskspace()

        if (self.startMode == StartMode.DIRECT):
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
        log.info(f"Starting server with: {arguments} in directory {self.config.paths.install}")
        if not isDebugMode(self.config):
            # we do not use subprocess.run here, since we'll need the PID later and only psutil.Popen provides that.            
            process = psutil.Popen(args=arguments)
        else:
            log.debug(f"debug mode enabled!")
        log.debug(f"Process returned: {process}")
        self.process = process
        return self.process

    def getCommandForDirectMode(self):
        pathToExecutable = Path(f"{self.config.paths.install}/{self.config.foldernames.dedicatedserver}/{self.config.filenames.dedicatedExe}").absolute()
        arguments = [pathToExecutable]
        if self.gfxMode == GfxMode.OFF:
            log.debug(f"gfxMode is {GfxMode.OFF}")
            arguments.append("-batchmode")
            arguments.append("-nographics")
        else:
            log.debug(f"gfxMode is {GfxMode.ON}")
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
        log.info(f"Starting server with: {arguments} in directory {self.config.paths.install}")
        if not isDebugMode(self.config):
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
        self.process = self.findProcessByNameWithTimeout(self.config.filenames.dedicatedExe, self.config.server.launcher.maxStartupTimeout)
        log.debug(f"found process of dedicated server: {self.process}")
        return self.process

    def getCommandForLauncherMode(self):
        launcherExeFileName = self.config.filenames.launcherExe
        pathToExecutable = Path(f"{self.config.paths.install}/{launcherExeFileName}").absolute()
        if (self.gfxMode==GfxMode.ON):
            log.debug(f"gfxMode is {GfxMode.ON}")
            startDedi = "-startDediWithGfx"
        else:
            log.debug(f"gfxMode is {GfxMode.OFF}")
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
        buildNumberFilePath = Path(f"{self.config.paths.install}/{self.config.filenames.buildNumber}").absolute()
        with open(buildNumberFilePath, "r") as buildNumberFilePath:
            firstLine = buildNumberFilePath.readline()
            cleanedString = re.sub(r'[^a-zA-Z0-9]', '', firstLine)
            return cleanedString
        
    def getFormattedDate(self, date=None):
        if date is None:
            date = datetime.now()
        formattedDate = date.strftime("%y%m%d-%H%M%S")
        return formattedDate

    def findProcessByNameWithTimeout(self, processName, maxStartupTimeout):
        """
        will search for a process that contains or is like the provided processName
        It will do that every few seconds in a loop until either a process was found
        or the the maxStartupTimeout is reached, raising a TimeoutError
        """
        timePassed=0
        checkIntervalInSeconds=3
        while timePassed < maxStartupTimeout:
            processes = self.getProcessByName(processName)
            if len(processes) == 1:
                self.process = processes[0]
                log.debug(f"found process by name '{processName}': {self.process}")
                return self.process
            elif len(processes) > 1:
                # exit the script with an error to avoid further breaking
                raise Exception(f"Found more than one process named {processName}. This will probably break this script. If you want to run multiple instances of the game, use the startmode 'direct'. Otherwise you'll probably want to stop or kill the remaining process first.")
            else:
                time.sleep(checkIntervalInSeconds)
                timePassed=timePassed+checkIntervalInSeconds
        # at this point the timeout was reached and we didn't find any processes.
        # exit the script with an error to avoid further breaking
        raise TimeoutError(f"Found no process named {processName} after waiting for {maxStartupTimeout} seconds. The game probably can't start or the timeout value is too low. Check its logfile and try starting it manually to see why it fails or increase the config value of 'server.launcher.maxStartupTimeout'.")
        
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
    
    def sendExit(self, timeout=0):
        """
        sends a "saveandexit $timeout" to the server via the epmremoteclient and returns immediately. 
        You need to check if the server stopped successfully via the other methods
        """
        # use the epmremoteclient and send a 'saveandexit x' where x is the timeout in minutes. a 0 will stop it immediately.
        epmrc = self.getEpmRemoteClientPath()
        cmd = [epmrc, "run", "-q", f"saveandexit {timeout}"]
        if isDebugMode(self.config):
            cmd = [epmrc, "run", f"saveandexit {timeout}"]
        log.debug(f"executing {cmd}")
        process = subprocess.run(cmd)
        log.debug(f"process returned: {process}")
        # this returns when epmrc ends, not the server!
        if process.returncode > 0:
            log.error(f"error executing the epm client: stdout: \n{process.stdout}\n, stderr: \n{process.stderr}\n")

    def sendExitAndWait(self, timeout=15, stoptimeout=0):
        """
        sends a "saveandexit $stoptimeout" to the server via epmremoteclient, then waits for the server process to stop before returning.
        """
        log.warning("This might not work, if the server is not ready to accept commands yet (e.g. on startup)")
        self.sendExit(stoptimeout)
        self.waitForEnd(timeout)

    def sendExitRetryAndWait(self, stoptimeout=0, additionalTimeout=120, interval=5):
        """
        sends a "saveandexit $stoptimeout" to the server via epmremoteclient, then checks every $interval seconds if it actually stopped
        and retries doing until the stoptimeout*60+additionalTimeout is reached, in which case it raises a TimeOutError
        returns True when successful
        """
        # stoptimeout is in minutes, so we need to add that to the waiting timeout
        maxTime = additionalTimeout
        if (stoptimeout>0):
            maxTime = stoptimeout*60+additionalTimeout
        waitedTime = 0
        while waitedTime < maxTime:
            self.sendExit(stoptimeout)
            time.sleep(interval)
            waitedTime = waitedTime + interval
            if not self.isRunning():
                log.debug(f"server stopped after {waitedTime} seconds")
                return True
            log.debug(f"server didn't stop yet, retrying after {waitedTime} seconds")
        raise TimeoutError(f"server did not stop after {maxTime} seconds, you may need to kill it with force")
    
    def getEpmRemoteClientPath(self):
        epmRC = self.config.paths.epmremoteclient
        if Path(epmRC).exists():
            return epmRC
        raise RequirementsNotFulfilledError(f"epm remote client not found in the configured path at {epmRC}. Please make sure it exists and the configuration points to it.")
    
    def kill(self):
        if self.process:
            log.info(f"Will send the server process {self.process.pid} the kill signal")
            # on windows there's only the possibility to kill :/
            self.process.terminate()
        else:
            raise Exception("process info does not exist, did you forget to start the server?")
        
    def killAndWait(self, timeout=15):
        if self.process:
            self.process.kill()
            self.waitForEnd(timeout)
        else:
            raise Exception("process info does not exist, did you forget to start the server?")

    def isRunning(self):
        if self.process:
            return self.process.is_running()
        else:
            return False
        
    def waitForEnd(self, timeout=60):
        if self.process:
            return self.process.wait(timeout=timeout)
        else:
            raise Exception("process info does not exist, did you forget to start the server?")
    
    def assertEnoughFreeDiskspace(self):
        """
        make sure there is enough space on the drive where the savegame resides, raise an error if not
        """
        driveToCheck = None
        if self.config.general.useRamdisk:
            driveToCheck = Path(f"{self.config.ramdisk.drive}:")
        else:
            driveToCheck = Path(self.config.paths.install).drive

        minimumSpaceHuman = self.config.server.minDiskSpaceForStartup
        hasEnough, freeSpace, freeSpaceHuman = FsTools.hasEnoughFreeDiskSpace(driveToCheck, minimumSpaceHuman)
        log.debug(f"Free space on drive {driveToCheck} is {freeSpaceHuman}. Configured minimum for startup is {minimumSpaceHuman}")
        if not hasEnough:
            log.error(f"The drive {driveToCheck} has not enough free disk space, the minimum required to start up is configured to be {minimumSpaceHuman}")
            raise AdminRequiredException("Space on the drive is running out, will not start up the server to prevent savegame corruption")
        return True
    
    def assertRamdiskExists(self):
        """
        make sure the ramdisk exists if ramdisk is enabled. Does only check for drive letter, not driver itself.
        """
        ramdiskEnabled = self.config.general.useRamdisk
        if ramdiskEnabled:
            ramdiskDrive = Path(f"{self.config.ramdisk.drive}:")
            if ramdiskDrive.exists():
                return True
            else:
                raise AdminRequiredException(f"Ramdisk is enabled but it does not exist as drive {ramdiskDrive}. Make sure to run the ramdisk setup first!")
