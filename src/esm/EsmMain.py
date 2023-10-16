from datetime import datetime
from functools import cached_property
import logging
from pathlib import Path
import shutil
import subprocess
import time
from esm import AdminRequiredException, RequirementsNotFulfilledError
from esm.EsmBackupService import EsmBackupService
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmLogger import EsmLogger
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer, GfxMode
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.FsTools import FsTools
from esm.ServiceRegistry import ServiceRegistry
from esm.Tools import Timer, askUser, getElapsedTime, getTimer, isDebugMode, monkeyPatchAllFSFunctionsForDebugMode

log = logging.getLogger(__name__)

class EsmMain:
    """
    Main esm class, manages all the other modules, config, etc.
    """
    @cached_property
    def backupService(self) -> EsmBackupService:
        return ServiceRegistry.get(EsmBackupService)

    @cached_property    
    def ramdiskManager(self) -> EsmRamdiskManager:
        return ServiceRegistry.get(EsmRamdiskManager)
    
    @cached_property
    def dedicatedServer(self) -> EsmDedicatedServer:
        return ServiceRegistry.get(EsmDedicatedServer)
    
    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)

    def __init__(self, configFileName, caller=__name__):
        self.configFilename = configFileName
        self.caller = caller

        # set up logging
        self.logFile = Path(caller).stem + ".log"
        EsmLogger.setUpLogging(self.logFile)

        # set up config
        self.configFilePath = Path(configFileName).absolute()
        context = {           
            'configFilePath': self.configFilePath,
            'logFile': self.logFile,
            'caller': self.caller
        }            
        self.config = ServiceRegistry.register(EsmConfigService(configFilePath=self.configFilePath, context=context))

        # in debug mode, monkey patch all functions that may alter the file system or execute other programs.
        if isDebugMode(self.config):
            monkeyPatchAllFSFunctionsForDebugMode()
        
    def askUserToCreateNewSavegame(self):
        if askUser("Do you want to create a new savegame? [yes/no] ", "yes"):
            log.debug("creating new savegame")
            self.createNewSavegame()
            return True
        return False

    def createNewSavegame(self):
        """
        will start the server shortly to create a new savegame that can be used for installation
        """
        log.info("Will start the server with its blue graphics overlay to create a new savegame. The startup might take a few minutes.")
        log.info("This script will shut down the server automatically again, if it doesn't work, you'll probably have to stop it yourself by clicking on the 'Save and Exit' button.")
        if askUser("Ready? [yes/no] ", "yes"):
            log.info("Will start the server with the default configuration now")
            newEsm = EsmDedicatedServer(config=self.config, gfxMode=GfxMode.ON)
            try:
                newEsm.startServer()
                # give the server some time to start and create the new savegame before we try stopping it again
                time.sleep(self.config.server.startUpSleepTime)
                try:
                    # try to tell the server to shut down and wait for it
                    newEsm.sendExitRetryAndWait()
                    return True
                except TimeoutError as ex:
                    log.error(f"could not stop server while trying to create a new savegame. Something's wrong")
                    raise AdminRequiredException("could not stop server while trying to create a new savegame.")
            except Exception as ex:
                log.info(f"Server didn't start: {ex}")
        else:
            log.info("Create a new savegame yourself then, you can always start this installation again.")
        return False

    def askUserToDeleteOldSavegameMirror(self):
        """
        ask user if he wants to the delete the old savegame mirror and do that if so
        """
        savegameMirrorPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        if askUser(f"Delete old savegame mirror at {savegameMirrorPath}? [yes/no] ", "yes"):
            self.fileSystem.delete(savegameMirrorPath)
            return True
        return False
    
    def startServer(self):
        """
        Will start the server (and the ramdisk synchronizer, if ramdisk is enabled)
        """
        if self.config.general.useRamdisk:
            syncInterval = self.config.ramdisk.synchronizeramtohddinterval
            if syncInterval>0:
                # start the synchronizer
                log.info(f"Starting ram2mirror synchronizer with interval {syncInterval}")
                self.ramdiskManager.startSynchronizer(syncInterval)
        
        # start the server
        log.info(f"Starting the dedicated server")
        return self.dedicatedServer.startServer()
    
    def waitForEnd(self, checkInterval=5):
        """
        will wait for the server to end, checking every $checkInterval seconds, then it will do the shutdown tasks and return.
        """
        while self.dedicatedServer.isRunning():
            time.sleep(checkInterval)
        return self.stopServer()

    def stopServer(self):
        """
        Will stop the synchronizer, then stop the server and do a last sync from ram 2 mirror
        """
        if self.config.general.useRamdisk:
            # stop synchronizer
            self.ramdiskManager.stopSynchronizer()

        if self.dedicatedServer.isRunning():
            # stop server
            self.dedicatedServer.sendExitRetryAndWait()

        if self.config.general.useRamdisk:
            # sync ram to mirror
            log.info("Starting final ram to mirror sync after shutdown")
            self.ramdiskManager.syncRamToMirror()

    def createBackup(self):
        """
        create a backup of the savegame using the rolling mirror backup system
        """
        log.info("creating rolling backup")
        self.backupService.createRollingBackup()

    def createStaticBackup(self):
        """
        create a static zipped backup of the latest rolling backup
        """
        self.backupService.createStaticBackup()

    def installGame(self):
        """
        calls steam to install the game via steam to the given installation directory

        # %steamCmdPath% +force_install_dir %installPath% +login anonymous +app_update 530870 validate +quit"
        """
        # steam install
        steamcmdExe = self.getSteamCmdExecutable()
        installPath = self.config.paths.install
        cmd = [steamcmdExe]
        cmd.extend(str(f"+force_install_dir {installPath} +login anonymous +app_update 530870 validate +quit").split(" "))
        log.debug(f"executing {cmd}")
        start = getTimer()
        process = subprocess.run(cmd)
        elapsedTime = getElapsedTime(start)
        log.debug(f"after {elapsedTime} process returned: {process} ")
        # this returns when the process finishes
        if process.returncode > 0:
            log.error(f"error executing steamcmd: stdout: \n{process.stdout}\n, stderr: \n{process.stderr}\n")
    
    def updateGame(self):
        """
        calls steam to update the game via steam and call any additionally configured steps (like updating the scenario, copying files etc.)

        # %steamCmdPath% +force_install_dir %installPath% +login anonymous +app_update 530870 validate +quit"
        """
        # steam update is actually the exact same call as the install command, so we'll call just that instead.
        self.installGame()

        # additional copying according to configuration
        self.copyAdditionalUpdateStuff()

    def getSteamCmdExecutable(self):
        """
        checks that the steam executable exists and returns its path.
        """
        steamcmdExe = self.config.paths.steamcmd
        if Path(steamcmdExe).exists():
            return steamcmdExe
        raise RequirementsNotFulfilledError(f"steamcmd.exe not found in the configured path at {steamcmdExe}. Please make sure it exists and the configuration points to it.")
    
    def copyAdditionalUpdateStuff(self):
        """
        copies any additionally configured stuff in the config under updates.additional
        """
        additionalStuffList = self.config.updates.additional
        if additionalStuffList and len(additionalStuffList)>0:
            for additionalStuff in additionalStuffList:

                source = Path(additionalStuff.src)
                if not Path(source).is_absolute():
                    source = Path(f"{self.config.paths.install}/{source}")

                destination = Path(additionalStuff.dst)
                if not Path(destination).is_absolute():
                    destination = Path(f"{self.config.paths.install}/{destination}")

                if source.is_dir():
                    # its a dir
                    log.info(f"copying directory {source} into {destination}")  
                    FsTools.copyDir(source=source, destination=destination)
                else:
                    # its a file
                    log.info(f"copying file {source} into {destination}")  
                    FsTools.copy(source=source, destination=destination)

    def deleteAll(self):
        """
        Offers the user to create a static backup first, then backs up the logs and stuff, and then starts deleting stuff.
        Deletes everything that belongs to a savegame, including:
        - the savegame (or the ramdisk, if enabled)
        - the backups (not the static ones)
        - the mirrors
        - the eah tool data
        - the logs from the game, tool and esm
        - any additional paths that were configured

        This will ask the user before executing the deletes though.
        """
        # ask user if he's sure he wants to completely delete the whole game and data
        log.debug("asking user if he's sure")
        if not askUser("This will delete *ALL* data belonging to the savegame, including the rolling backups (not the static ones), tool data, logs and everything that has been additionally configured. Are you sure you want to do this now? [yes/no] ", "yes"):
            log.info("Ok, will not delete anything.")
            return False

        # ask user for static backup
        if askUser("It is strongly recommended to create a last static backup, just in case. Do that now? [yes/no] ", "yes"):
            self.backupService.createStaticBackup()

        if self.config.general.useRamdisk:
            # just unmount the ramdisk, if it exists.
            driveLetter = self.config.ramdisk.drive
            if Path(f"{driveLetter}:").exists():
                log.info(f"Unmounting ramdisk at {driveLetter}.")
                try:
                    self.ramdiskManager.unmountRamdisk(driveLetter=driveLetter)
                except AdminRequiredException as ex:
                    log.error(f"exception trying to unmount. Will check if its mounted at all")
                    if self.ramdiskManager.checkRamdrive(driveLetter=driveLetter):
                        raise AdminRequiredException(f"Ramdisk is still mounted, can't recuperate from the error here. Exception: {ex}")
                    else:
                        log.info(f"There is no more ramdisk mounted as {driveLetter}, will continue.")
                log.info(f"Ramdisk at {driveLetter} unmounted")
        else:
            with Timer() as timer:
                savegamePath = self.fileSystem.getAbsolutePathTo("saves.games.savegame")
                log.info(f"Deleting savegame at {savegamePath}. Depending on savegame size this might take a while!")
                self.fileSystem.delete(savegamePath, native=True)
            log.debug(f"deleting savegame took {timer.elapsedTime}")

        # delete backups
        backups = self.fileSystem.getAbsolutePathTo("backup")
        backupMirrors = self.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        # delete all hardlinks to the backupmirrors first
        log.debug(F"deleting all links to the rolling backups")
        for entry in backups.iterdir():
            if FsTools.isHardLink(entry):
                rollingBackup = FsTools.getLinkTarget(entry)
                if self.config.foldernames.backupmirrorprefix in rollingBackup.name:
                    # the link points to a rolling backup, delete it
                    FsTools.deleteLink(entry)
        with Timer() as timer:
            log.info(f"Deleting all rolling backups at {backupMirrors}. Depending on savegame size this might take quite a while!")
            self.fileSystem.delete(backupMirrors, native=True)
        log.debug(f"deleting rolling backups took {timer.elapsedTime}")

        # delete game mirrors
        with Timer() as timer:
            gamesmirrors = self.fileSystem.getAbsolutePathTo("saves.gamesmirror")
            log.info(f"Deleting all hdd mirrors at {gamesmirrors}. Depending on savegame size this might take a while!")
            self.fileSystem.delete(gamesmirrors, native=True)
        log.debug(f"deleting hdd mirrors took {timer.elapsedTime}")

        # delete the cache
        with Timer() as timer:
            cache = self.fileSystem.getAbsolutePathTo("saves.cache")
            cacheSavegame = f"{cache}/{self.config.server.savegame}"
            log.info(f"Deleting the cache at {cacheSavegame}")
            self.fileSystem.delete(cacheSavegame)
        log.debug(f"deleting cache took {timer.elapsedTime}")
        
        #delete eah tool data
        eahToolDataPattern = Path(f"{self.config.paths.eah}/Config/").absolute().joinpath("*.dat")
        deglobbedPaths = FsTools.resolveGlobs([eahToolDataPattern])
        for entry in deglobbedPaths:
            self.fileSystem.delete(entry)

        # delete additionally configured stuff
        additionalDeletes = self.config.deletes.additionalDeletes
        if additionalDeletes and len(additionalDeletes)>0:
            absolutePaths = FsTools.toAbsolutePaths(additionalDeletes, parent=self.config.paths.install)
            deglobbedPaths = FsTools.resolveGlobs(absolutePaths)
            for path in deglobbedPaths:
                self.fileSystem.delete(path)
        
        # backupAllLogs
        self.backupAllLogs()
        log.info("Deletion complete, you can now start a fresh game.")

    def backupAllLogs(self):
        backupDir = self.fileSystem.getAbsolutePathTo("backup")
        logBackupFolder = Path(f"{backupDir}/alllogs")
        logBackupFolder.mkdir(exist_ok=True)
        if self.config.deletes.backupGameLogs:
            source = f"{self.config.paths.install}/Logs/*"
            self.backupLogs(source, logBackupFolder, "GameLogs")
        if self.config.deletes.backupEahLogs:
            source = f"{self.config.paths.eah}/logs/*"
            self.backupLogs(source, logBackupFolder, "EAHLogs")
        if self.config.deletes.backupEsmLogs:            
            source = f"{self.config.paths.install}/*.log"
            self.backupLogs(source, logBackupFolder, "ESMLogs")
            source = f"{self.config.paths.install}/esm/*.log"
            self.backupLogs(source, logBackupFolder, "ESMLogs")
        # zip the target folder and remove it afterwards
        zipFileName = self.getLogsBackupFileName()
        self.backupService.createZip(source=logBackupFolder, backupDirectory=backupDir, zipFileName=zipFileName)
        self.fileSystem.delete(logBackupFolder)
        log.info(f"All logs backed up and zipped as {zipFileName}")

    def backupLogs(self, sourcePath, backupFolderPath, folderName):
        """
        move the content of given source path to the backup folder path, putting the contents into the folder called foldername at the target
        """
        sourcePaths = []
        # if source is glob, get list of sources.
        if FsTools.isGlobPattern(sourcePath):
            sourcePaths.extend(FsTools.resolveGlobs(paths=[sourcePath]))
        else:
            sourcePaths.append(sourcePath)

        for source in sourcePaths:
            # move source into backupfolder as requested.
            target = backupFolderPath.joinpath(folderName);
            FsTools.createDir(target)
            # if we're trying to move our own logfile, just create a copy instead.
            if Path(self.config.context.logFile).samefile(source):
                shutil.copy(src=source, dst=target)
            else:
                shutil.move(src=source, dst=target)
        
    def getLogsBackupFileName(self, date=None):
        """
        returns a filename for the static zip file looking like: 20231002_2359_savegame_logs.zip
        """
        if date:
            date = date
        else:
            date = datetime.now()
        formattedDate = date.strftime("%Y%m%d_%H%M%S")
        return f"{formattedDate}_{self.config.server.savegame}_logs.zip"
