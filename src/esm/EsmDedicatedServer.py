import time
import logging
import psutil
import re
from pathlib import Path, PurePath
from datetime import datetime
from esm import isDebugMode

log = logging.getLogger(__name__)

class EsmDedicatedServer:
    """
    Represents the dedicated server (executable), with the ability to start, stop, check if its running, etc.

    contains constants for the different startmodes and gfxmodes
    
    Initialize with the configuration, since it will read anything it needs from there.
    """

    STARTMODE_DIRECT = ["direct", "will bypass the launcher and use the dedicated.exe directly. Use this mode if you need to run multiple instances of the server on one machine."]
    STARTMODE_LAUNCHER = ["launcher", "will use the EmpyrionLauncher.exe to start the game"]
    STARTMODES = [STARTMODE_DIRECT, STARTMODE_LAUNCHER]

    GFXMODE_ON = [True, "uses the '-startDediWithGfx' param in the launcher - which enables the server graphics overlay, you may want to use this when you have no other means of stopping the server."]
    GFXMODE_OFF = [False, "graphics overlay disabled, you probably want this if you're using EAH. You'll need to stop the server via EAH or other means."]
    GFXMODES = [GFXMODE_ON, GFXMODE_OFF]

    def __init__(self, config, installDir=None, dedicatedYaml=None, startMode=None, gfxMode=None):
        self.config = config
        self.installDir = installDir
        self.dedicatedYaml = dedicatedYaml
        self.startMode = startMode
        self.gfxMode = gfxMode        
        log.debug(f"{__name__} initialized with installDir {installDir}, dedicatedYaml {dedicatedYaml}, startmode {startMode}, gfxMode {gfxMode}")

    @classmethod
    def withConfig(cls, config):
        installDir = config.paths.install
        dedicatedYaml = config.server.dedicatedYaml
        gfxMode = config.server.gfxMode
        startMode = config.server.startMode
        return cls(config, installDir, dedicatedYaml, startMode, gfxMode)

    @classmethod    
    def withGfxMode(cls, config, gfxMode):
        installDir = config.paths.install
        dedicatedYaml = config.server.dedicatedYaml
        startMode = config.server.startMode
        return cls(config, installDir, dedicatedYaml, startMode, gfxMode)

    def startServer(self):
        """
        Start the server with the configured mode.
        The called methods will wait until the respective process is started

        If the server started successfully, the psutil process is returned.
        """
        if (self.getConfiguredStartMode() == self.STARTMODE_DIRECT):
            log.debug(f"startMode is {self.STARTMODE_DIRECT}")
            return self.startServerDirectMode()
        else:
            log.debug(f"startMode is {self.STARTMODE_LAUNCHER}")
            return self.startServerLauncherMode()
        
    def startServerDirectMode(self):
        """
        Starts the server using the dedicated exe, bypassing the launcher. This enables us to be able to identify the process id directly
        This, in turn, allows that there can be multiple instances of the dedicated exe running on the same machine

        Method returns as soon as the process is started and its process info is returned.
        """
        pathToExecutable = Path(f"{self.config.paths.install}/{self.config.foldernames.dedicatedServer}/{self.config.filenames.dedicatedExe}").absolute()
        arguments = [pathToExecutable]
        if self.getConfiguredGfxMode() == self.GFXMODE_OFF:
            log.debug(f"gfxMode is {self.GFXMODE_OFF}")
            arguments.append("-batchmode")
            arguments.append("-nographics")
        else:
            log.debug(f"gfxMode is {self.GFXMODE_ON}")
        arguments.append("-dedicated")
        arguments.append(self.config.server.dedicatedYaml)
        arguments.append("-logFile")
        arguments.append(self.createLogFileName())
        log.info(f"Starting server with: {arguments} in directory {self.config.paths.install}")
        if not isDebugMode(self.config):
            process = psutil.Popen(args=arguments)
        else:
            log.debug(f"debug mode enabled!")
        log.debug(f"Process returned: {process}")
        self.process = process
        return self.process
    
    def startServerLauncherMode(self):
        """
        Start the game using the default empyrion launcher, returns the psutil process of the dedicated exe if successful

        Method returns as soon as the process of the dedicated server was found and its process info is returned, otherwise exceptions are passed.
        """
        launcherExeFileName = self.config.filenames.launcherExe
        pathToExecutable = Path(f"{self.config.paths.install}/{launcherExeFileName}").absolute()
        if (self.getConfiguredGfxMode()==self.GFXMODE_ON):
            log.debug(f"gfxMode is {self.GFXMODE_ON}")
            startDedi = "-startDediWithGfx"
        else:
            log.debug(f"gfxMode is {self.GFXMODE_OFF}")
            startDedi = "-startDedi"
        arguments = [pathToExecutable, startDedi, "-dedicated", self.config.server.dedicatedYaml]
        log.info(f"Starting server with: {arguments} in directory {self.config.paths.install}")
        if not isDebugMode(self.config):
            process = psutil.Popen(args=arguments, cwd=self.config.paths.install)
        else:
            log.debug(f"debug mode enabled!")
        # give the launcher a few seconds to start the dedicated exe
        time.sleep(3)
        log.debug(f"launcher returned: {process}")
        
        # find the dedicated process and remember its process info
        self.process = self.findProcessByNameWithTimeout(self.config.filenames.dedicatedExe, self.config.server.launcher.maxStartupTimeout)
        log.debug(f"found process of dedicated server: {self.process}")
        return self.process
    
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
        amountOfProcesses=0
        timePassed=0
        checkIntervalInSeconds=3
        while (amountOfProcesses==0 and timePassed < maxStartupTimeout):
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
            if name == processName or PurePath(exe).name() == processName or (len(cmdline) > 0 and cmdline[0] == processName):
                list.append(process)
        return list
    
    def getGfxModeByString(self, string):
        for mode in self.GFXMODES:
            if mode[0]==string:
                return mode
        # default to on
        return self.GFXMODE_ON
    
    def getConfiguredGfxMode(self):
        return self.getGfxModeByString(self.gfxMode)

    def getStartModeByString(self, string):
        for mode in self.STARTMODES:
            if mode[0]==string:
                return mode
        # default to launcher
        return self.STARTMODE_LAUNCHER
    
    def getConfiguredStartMode(self):
        return self.getStartModeByString(self.startMode)
    
    def stop(self, timeout):
        # TODO: use the epmremoteclient and send a 'saveandexit x' where x is the timeout in minutes. a 0 will stop it immediately.
        raise NotImplementedError("not implemented yet")
    
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
            # wait for a few seconds. if the timeout is reached there will be a timeoutexpired exception thrown.
            self.process.wait(timeout=timeout)
        else:
            raise Exception("process info does not exist, did you forget to start the server?")

    def isRunning(self):
        if self.process:
            return self.process.is_running()
        else:
            return False
        
    def waitForStop(self, timeout=60):
        if self.process:
            return self.process.wait(timeout=timeout)
        else:
            raise Exception("process info does not exist, did you forget to start the server?")
