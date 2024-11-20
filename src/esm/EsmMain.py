from functools import cached_property
import logging
from pathlib import Path
import socket
import threading
import time
import sys
from typing import List
from esm import Tools
from esm.EsmGameChatService import EsmGameChatService
from esm.EsmHaimsterConnector import EsmHaimsterConnector
from esm.EsmSharedDataServer import EsmSharedDataServer
from esm.exceptions import AdminRequiredException, ExitCodes, RequirementsNotFulfilledError, ServerNeedsToBeStopped, UserAbortedException, WrongParameterError
from esm.ConfigModels import MainConfig
from esm.DataTypes import Territory, WipeType
from esm.EsmLogger import EsmLogger
from esm.FsTools import FsTools
from esm.Tools import Timer, askUser, mergeDicts, monkeyPatchAllFSFunctionsForDebugMode
from esm.EsmEmpRemoteClientService import EsmEmpRemoteClientService
from esm.EsmConfigService import EsmConfigService
from esm.EsmBackupService import EsmBackupService
from esm.EsmDeleteService import EsmDeleteService
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.EsmSteamService import EsmSteamService
from esm.EsmWipeService import EsmWipeService
from esm.ServiceRegistry import ServiceRegistry

log = logging.getLogger(__name__)

class EsmMain:
    """
    main esm class, manages all the other modules, config, tools etc.

    this will also handle any user input and exceptions, so the service classes can focus on the task to be solved.
    make sure that no delegate actually asks the user for input.
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

    @cached_property    
    def wipeService(self) -> EsmWipeService:
        return ServiceRegistry.get(EsmWipeService)
    
    @cached_property
    def sharedDataServer(self) -> EsmSharedDataServer:
        return ServiceRegistry.get(EsmSharedDataServer)
    
    @cached_property
    def haimsterConnector(self) -> EsmHaimsterConnector:
        return ServiceRegistry.get(EsmHaimsterConnector)
    
    @cached_property
    def configService(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    @cached_property
    def gameChatService(self) -> EsmGameChatService:
        return ServiceRegistry.get(EsmGameChatService)
    
    @cached_property
    def config(self) -> MainConfig:
        if self.customConfigFilePath is not None:
            self.configService.setConfigFilePath(self.customConfigFilePath)
        
        self.addContext(self.configService.config.context)
        self.setupDebugging(self.configService.config)
        return self.configService.config

    def __init__(self, caller=__name__, fileLogLevel=logging.DEBUG, streamLogLevel=logging.DEBUG, waitForPort=False, customConfigFilePath: Path=None):
        self.caller = caller
        self.waitForPort = waitForPort
        self.customConfigFilePath = customConfigFilePath

        # set up logging
        self.setUpLogging(caller, fileLogLevel, streamLogLevel)

    def setUpLogging(self, caller, fileLogLevel=logging.DEBUG, streamLogLevel=logging.DEBUG):
        self.logFile = Path(caller).stem + ".log"
        EsmLogger.setUpLogging(self.logFile, fileLogLevel=fileLogLevel, streamLogLevel=streamLogLevel)

    def setupDebugging(self, config: MainConfig):
        """in debug mode, monkey patch all functions that may alter the file system or execute other programs."""
        if config.general.debugMode:
            monkeyPatchAllFSFunctionsForDebugMode()
            log.debug(f"context: {config.context}")

    def addContext(self, context):
        mergeDicts(a=context, b={           
                'logFile': self.logFile,
                'caller': self.caller,
                'waitForPort': self.waitForPort,
                'customConfigFilePath': self.customConfigFilePath
                })
        
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
        newEsm = EsmDedicatedServer()
        newEsm.gfxMode = True
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
        Will start the server (and the ramdisk synchronizer, if ramdisk is enabled). Function returns once the server has been started.
        """
        if self.dedicatedServer.isRunning():
            log.warning("A server is already running! You may want to use the server resume operation to connect back to it.")
            raise ServerNeedsToBeStopped("A server is already running!")

        self.startSynchronizer()
        
        # start the server
        log.info(f"Starting the dedicated server")
        serverProcess = self.dedicatedServer.startServer()

        # start the haimster connector after the server has started. this is to make sure that the server has started before
        def startHaimsterConnectorDelayed():
            time.sleep(self.config.communication.haimsterStartupDelay)
            self.startHaimsterConnector()
        threading.Thread(target=startHaimsterConnectorDelayed, daemon=True).start()

        return serverProcess

    def startSynchronizer(self):
        """
        starts the ramdisk synchronizer if ramdisk and the synchronizer are enabled and properly configured
        """
        if self.config.general.useRamdisk:
            syncInterval = self.config.ramdisk.synchronizeRamToMirrorInterval
            if syncInterval > 0:
                # start the synchronizer
                log.info(f"Starting ram2mirror synchronizer with interval '{syncInterval}'")
                self.ramdiskManager.startSynchronizer(syncInterval)
    
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
        myHostIp = Tools.getOwnIp(self.config)
        serverPort = self.config.dedicatedConfig.ServerConfig.Srv_Port
        log.info(f"Server started. Reachable at '{myHostIp}:{serverPort}' - Waiting until it shut down or stopped existing.")
        self.waitForEnd()
        log.info(f"Server shut down. Executing shutdown tasks.")
        self.onShutdown()

    def sendSaveAndExit(self):
        """
        Just send the saveandexit signal. Since this is probably called from another instance of the script that probably does not have
        the correct instances of the server and process, we don't check for anything nor execute other actions.
        """
        # stop server
        log.info(f"Trying to stop the server by sending the saveandexit command.")
        success = self.dedicatedServer.sendExitRetryAndWait(interval=self.config.server.sendExitInterval, additionalTimeout=self.config.server.sendExitTimeout)
        if success:
            log.info(f"Server shut down or not running any more.")

    def resumeServerAndWait(self):
        """
        resumes execution for when the gameserver is probably still running
        """
        if not self.dedicatedServer.isRunning():
            log.warning("No running gameserver found.")
            return
        
        log.info(f"Running server found")
        # we found a server, then start synchronizer if enabled
        self.startSynchronizer()

        self.startHaimsterConnector()
        
        log.info(f"Waiting until game server shut down or stopped existing.")
        self.waitForEnd()

        log.info(f"Game server shut down. Executing shutdown tasks.")
        self.onShutdown()


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
        pathToExecutable = Path(f"{self.config.paths.install}/{self.config.foldernames.dedicatedserver}/{self.config.filenames.dedicatedExe}").resolve()
        if pathToExecutable.exists():
            raise AdminRequiredException(f"The server seems to be already installed at '{self.config.paths.install}'. Please check the config, or use the game-update command to update the game.")

        return self.steamService.installGame()
    
    def updateGame(self, steam=True, additionals=True):
        """
        calls steam to update the game via steam and call any additionally configured steps (like updating the scenario, copying files etc.)
        """
        return self.steamService.updateGame(steam, additionals)
    
    def updateScenario(self, sourcePathParameter: str = None, dryrun: bool=True):
        """
        synchronizes the source scenario folder with the games scenario folder.
        only new files or files whose size or content differ are copied, deleted files in the destination are removed.
        """
        if self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not update scenario while the server is running. Please stop it first.")

        scenarioName = self.config.dedicatedConfig.GameConfig.CustomScenario

        if sourcePathParameter is not None:
            sourcePath = Path(sourcePathParameter).joinpath(scenarioName)
        else:
            sourcePath = Path(self.config.updates.scenariosource).joinpath(scenarioName)

        sourcePath = sourcePath.resolve()
        if not sourcePath.exists():
            raise AdminRequiredException(f"Path to scenario source not properly configured, '{sourcePath}' does not exist.")

        destinationPath = Path(f"{self.config.paths.install}/Content/Scenarios/{scenarioName}").resolve()
        if not destinationPath.exists():
            log.warning(f"Path to game scenarios folder '{destinationPath}' does not exist. Will create the directory assuming the configuration is correct.")
            destinationPath.mkdir(parents=False, exist_ok=False)

        if dryrun:
            log.info(f"Would synchronize scenario from '{sourcePath}' to '{destinationPath}'. If you want to actually run it, use --nodryrun.")
        else:
            log.info(f"Synchronizing scenario from '{sourcePath}' to '{destinationPath}'")
            return self.fileSystem.synchronize(sourcePath, destinationPath)

    
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

    def ramdiskInstall(self):
        """
        Checks existence of savegame and mirror, offers the user the possibility to fix that, then proceeds to prepare for ramdisk
        
        if mirror and savegame: delete mirror, do prepare
        if mirror and nosavegame: do nothing
        if nomirror and savegame:  do prepare
        if nomirror and nosavegame: create new, do prepare
        """
        if self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not execute ramdisk prepare if the server is running. Please stop it first.")

        mirrorExists, mirrorPath = self.ramdiskManager.existsMirror()
        savegameExists, savegamePath = self.ramdiskManager.existsSavegame()

        if mirrorExists:
            if savegameExists:
                log.info(f"A savegame mirror exists at '{mirrorPath}'. The file system is either already prepared, there is a configuration error or the savegame mirror needs to be deleted.")
                if askUser(f"Delete old savegame mirror at '{mirrorPath}'? [yes/no] ", "yes"):
                    self.fileSystem.markForDelete(mirrorPath)
                    self.fileSystem.commitDelete()
                    self.ramdiskManager.prepare()
                else:
                    log.warning("Can not prepare the file system for ramdisk usage as long as a savegamemirror already exists. Maybe we don't need to prepare?")
                    raise UserAbortedException("User does not want to delete the savegame mirror")
            else:
                log.info(f"A savegame mirror exists at '{mirrorPath}' and no savegame exists at '{savegamePath}'. Looks like we are already prepared for using a ramdisk. Will not do anything.")
                return True
        else:
            if savegameExists:
                log.info(f"Savegame exists and no mirror exists, calling prepare.")
                self.ramdiskManager.prepare()
            else:
                log.info(f"No savegame exists at '{savegamePath}'. This is either a configuration error or we need to create one first.")
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
        if self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not execute ramdisk setup if the server is running. Please stop it first.")

        self.ramdiskManager.setup()

    def ramdiskUninstall(self, force=False):
        """
        Checks existence of savegame and mirror, offers the user the possibility to fix that, then proceeds to revert the ramdisk-install and -setup stuff
        
        if mirror and savegame: delete savegame, move mirror
        if mirror and nosavegame: move mirror
        if nomirror and savegame:  do nothing
        if nomirror and nosavegame: do nothing
        """
        if self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not execute ramdisk uninstall if the server is running. Please stop it first.")

        if not force and self.config.general.useRamdisk:
            log.error("Ramdisk usage is enabled in the configuration, can not uninstall the ramdisk usage when it is enabled.")
            raise AdminRequiredException("Ramdisk usage is enabled in the configuration, can not uninstall when it is enabled.")
        if force:
            log.warning("Forcing uninstall even though the configuration is set to not use a ramdisk")

        mirrorExists, mirrorPath = self.ramdiskManager.existsMirror()
        savegameExists, savegamePath = self.ramdiskManager.existsSavegame()

        if mirrorExists:
            if savegameExists:
                log.info(f"A savegame already exists at '{savegamePath}'. The ramdisk stuff is either already uninstalled, there is a configuration error or the savegame needs to be deleted.")
                if askUser(f"Delete old savegame at '{savegamePath}'? [yes/no] ", "yes"):
                    self.fileSystem.markForDelete(savegamePath)
                    self.fileSystem.commitDelete()
                    self.ramdiskManager.uninstall(force)
                else:
                    log.warning("Can not uninstall the file system as long as a savegame already exists. Maybe we don't need to uninstall?")
                    raise UserAbortedException("User does not want to delete the savegame")
            else:
                log.info(f"A savegame mirror exists at '{mirrorPath}' and no savegame exists at '{savegamePath}'")
                self.ramdiskManager.uninstall(force)
        else:
            if savegameExists:
                log.info(f"Savegame exists and no mirror exists. There file system is already ready to be used without a ramdisk.")
                return False
            else:
                log.info(f"No savegame exists at '{savegamePath}'. This is either a configuration error or none exists. You might need to create a new one later.")
                return False
            
    # def wipeEmptyPlayfieldsOld(self, dbLocation=None, wipeType=None, territory=None, dryrun=True, cleardiscoveredby=True):
    #     """
    #     Wipes all defined playfields with the defined wipetype, filtering out any playfield that has a player, player owned structure or terrain placeable on it.

    #     Optimized for speed and huge savegames.
    #     Takes about a minute to wipe 50k playfields on a 30GB savegame. 
    #     Comparison: EAH's "wipe empty playfield" function takes 36hs and does not take into account terrain placeables.
    #     """
    #     if not dryrun and self.dedicatedServer.isRunning():
    #         raise ServerNeedsToBeStopped("Can not execute wipe empty playfields with --nodryrun if the server is running. Please stop it first.")

    #     if dbLocation is None:
    #         dbLocation = self.fileSystem.getAbsolutePathTo("saves.games.savegame.globaldb")
    #     else:
    #         dbLocationPath = Path(dbLocation).resolve().absolute()
    #         if dbLocationPath.exists():
    #             dbLocation = str(dbLocationPath)
    #         else:
    #             raise WrongParameterError(f"DbLocation '{dbLocation}' is not a valid database location path.")

    #     availableTerritories = self.configService.getAvailableTerritories()
    #     atn = list(map(lambda x: x.name, availableTerritories))
    #     if territory and (territory in atn or territory == Territory.GALAXY):
    #         log.debug(f"valid territory selected '{territory}'")
    #     else:
    #         raise WrongParameterError(f"Territory '{territory}' not valid, must be one of: {Territory.GALAXY}, {', '.join(atn)}")

    #     wtl = WipeType.valueList()
    #     if wipeType and wipeType in wtl:
    #         log.debug(f"valid wipetype selected '{wipeType}'")
    #     else:
    #         raise WrongParameterError(f"Wipe type '{wipeType}' not valid, must be one of: {wtl}")
        
    #     log.info(f"Calling wipe empty playfields for dbLocation: '{dbLocation}' territory '{territory}', wipeType '{wipeType}', dryrun '{dryrun}', cleardiscoveredby '{cleardiscoveredby}'")
    #     self.wipeService.wipeTerritory(dbLocation, territory, WipeType.byName(wipeType), dryrun, cleardiscoveredby)

    def ramdiskRemount(self):
        """
        just unmounts and mounts the ramdisk again. Can be used when the ramdisk size configuration changed. Will just unmount and call the setup.
        """
        if self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not remount the ramdrive if the server is running. Please stop it first.")

        if not self.config.general.useRamdisk:
            log.error("Ramdisk usage is disabled in the configuration, remount the ramdisk if its not enabled.")
            raise AdminRequiredException("Ramdisk usage is disabled in the configuration, remount the ramdisk if its not enabled.")

        # just unmount the ramdisk, if it exists.
        ramdiskDriveLetter = self.config.ramdisk.drive
        if Path(ramdiskDriveLetter).exists():
            log.info(f"Unmounting ramdisk at '{ramdiskDriveLetter}'.")
            try:
                self.ramdiskManager.unmountRamdisk(driveLetter=ramdiskDriveLetter)
            except AdminRequiredException as ex:
                log.error(f"exception trying to unmount. Will check if its mounted at all")
                if self.ramdiskManager.checkRamdrive(driveLetter=ramdiskDriveLetter):
                    raise AdminRequiredException(f"Ramdisk is still mounted, can't recuperate from the error here. Exception: {ex}")
                else:
                    log.info(f"There is no more ramdisk mounted as '{ramdiskDriveLetter}', will continue.")
            log.info(f"Ramdisk at '{ramdiskDriveLetter}' unmounted")
        else:
            log.info(f"Ramdisk at '{ramdiskDriveLetter}' did not exist, will assume it is not mounted")
        
        log.info("Calling ramdisk setup to mount it again with the current configuration and sync the savegame again.")
        self.ramdiskSetup()

    def clearDiscovered(self, dblocation, dryrun=True, territoryName=None, inputFile=None, inputNames=None):
        """
        resolves the given system- and playfieldnames from the file or the names array and clears the discovered by info for these completely
        The game saves an entry for every player, even if it was discovered before, so this tool will delete them all so it goes back to "Undiscovered".
        """
        dbLocationPath = self.getDBLocationPath(dblocation)

        territory = None
        systemAndPlayfieldNames = None

        if territoryName:
            territory = self.wipeService.getCustomTerritoryByName(territoryName)
            if territoryName == Territory.GALAXY:
                territory = Territory(Territory.GALAXY, 0,0,0,99999999)
            log.info(f"Requested clearing discovered-by infos for territory '{territory.name}'.")

        if inputFile:
            systemAndPlayfieldNames = self.readSystemAndPlayfieldListFromFile(inputFile, inputNames)
            log.info(f"Requested clearing discovered-by infos for {len(systemAndPlayfieldNames)} names from the file {inputFile}.")
        
        self.wipeService.clearDiscoveredByInfo(dbLocationPath=dbLocationPath, territory=territory, systemAndPlayfieldNames=systemAndPlayfieldNames, dryrun=dryrun)

    def getDBLocationPath(self, dbLocation):
        """
        resolves the given dbLocation and returns the absolute path or uses the global db if dbLocation is None
        """
        if dbLocation is None:
            return self.fileSystem.getAbsolutePathTo("saves.games.savegame.globaldb")
        else:
            dbLocationPath = Path(dbLocation).resolve()
            if dbLocationPath.exists():
                return dbLocationPath
            else:
                raise WrongParameterError(f"DbLocation '{dbLocation}' is not a valid database location path.")

    def readSystemAndPlayfieldListFromFile(self, inputFile, inputNames: List[str]=None):
        """
        retrieve the list of systems and playfields from the given file
        """
        names = []
        if inputNames:
            names.extend(inputNames)
        if inputFile:
            inputFilePath = Path(inputFile).resolve()
            if inputFilePath.exists() and inputFilePath.is_file():
                with open(inputFilePath, "r") as file:
                    names.extend([line.rstrip('\n') for line in file.readlines()])
            else:
                raise WrongParameterError(f"Input file at '{inputFilePath}' not found")
        return names

    def purgeEmptyPlayfieldsOld(self, dbLocation=None, dryrun=True, cleardiscoveredby=True, minimumage=30, leavetemplates=False, force=False):
        """
        checks for playfields that haven't been visited for the minimumage days and purges them from the filesystem
        """
        if not dryrun and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not purge empty playfields with --nodryrun if the server is running. Please stop it first.")

        if dbLocation is None:
            dbLocation = self.fileSystem.getAbsolutePathTo("saves.games.savegame.globaldb")
        else:
            dbLocationPath = Path(dbLocation).resolve()
            if dbLocationPath.exists() and dbLocationPath.is_file():
                dbLocation = str(dbLocationPath)
            else:
                raise WrongParameterError(f"DbLocation '{dbLocation}' is not a valid database location path.")

        if minimumage < 1:
            raise WrongParameterError(f"Minimum age must be greater than or equal to 1, you chose '{minimumage}'")

        try:
            log.info(f"Calling purge empty playfields for dbLocation: '{dbLocation}', minimumage '{minimumage}', dryrun '{dryrun}', cleardiscoveredby '{cleardiscoveredby}', leavetemplates '{leavetemplates}', force '{force}'")
            self.wipeService.purgeEmptyPlayfields(dbLocation=dbLocation, minimumage=minimumage, dryrun=dryrun, cleardiscoveredby=cleardiscoveredby, leavetemplates=leavetemplates, force=force)
        except UserAbortedException as ex:
            log.warning(f"User aborted the operation, nothing deleted.")

    def cleanupRemovedEntities(self, savegame=None, dryrun=True, force=False):
        """
        will purge all entity folders in the shared folder of entities that are marked as deleted in the database
        """
        savegamePath = self.getSavegamePath(savegame)

        isCurrentSaveGame = savegamePath.samefile(self.fileSystem.getAbsolutePathTo("saves.games.savegame"))
        if not dryrun and isCurrentSaveGame and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not clean up shared removed entities of the current savegame with --nodryrun if the server is running. Please stop it first.")

        log.info(f"Purging removed entities for savegame: '{savegamePath}', dryrun '{dryrun}'")
        count = self.wipeService.purgeRemovedEntities(savegamePath=savegamePath, dryrun=dryrun)
        if not count or count == 0:
            return

        if not dryrun:
            if force:
                result, elapsedTime = self.fileSystem.commitDelete(override="yes")
                log.info(f"Deleted '{count}' folders with removed entities in the Shared folder, elapsed time: {elapsedTime}")
            else:
                result, elapsedTime = self.fileSystem.commitDelete()
                log.info(f"Deleted '{count}' folders with removed entities in the Shared folder, elapsed time: {elapsedTime}")
        else:
            log.info(f"This is a dryrun, did not delete '{count}' entity folders")

    def purgeWipedPlayfieldsOld(self, dryrun=True, leavetemplates=False, force=False):
        """
        search for wipeinfo.txt containing "all" for all playfields and purge those (and their templates) completely.
        """
        if not dryrun and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not purge wiped playfields with --nodryrun if the server is running. Please stop it first.")

        log.info(f"Executing purge on wiped playfields: dryrun '{dryrun}', leavetemplates '{leavetemplates}', force '{force}'")
        with Timer() as timer:
            wipedPlayfieldNames, playfieldCount, templateCount = self.wipeService.purgeWipedPlayfields(leavetemplates)
        log.info(f"Marked {playfieldCount} playfield folders and {templateCount} template folders for deletion, time elapsed: {timer.elapsedTime}")

        if len(wipedPlayfieldNames) < 1:
            log.info(f"Nothing to purge")
            return

        if dryrun:
            fileName = f"esm-purgewipedplayfields.lst"
            with open(fileName, "w", encoding='utf-8') as file:
                file.writelines([line + '\n' for line in wipedPlayfieldNames])
            log.warning(f"Dry mode is active, exported list of playfields to purge as '{fileName}'")
        else:
            if force:
                result, elapsedTime = self.fileSystem.commitDelete(override="yes")
                log.info(f"Purged {playfieldCount} playfield and {templateCount} template folders, time elapsed: {elapsedTime}.")
            else:
                try:
                    result, elapsedTime = self.fileSystem.commitDelete()
                    log.info(f"Purged {playfieldCount} playfield and {templateCount} template folders, time elapsed: {elapsedTime}.")
                except UserAbortedException as ex:
                    log.warning("User aborted operation, nothing was deleted.")
    
    def cleanupSharedFolder(self, savegame=None, dryrun=True, force=False):
        """
        will clean up the shared folder, after checking the entries against the entities table in the db.

        if savegame is given, will use that instead of the current savegame, also the server may keep running.
        """
        #log.debug(f"{__name__}.cleanupSharedFolder: savegame: '{savegame}', dryrun: '{dryrun}', force: '{force}'")

        savegamePath = self.getSavegamePath(savegame)

        isCurrentSaveGame = savegamePath.samefile(self.fileSystem.getAbsolutePathTo("saves.games.savegame"))
        if not dryrun and isCurrentSaveGame and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not clean up shared folders of the current savegame with --nodryrun if the server is running. Please stop it first.")

        log.info(f"Cleaning up shared folder for savegamePath: '{savegamePath}', dryrun '{dryrun}', force '{force}'")
        try:
            self.wipeService.cleanUpSharedFolder(savegamePath=savegamePath, dryrun=dryrun, force=force)
        except UserAbortedException:
            log.info(f"User aborted clean up execution.")

    def getSavegamePath(self, savegame=None):
        if savegame is None:
            return self.fileSystem.getAbsolutePathTo("saves.games.savegame")
        else:
            savegamePath = Path(savegame).resolve()
            if savegamePath.exists() and savegamePath.is_dir():
                return savegamePath
            else:
                raise WrongParameterError(f"Savegame path '{savegamePath}' is not a valid savegame location path.")

    def openSocket(self, port=6969, interval=0, tries=0, raiseException=False):
        """
        open a socket for this application to make sure only one instance can run at a time (with given port).
        supports interval and tries if you want to check and wait for a longer period.
        """
        self.serverSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        timeLeft = tries * interval + 1
        while timeLeft >= 0:
            try:
                self.serverSocket.bind(('localhost', port))
                return
            except OSError as ex:
                if timeLeft > 1:
                    log.warning(f"Port {port} probably already bound, is esm already running? Will wait {interval} seconds to retry. Time left for tries: {timeLeft}")
                    time.sleep(interval)
                    timeLeft = timeLeft - interval
                elif timeLeft == 0:
                    log.error(f"Giving up on waiting. You will have to check yourself why there is another esm instance running.")
                    timeLeft = -1
                    if raiseException:
                        raise AdminRequiredException(f"Giving up on waiting. You will have to check yourself why there is another esm instance running.")
                    sys.exit(ExitCodes.INSTANCE_RUNNING_GAVE_UP)
                else:
                    log.debug(f"If you need to use another port for this application, set it in the config.")
                    log.error(f"Looks like the tool is already running!")
                    if raiseException:
                        raise AdminRequiredException("Looks like the tool is already running!")
                    sys.exit(ExitCodes.INSTANCE_RUNNING)

    def checkRequirements(self, admin=True):
        """
        does a series of tests for integrity of the scripts, config, game, os and whatnot.
        """
        # check gamename, this will make sure the yaml was read, parsed and contains a valid game name.
        try:
            gameName = self.config.dedicatedConfig.GameConfig.GameName
            scenario = self.config.dedicatedConfig.GameConfig.CustomScenario
            dedicatedYaml = self.config.paths.install.joinpath(self.config.server.dedicatedYaml).absolute()
            log.info(f"Game name is '{gameName}' scenario is '{scenario}' - (read from dedicated yaml at '{dedicatedYaml}')")
        except KeyError as ex:
            log.error(f"{ex}")

        self.fileSystem.check8Dot3NameGeneration()

        self.fileSystem.testLinkGeneration()

        self.fileSystem.testRobocopy()

        if self.config.general.useRamdisk:
            try:
                path = self.ramdiskManager.checkAndGetOsfMountPath()
                log.info(f"'{path}' found")
            except RequirementsNotFulfilledError as ex:
                log.error(f"{ex}")
        else:
            log.info("ramdisk usage is disabled")

        try:
            path = self.backupService.checkAndGetPeaZipPath()
            log.info(f"'{path}' found")
        except RequirementsNotFulfilledError as ex:
            log.error(f"{ex}")

        emprc = ServiceRegistry.get(EsmEmpRemoteClientService)
        try:
            path = emprc.checkAndGetEmpRemoteClientPath()
            log.info(f"'{path}' found")
        except RequirementsNotFulfilledError as ex:
            log.error(f"{ex}")

        try:
            path = self.steamService.checkAndGetSteamCmdExecutable()
            log.info(f"'{path}' found")
        except RequirementsNotFulfilledError as ex:
            log.error(f"{ex}")

        log.info(f"Checking if there is enough space available for backups.")
        try:
            self.backupService.assertEnoughFreeSpace()
        except AdminRequiredException as ex:
            log.error(f"{ex}")


        log.info(f"Checking if there is enough space to start the game.")
        if self.config.general.useRamdisk:
            ramdriveMounted = self.ramdiskManager.checkRamdrive(simpleCheck=True)
            if ramdriveMounted:
                try:
                    self.dedicatedServer.assertEnoughFreeDiskspace()
                except AdminRequiredException as ex:
                    log.error(f"{ex}")
            else:
                log.warning(f"no ramdisk mounted, can't check its free space now. You may want to run ramdisk-setup first.")
        else:
            try:
                self.dedicatedServer.assertEnoughFreeDiskspace()
            except AdminRequiredException as ex:
                log.error(f"{ex}")

        if admin and self.config.general.useRamdisk:
            log.info(f"Checking if you have the required privileges to run access ramdisks at all")
            ramdriveMounted = self.ramdiskManager.checkRamdrive(simpleCheck=False)
            if not ramdriveMounted:
                log.warning(f"Could either not execute or not access the ramdisk with osf mount. Either it is not mounted yet or you may not have admin privileges to execute osfmount.")

        if self.config.dedicatedConfig.GameConfig.SharedDataURL is not None:
            log.info(f"checking if the shared data url is available")
            self.dedicatedServer.assertSharedDataURLIsAvailable()

            if self.config.downloadtool.useSharedDataURLFeature is False:
               log.warn(f"The dedicated yaml defines a shared data url, but esm is configured to NOT use it for the download tool. This is ok if you are using something different than esm to server the shared data zip.")

        # clean up. the only time we call the fstool directly.
        FsTools.deleteDir(Path(f"{self.config.paths.install}/{self.config.foldernames.esmtests}").resolve(), recursive=True)

    def checkAndWaitForOtherInstances(self):
        """ 
        enable multiple instance check and wait if waitForPort was set. If the instance ends, 
        in the configured interval and amount of tries this will return gracefully, if not an exception will be thrown
        """
        port = self.config.general.bindingPort
        if self.waitForPort:
            interval = self.config.general.multipleInstanceWaitInterval
            tries = self.config.general.multipleInstanceWaitTries
            self.openSocket(port, interval=interval, tries=tries)
        else:
            self.openSocket(port)

    def wipeTool(self, inputFilePath: Path=None, territoryName=None, wipetype: WipeType=None, cleardiscoveredby=True, minage: int=None, dbLocation=None, dryrun=True):
        """
        the mighty wipe tool
        """
        #log.debug(f"{__name__}.{sys._getframe().f_code.co_name} called with params: {locals()}")

        if not dryrun and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not execute tool-wipe with --nodryrun if the server is running. Please stop it first.")

        dbLocationPath = self.getDBLocationPath(dbLocation)

        systemAndPlayfieldNames = None
        territory = None

        if inputFilePath is not None:
            systemAndPlayfieldNames = self.readSystemAndPlayfieldListFromFile(inputFilePath)
            log.info(f"calling wipetool for {len(systemAndPlayfieldNames)} names, wipetype={wipetype.value.name}, cleardiscoveredby={cleardiscoveredby}, minage={minage}, dbLocationPath={dbLocationPath}, dryrun={dryrun}")
        else:
            territory = self.wipeService.getCustomTerritoryByName(territoryName)
            if territoryName == Territory.GALAXY:
                territory = Territory(Territory.GALAXY, 0,0,0,99999999)
            log.info(f"calling wipetool for territory {territory.name}, wipetype={wipetype.value.name}, cleardiscoveredby={cleardiscoveredby}, minage={minage}, dbLocationPath={dbLocationPath}, dryrun={dryrun}")

        self.wipeService.wipeTool(systemAndPlayfieldNames, territory, wipetype, cleardiscoveredby, minage, dbLocationPath, dryrun)

    def startSharedDataServer(self, resume=False):
        """
        starts the shared data server
        """
        if resume:
            self.sharedDataServer.resume()
        else:
            self.sharedDataServer.start()

    def startHaimsterConnector(self):
        """
            starts the haimster connector (in a separate thread) and returns immediately
        """
        if self.config.communication.haimsterEnabled:
            self.openSocket(port=self.config.communication.incomingMessageHostPort, interval=5, tries=10, raiseException=True)
            return self.haimsterConnector.initialize()

    def startHaimsterConnectorAndWait(self):
        """
            Starts the haimster connector (in a separate thread) and waits for it to exit, ignoring the configuration flag
            This can be used if you want to start the haimster connector in a separate process with a tool call
        """
        self.openSocket(port=self.config.communication.incomingMessageHostPort, interval=5, tries=10, raiseException=True)
        shouldExit = self.haimsterConnector.initialize()
        while not shouldExit.is_set():
            time.sleep(1)

    def exportChatLog(self, dblocation: str=None, filename: str="chatlog.json", format: str="json", excludeNames: List[str] = [], includeNames: List[str] = []):
        """
            exports the chat log from given database to filename with given format.
        """
        dbLocationPath = self.getDBLocationPath(dblocation)
        self.gameChatService.exportChatLog(dbLocationPath, filename, format, excludeNames, includeNames)
