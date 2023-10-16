import os, sys, time
import logging
import subprocess
import psutil
import re
from pathlib import Path
from datetime import datetime

log = logging.getLogger(__name__)

"""
Represents the dedicated server (executable), with the ability to start, stop, check if its running, etc.
"""
class EsmDedicatedServer:

    STARTMODE_DIRECT = ["direct", "will bypass the launcher and use the dedicated.exe directly. Use this mode if you need to run multiple instances of the server on one machine."],
    STARTMODE_LAUNCHER = ["launcher", "will use the EmpyrionLauncher.exe to start the game"]
    STARTMODES = [STARTMODE_DIRECT, STARTMODE_LAUNCHER]

    GFXMODE_ON = [True, "uses the '-startDediWithGfx' param in the launcher - which enables the server graphics overlay, you may want to use this when you have no other means of stopping the server."]
    GFXMODE_OFF = [False, "graphics overlay disabled, you probably want this if you're using EAH. You'll need to stop the server via EAH or other means."]
    GFXMODE = [GFXMODE_ON, GFXMODE_OFF]

    def __init__(self, config):
        self.config = config
        installDir = config.paths.install
        dedicatedYaml = config.server.dedicatedYaml
        gfxMode = config.server.gfxMode
        startMode = config.server.startMode
        log.debug(f"{__name__} initialized with startmode {startMode}, gfxMode {gfxMode}, dedicatedYaml {dedicatedYaml}, installDir {installDir}")

    def start(self):
        log.debug(f"starting server in startMode {self.config.server.startMode}")
        if (self.config.server.startMode == EsmDedicatedServer.STARTMODE_DIRECT):
            self.startDirectMode()
        else:
            self.startLauncherMode()
        
    def startDirectMode(self):
        arguments = [os.path.abspath(f"{self.config.folderNames.dedicatedServer}/{self.config.filenames.dedicatedExe}")]
        log.debug(f"gfxMode: {self.config.server.gfxMode}")
        if (self.config.server.gfxMode == self.GFXMODE_OFF):
            log.debug(f"gfxMode: {self.config.server.gfxMode} is OFF")
            arguments.append("-batchmode")
            arguments.append("-nographics")
        arguments.append("-dedicated")
        arguments.append(self.config.server.dedicatedYaml)
        arguments.append("-logFile")
        arguments.append(self.createLogFileName())
        log.info(f"Starting server with: {arguments} in directory {self.config.paths.install}")
        process = subprocess.Popen(args=arguments)
        log.debug(f"Process returned: {process}. pid: {process.pid}")
        self.process = process

    def createLogFileName(self):
        " reproduce a logfile name like ../Logs/$buildNumber/Dedicated_YYMMDD-HHMMSS-xx.log. xx is unknown, so it can be omited for now."
        buildNumber = self.getBuildNumber()
        formattedDate = self.getFormattedDate()
        logFileName = f"../Logs/{buildNumber}/Dedicated_{formattedDate}.log"
        return logFileName
    
    def getBuildNumber(self):
        buildNumberFilePath = os.path.abspath(Path(f"{self.config.paths.install}/{self.config.filenames.buildNumber}"))
        with open(buildNumberFilePath, "r") as buildNumberFilePath:
            firstLine = buildNumberFilePath.readline()
            cleanedString = re.sub(r'[^a-zA-Z0-9]', '', firstLine)
            return cleanedString
        
    def getFormattedDate(self, date=None):
        if date is None:
            date = datetime.now()
        formattedDate = date.strftime("%y%m%d-%H%M%S")
        return formattedDate

    def startLauncherMode(self):
        exeFileName = self.config.filenames.launcherExe
        pathToExecutable = os.path.abspath(f"{self.config.paths.install}/{self.config.filenames.launcherExe}")
        startDedi = "-startDedi"
        log.debug(f"gfxMode: {self.config.server.gfxMode}")
        if (self.config.server.gfxMode == self.GFXMODE_ON):
            log.debug(f"gfxMode: {self.config.server.gfxMode} is ON")
            startDedi = "-startDediWithGfx"
        arguments = [pathToExecutable, startDedi, "-dedicated", self.config.server.dedicatedYaml]
        log.info(f"Starting server with: {arguments} in directory {self.config.paths.install}")
        process = subprocess.Popen(args=arguments, cwd=self.config.paths.install)
        # give it a few seconds to start properly
        time.sleep(5)
        log.debug(f"launcher returned: {process}")
        # find the process and save its pid
        processes = self.getProcessByName(self.config.filenames.dedicatedExe)
        if len(processes) == 1:
            self.process = processes[0]
        elif len(processes) > 1:
            # exit the script with an error to avoid further breaking
            raise Exception(f"Found more than one process named {self.config.filenames.dedicatedExe}. This will probably break this script. If you want to run multiple instances of the game, use the startmode 'direct'. Otherwise you'll probably want to stop or kill the remaining process first.")
        else:
            # exit the script with an error to avoid further breaking
            raise Exception(f"Found no process named {self.config.filenames.dedicatedExe}. The game probably can't start. Check its logfile and try starting it manually to see why it fails?")
        
    def getProcessByName(self, processName):
        assert processName
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
            if name == processName or os.path.basename(exe) == processName or (len(cmdline) > 0 and cmdline[0] == processName):
                list.append(process)
        return list
    
    def stop(self):
        log.info(f"Will try to kill the server now")
        if self.process:
            self.process.kill()

    def isRunning(self):
        if self.process:
            return self.process.is_running
        return False
