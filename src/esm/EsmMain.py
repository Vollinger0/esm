from functools import cached_property
import logging
from pathlib import Path
import time
from esm import AdminRequiredException, NoSaveGameFoundException, SaveGameMirrorExistsException, UserAbortedException
from esm.EsmBackupService import EsmBackupService
from esm.EsmDeleteService import EsmDeleteService
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmLogger import EsmLogger
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer, GfxMode
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.EsmSteamService import EsmSteamService
from esm.ServiceRegistry import ServiceRegistry
from esm.Tools import askUser, isDebugMode, monkeyPatchAllFSFunctionsForDebugMode

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
    
    @cached_property
    def steamService(self) -> EsmSteamService:
        return ServiceRegistry.get(EsmSteamService)
    
    @cached_property
    def deleteService(self) -> EsmDeleteService:
        return ServiceRegistry.get(EsmDeleteService)

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
        
    def createNewSavegame(self):
        """
        will start the server shortly to create a new savegame that can be used for installation
        """
        log.info("Will start the server with its blue graphics overlay to create a new savegame. The startup might take a few minutes.")
        log.info("This script will shut down the server automatically again, if it doesn't work, you'll probably have to stop it yourself by clicking on the 'Save and Exit' button.")
        if not askUser("Ready? [yes/no] ", "yes"):
            log.info("Create a new savegame yourself then, you can always start this installation again.")
            raise UserAbortedException("Did not create new savegame")

        log.info("Will start the server with the default configuration now")
        newEsm = EsmDedicatedServer(config=self.config)
        newEsm.gfxMode = GfxMode.ON
        try:
            # start the server without checking for the ramdisk or diskspace, since this may have been called *before* the ramdisk setup.
            newEsm.startServer(checkForRamdisk=False, checkForDiskSpace=False)
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
            log.error(f"Server didn't start: {ex}")
            raise AdminRequiredException(f"Server didn't start: {ex}")

    def startServer(self):
        """
        Will start the server (and the ramdisk synchronizer, if ramdisk is enabled)
        """
        if self.config.general.useRamdisk:
            syncInterval = self.config.ramdisk.synchronizeRamToMirrorInterval
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
            self.dedicatedServer.sendExitRetryAndWait(interval=self.config.server.sendExitInterval, additionalTimeout=self.config.server.sendExitTimeout)

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
        """
        return self.steamService.installGame()
    
    def updateGame(self):
        """
        calls steam to update the game via steam and call any additionally configured steps (like updating the scenario, copying files etc.)
        """
        return self.steamService.updateGame()
    
    def deleteAll(self):
        """
        Deletes the savegame, the related rolling backups, all ehh data, logs etc.
        
        Asks user if he's sure and offers to create a static backup first.
        """
        # ask user if he's sure he wants to completely delete the whole game and data
        log.debug("Asking user if he's sure he wants to delete everything related to the savegame.")
        if not askUser("This will delete *ALL* data belonging to the savegame, including the rolling backups (not the static ones), tool data, logs and everything that has been additionally configured. Are you sure you want to do this now? [yes/no] ", "yes"):
            log.info("Ok, will not delete anything.")
            return False

        # ask user for static backup
        if askUser("It is strongly recommended to create a last static backup, just in case. Do that now? [yes/no] ", "yes"):
            self.backupService.createStaticBackup()

        return self.deleteService.deleteAll()

    def ramdiskPrepare(self):
        """
        Checks that savegame exists and savegamemirror does not, offers the user the possibility to fix that, then proceeds to prepare for ramdisk
        """
        savegameFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame")
        if not savegameFolderPath.exists():
            log.info(f"No savegame exists at {savegameFolderPath}. This is either a configuration error or we need to create one first.")
            if askUser("Do you want to create a new savegame? [yes/no] ", "yes"):
                log.debug("creating new savegame")
                self.createNewSavegame()
            else:
                log.warning("Can not prepare the file system for ramdisk usage if there is no savegame")
                raise UserAbortedException("User does not want to create a new savegame")

        savegameMirrorFolderPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        if savegameMirrorFolderPath.exists():
            log.info(f"A savegame mirror exists at {savegameMirrorFolderPath}. This is either a configuration error or we need to delete it first.")
            if askUser(f"Delete old savegame mirror at {savegameMirrorFolderPath}? [yes/no] ", "yes"):
                self.fileSystem.markForDelete(savegameMirrorFolderPath)
                self.fileSystem.commitDelete()
            else:
                log.warning("Can not prepare the file system for ramdisk usage as long as the savegamemirror already exists.")
                raise UserAbortedException("User does not want to delete the savegame mirror")

        log.debug("calling ramdisk prepare")
        self.ramdiskManager.prepare()
        log.info("Prepare complete, you may now start the ramdisk setup")

    def ramdiskSetup(self):
        raise NotImplementedError()

    def ramdiskUninstall(self):
        raise NotImplementedError()
    
