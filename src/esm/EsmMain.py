from functools import cached_property
import logging
from pathlib import Path
import time
from esm import AdminRequiredException
from esm.EsmBackupService import EsmBackupService
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmLogger import EsmLogger
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer, GfxMode
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.ServiceRegistry import ServiceRegistry
from esm.Tools import askUser

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
