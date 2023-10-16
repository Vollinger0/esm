from functools import cached_property
import logging
from pathlib import Path
import time
from esm import AdminRequiredException, UserAbortedException
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

    def __init__(self, configFileName, customConfigFileName=None, caller=__name__, fileLogLevel=logging.DEBUG, streamLogLevel=logging.DEBUG):
        self.configFilename = configFileName
        self.customConfigFileName = customConfigFileName
        self.caller = caller

        # set up logging
        self.logFile = Path(caller).stem + ".log"
        EsmLogger.setUpLogging(self.logFile, fileLogLevel=fileLogLevel, streamLogLevel=streamLogLevel)

        # set up config
        self.configFilePath = Path(configFileName).absolute().resolve()
        context = {           
            'configFilePath': self.configFilePath,
            'logFile': self.logFile,
            'caller': self.caller
        }
        if customConfigFileName:
            self.customConfigFilePath = Path(customConfigFileName).absolute().resolve()
            context.update({'customConfigFilePath': self.customConfigFilePath})
        self.config = ServiceRegistry.register(EsmConfigService(configFilePath=self.configFilePath, customConfigFilePath=customConfigFileName, context=context))

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
        will wait for the server to end, checking every $checkInterval seconds
        """
        while self.dedicatedServer.isRunning():
            time.sleep(checkInterval)
    
    def onShutdown(self):
        """
        Will stop the synchronizer, then stop the server and do a last sync from ram 2 mirror
        """
        if self.config.general.useRamdisk:
            # stop synchronizer
            log.info(f"Stopping synchronizer thread")
            self.ramdiskManager.stopSynchronizer()
            log.info(f"Synchronizer thread stopped")

        # this should not be necessary, but just in case.
        if self.dedicatedServer.isRunning():
            # stop server
            log.info(f"Sending server the saveandexit command.")
            self.dedicatedServer.sendExitRetryAndWait(interval=self.config.server.sendExitInterval, additionalTimeout=self.config.server.sendExitTimeout)
            log.info(f"Server shut down")

        if self.config.general.useRamdisk:
            # sync ram to mirror
            log.info("Starting final ram to mirror sync after shutdown")
            self.ramdiskManager.syncRamToMirror()
        log.info("Server shutdown complete")

    def startServerAndWait(self):
        """
        Start the server and wait for it to end. This will not return until the server is shutdown via other means!
        """
        log.info(f"Starting server")
        self.startServer()
        log.info(f"Server started. Waiting for it to shut down.")
        self.waitForEnd()
        log.info(f"Server shut down. Executing shutdown tasks.")
        self.onShutdown()

    def sendSaveAndExit(self):
        """
        Just saven the saveandexit signal. Since this is probably called from another instance of the script that probably does not have
        the correct instances of the server and process, we don't check for anything nor execute other actions.
        """
        # stop server
        log.info(f"Trying to stop the server by sending the saveandexit command.")
        success = self.dedicatedServer.sendExitRetryAndWait(interval=self.config.server.sendExitInterval, additionalTimeout=self.config.server.sendExitTimeout)
        if success:
            log.info(f"Server shut down")

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
        Deletes the savegame, the related rolling backups, all eah data, logs etc.
        
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
        Checks existence of savegame and mirror, offers the user the possibility to fix that, then proceeds to prepare for ramdisk
        
        if mirror and savegame: delete mirror, do prepare
        if mirror and nosavegame: do nothing
        if nomirror and savegame:  do prepare
        if nomirror and nosavegame: create new, do prepare
        """
        savegameMirrorExists = self.fileSystem.existsDotPath("saves.gamesmirror.savegamemirror.globaldb")
        savegameExists = self.fileSystem.existsDotPath("saves.games.savegame.globaldb")
        savegameMirrorPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        savegamePath = self.fileSystem.getAbsolutePathTo("saves.games.savegame")

        if savegameMirrorExists:
            if savegameExists:
                log.info(f"A savegame mirror exists at {savegameMirrorPath}. The file system is either already prepared, there is a configuration error or the savegame mirror needs to be deleted.")
                if askUser(f"Delete old savegame mirror at {savegameMirrorPath}? [yes/no] ", "yes"):
                    self.fileSystem.markForDelete(savegameMirrorPath)
                    self.fileSystem.commitDelete()
                    self.ramdiskManager.prepare()
                else:
                    log.warning("Can not prepare the file system for ramdisk usage as long as a savegamemirror already exists. Maybe we don't need to prepare?")
                    raise UserAbortedException("User does not want to delete the savegame mirror")
            else:
                log.info(f"A savegame mirror exists at {savegameMirrorPath} and no savegame exists at {savegamePath}. Looks like we are already prepared for using a ramdisk. Will not do anything.")
                return True
        else:
            if savegameExists:
                log.info(f"Savegame exists and no mirror exists, calling prepare.")
                self.ramdiskManager.prepare()
            else:
                log.info(f"No savegame exists at {savegamePath}. This is either a configuration error or we need to create one first.")
                if askUser("Do you want to create a new savegame? [yes/no] ", "yes"):
                    log.debug("creating new savegame")
                    self.createNewSavegame()
                    self.ramdiskManager.prepare()
                else:
                    log.warning("Can not prepare the file system for ramdisk usage if there is no savegame")
                    raise UserAbortedException("User does not want to create a new savegame")

    def ramdiskSetup(self):
        """
        Sets up the ramdisk and all links to and from it respectively.
        """
        self.ramdiskManager.setup()

    def ramdiskUninstall(self, force=False):
        """
        Checks existence of savegame and mirror, offers the user the possibility to fix that, then proceeds to revert the ramdisk-prepare and -setup stuff
        
        if mirror and savegame: delete savegame, move mirror
        if mirror and nosavegame: move mirror
        if nomirror and savegame:  do nothing
        if nomirror and nosavegame: do nothing
        """
        if not force and self.config.general.useRamdisk:
            log.error("Ramdisk usage is enabled in the configuration, can not uninstall the ramdisk usage when it is enabled.")
            raise AdminRequiredException("Ramdisk usage is enabled in the configuration, can not uninstall when it is enabled.")
        if force:
            log.warning("Forcing uninstall even though the configuration is set to not use a ramdisk")

        mirrorExists = self.fileSystem.existsDotPath("saves.gamesmirror.savegamemirror.globaldb")
        mirrorPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        savegameExists = self.fileSystem.existsDotPath("saves.games.savegame.globaldb")
        savegamePath = self.fileSystem.getAbsolutePathTo("saves.games.savegame")

        if mirrorExists:
            if savegameExists:
                log.info(f"A savegame already exists at {savegamePath}. The ramdisk stuff is either already uninstalled, there is a configuration error or the savegame needs to be deleted.")
                if askUser(f"Delete old savegame at {savegamePath}? [yes/no] ", "yes"):
                    self.fileSystem.markForDelete(savegamePath)
                    self.fileSystem.commitDelete()
                    self.ramdiskManager.uninstall(force)
                else:
                    log.warning("Can not uninstall the file system as long as a savegame already exists. Maybe we don't need to uninstall?")
                    raise UserAbortedException("User does not want to delete the savegame")
            else:
                log.info(f"A savegame mirror exists at {mirrorPath} and no savegame exists at {savegamePath}")
                self.ramdiskManager.uninstall(force)
        else:
            if savegameExists:
                log.info(f"Savegame exists and no mirror exists. There file system is already ready to be used without a ramdisk.")
                return False
            else:
                log.info(f"No savegame exists at {savegamePath}. This is either a configuration error or none exists. You might need to create a new one later.")
                return False
