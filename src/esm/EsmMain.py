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
        if askUser("Ready? [yes/no] ", "yes"):
            log.info("Will start the server with the default configuration now")
            newEsm = EsmDedicatedServer(config=self.config)
            newEsm.gfxMode = GfxMode.ON
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
        try:
            try:
                log.debug("calling ramdisk prepare")
                self.ramdiskManager.prepare()
                log.debug("ramdisk prepare finished")
                log.info("Prepare complete, you may now start the ramdisk setup")
            except NoSaveGameFoundException:
                log.debug("asking user to create new savegame")
                if askUser("Do you want to create a new savegame? [yes/no] ", "yes"):
                    log.debug("creating new savegame")
                    self.createNewSavegame()
                    log.info("Calling prepare again. Won't handle another fail.")
                    self.ramdiskManager.prepare()
                else:
                    log.debug("user decided to abort prepare")
                    raise UserAbortedException("user decided to abort prepare")
            except SaveGameMirrorExistsException:
                log.debug("asking user if he wants to delete the existing savegame mirror")        
                savegameMirrorPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
                if askUser(f"Delete old savegame mirror at {savegameMirrorPath}? [yes/no] ", "yes"):
                    self.fileSystem.markForDelete(savegameMirrorPath)
                    self.fileSystem.commitDelete()
                    log.debug("deleted old savegame mirror")
                    self.ramdiskPrepare()
                else:
                    log.debug("user decided not to delete the old savegame mirror")
        except UserAbortedException:
            log.info("User aborted operation")

    def ramdiskSetup(self):
        raise NotImplementedError()

    def ramdiskUninstall(self):
        raise NotImplementedError()
    
