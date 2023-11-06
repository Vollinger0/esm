from functools import cached_property
import logging
from pathlib import Path
import socket
import time
from esm.EsmEpmRemoteClientService import EsmEpmRemoteClientService
from esm.Exceptions import AdminRequiredException, ExitCodes, RequirementsNotFulfilledError, ServerNeedsToBeStopped, UserAbortedException, WrongParameterError
from esm.DataTypes import Territory, WipeType
from esm.EsmBackupService import EsmBackupService
from esm.EsmDeleteService import EsmDeleteService
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmLogger import EsmLogger
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer, GfxMode
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.EsmSteamService import EsmSteamService
from esm.EsmWipeService import EsmWipeService
from esm.ServiceRegistry import ServiceRegistry
from esm.Tools import Timer, askUser, isDebugMode, monkeyPatchAllFSFunctionsForDebugMode

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
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)

    def __init__(self, configFileName="esm-base-config.yaml", customConfigFileName="esm-custom-config.yaml", caller=__name__, fileLogLevel=logging.DEBUG, streamLogLevel=logging.DEBUG, waitForPort=False):
        self.configFilename = configFileName
        self.customConfigFileName = customConfigFileName
        self.caller = caller
        self.waitForPort = waitForPort

        # set up logging
        self.logFile = Path(caller).stem + ".log"
        EsmLogger.setUpLogging(self.logFile, fileLogLevel=fileLogLevel, streamLogLevel=streamLogLevel)

        # set up config
        self.configFilePath = Path(configFileName).absolute().resolve()
        self.customConfigFilePath = Path(customConfigFileName).absolute().resolve()
        context = {           
            'configFilePath': self.configFilePath,
            'customConfigFileName': self.customConfigFilePath,
            'logFile': self.logFile,
            'caller': self.caller
        }
        esmConfig = EsmConfigService(configFilePath=self.configFilePath, customConfigFilePath=self.customConfigFilePath, context=context)
        ServiceRegistry.register(esmConfig)

        # in debug mode, monkey patch all functions that may alter the file system or execute other programs.
        if isDebugMode(esmConfig):
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
        Will start the server (and the ramdisk synchronizer, if ramdisk is enabled). Function returns once the server has been started.
        """
        if self.dedicatedServer.isRunning():
            log.warning("A server is already running!")
            return

        self.startSynchronizer()
        
        # start the server
        log.info(f"Starting the dedicated server")
        return self.dedicatedServer.startServer()

    def startSynchronizer(self):
        """
        starts the ramdisk synchronizer if ramdisk and the synchronizer are enabled and properly configured
        """
        if self.config.general.useRamdisk:
            syncInterval = self.config.ramdisk.synchronizeRamToMirrorInterval
            if syncInterval > 0:
                # start the synchronizer
                log.info(f"Starting ram2mirror synchronizer with interval {syncInterval}")
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
        log.info(f"Server started. Waiting until it shut down or stopped existing.")
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
            log.info(f"Server shut down or not running any more.")

    def resumeServerAndWait(self):
        """
        resumes execution for when the gameserver is probably still running
        """
        if not self.dedicatedServer.isRunning():
            log.warning("No running gameserver found.")
            return
        # we found a server, then start synchronizer if enabled
        self.startSynchronizer()
        
        log.info(f"Running server found. Waiting until it shut down or stopped existing.")
        self.waitForEnd()

        log.info(f"Server shut down. Executing shutdown tasks.")
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
        return self.steamService.installGame()
    
    def updateGame(self, nosteam=False):
        """
        calls steam to update the game via steam and call any additionally configured steps (like updating the scenario, copying files etc.)
        """
        return self.steamService.updateGame(nosteam=nosteam)
    
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
        if self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not execute ramdisk prepare if the server is running. Please stop it first.")

        mirrorExists, mirrorPath = self.ramdiskManager.existsMirror()
        savegameExists, savegamePath = self.ramdiskManager.existsSavegame()

        if mirrorExists:
            if savegameExists:
                log.info(f"A savegame mirror exists at {mirrorPath}. The file system is either already prepared, there is a configuration error or the savegame mirror needs to be deleted.")
                if askUser(f"Delete old savegame mirror at {mirrorPath}? [yes/no] ", "yes"):
                    self.fileSystem.markForDelete(mirrorPath)
                    self.fileSystem.commitDelete()
                    self.ramdiskManager.prepare()
                else:
                    log.warning("Can not prepare the file system for ramdisk usage as long as a savegamemirror already exists. Maybe we don't need to prepare?")
                    raise UserAbortedException("User does not want to delete the savegame mirror")
            else:
                log.info(f"A savegame mirror exists at {mirrorPath} and no savegame exists at {savegamePath}. Looks like we are already prepared for using a ramdisk. Will not do anything.")
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
        if self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not execute ramdisk setup if the server is running. Please stop it first.")

        self.ramdiskManager.setup()

    def ramdiskUninstall(self, force=False):
        """
        Checks existence of savegame and mirror, offers the user the possibility to fix that, then proceeds to revert the ramdisk-prepare and -setup stuff
        
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
            
    def wipeEmptyPlayfields(self, dbLocation=None, wipeType=None, territory=None, nodryrun=False, nocleardiscoveredby=False):
        """
        Wipes all defined playfields with the defined wipetype, filtering out any playfield that has a player, player owned structure or terrain placeable on it.

        Optimized for speed and huge savegames.
        Takes about a minute to wipe 50k playfields on a 30GB savegame. 
        Comparison: EAH's "wipe empty playfield" function takes 36hs and does not take into account terrain placeables.
        """
        if nodryrun and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not execute wipe empty playfields with --nodryrun if the server is running. Please stop it first.")

        if dbLocation is None:
            dbLocation = self.fileSystem.getAbsolutePathTo("saves.games.savegame.globaldb")
        else:
            dbLocationPath = Path(dbLocation).resolve().absolute()
            if dbLocationPath.exists():
                dbLocation = str(dbLocationPath)
            else:
                raise WrongParameterError(f"DbLocation '{dbLocation}' is not a valid database location path.")

        availableTerritories = self.wipeService.getAvailableTerritories()
        atn = list(map(lambda x: x.name, availableTerritories))
        if territory and (territory in atn or territory == Territory.GALAXY):
            log.debug(f"valid territory selected '{territory}'")
        else:
            raise WrongParameterError(f"Territory '{territory}' not valid, must be one of: {Territory.GALAXY}, {', '.join(atn)}")

        wtl = WipeType.valueList()
        if wipeType and wipeType in wtl:
            log.debug(f"valid wipetype selected '{wipeType}'")
        else:
            raise WrongParameterError(f"Wipe type '{wipeType}' not valid, must be one of: {wtl}")
        
        log.info(f"Calling wipe empty playfields for dbLocation: '{dbLocation}' territory '{territory}', wipeType '{wipeType}', nodryrun '{nodryrun}', nocleardiscoveredby '{nocleardiscoveredby}'")
        self.wipeService.wipeEmptyPlayfields(dbLocation, territory, WipeType.byName(wipeType), nodryrun, nocleardiscoveredby)

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
            log.info(f"Unmounting ramdisk at {ramdiskDriveLetter}.")
            try:
                self.ramdiskManager.unmountRamdisk(driveLetter=ramdiskDriveLetter)
            except AdminRequiredException as ex:
                log.error(f"exception trying to unmount. Will check if its mounted at all")
                if self.ramdiskManager.checkRamdrive(driveLetter=ramdiskDriveLetter):
                    raise AdminRequiredException(f"Ramdisk is still mounted, can't recuperate from the error here. Exception: {ex}")
                else:
                    log.info(f"There is no more ramdisk mounted as {ramdiskDriveLetter}, will continue.")
            log.info(f"Ramdisk at {ramdiskDriveLetter} unmounted")
        else:
            log.info(f"Ramdisk at {ramdiskDriveLetter} did not exist, will assume it is not mounted")
        
        log.info("Calling ramdisk setup to mount it again with the current configuration and sync the savegame again.")
        self.ramdiskSetup()

    def clearDiscoveredByInfos(self, dbLocation, nodryrun, inputFile=None, inputNames=None):
        """
        resolves the given system- and playfieldnames from the file or the names array and clears the discovered by info for these completely
        The game saves an entry for every player, even if it was discovered before, so this tool will delete them all so it goes back to "Undiscovered".
        """
        names = []
        if inputNames:
            names.extend(inputNames)
        if inputFile:
            inputFilePath = Path(inputFile).resolve()
            if inputFilePath.exists():
                with open(inputFilePath, "r") as file:
                    names.extend([line.rstrip('\n') for line in file.readlines()])
            else:
                raise WrongParameterError(f"input file at '{inputFilePath}' not found")
            
        if dbLocation is None:
            dbLocation = self.fileSystem.getAbsolutePathTo("saves.games.savegame.globaldb")
        else:
            dbLocationPath = Path(dbLocation).resolve()
            if dbLocationPath.exists():
                dbLocation = str(dbLocationPath)
            else:
                raise WrongParameterError(f"DbLocation '{dbLocation}' is not a valid database location path.")
        log.info(f"Clearing discovered by infos for {len(names)} names.")
        self.wipeService.clearDiscoveredByInfo(dbLocation=dbLocation, names=names, nodryrun=nodryrun)

    def purgeEmptyPlayfields(self, dbLocation=None, nodryrun=False, nocleardiscoveredby=False, minimumage=30, leavetemplates=False, force=False):
        """
        checks for playfields that haven't been visited for the minimumage days and purges them from the filesystem
        """
        if nodryrun and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not purge empty playfields with --nodryrun if the server is running. Please stop it first.")

        if dbLocation is None:
            dbLocation = self.fileSystem.getAbsolutePathTo("saves.games.savegame.globaldb")
        else:
            dbLocationPath = Path(dbLocation).resolve().absolute()
            if dbLocationPath.exists():
                dbLocation = str(dbLocationPath)
            else:
                raise WrongParameterError(f"DbLocation '{dbLocation}' is not a valid database location path.")

        if minimumage < 1:
            raise WrongParameterError(f"Minimum age in days is 1, you chose {minimumage}")

        try:
            log.info(f"Calling purge empty playfields for dbLocation: '{dbLocation}', minimumage '{minimumage}', nodryrun '{nodryrun}', nocleardiscoveredby '{nocleardiscoveredby}', leavetemplates '{leavetemplates}', force '{force}")
            self.wipeService.purgeEmptyPlayfields(dbLocation=dbLocation, minimumage=minimumage, nodryrun=nodryrun, nocleardiscoveredby=nocleardiscoveredby, leavetemplates=leavetemplates, force=force)
        except UserAbortedException as ex:
            log.warning(f"User aborted the operation, nothing deleted.")

    def purgeRemovedEntities(self, dbLocation=None, nodryrun=False, force=False):
        """
        will purge all entity folders in the shared folder of entities that are marked as deleted in the database
        """
        if nodryrun and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not purge removed entities with --nodryrun if the server is running. Please stop it first.")

        if dbLocation is None:
            dbLocation = self.fileSystem.getAbsolutePathTo("saves.games.savegame.globaldb")
        else:
            dbLocationPath = Path(dbLocation).resolve().absolute()
            if dbLocationPath.exists():
                dbLocation = str(dbLocationPath)
            else:
                raise WrongParameterError(f"DbLocation '{dbLocation}' is not a valid database location path.")

        log.info(f"Purging removed entities for dbLocation: '{dbLocation}', nodryrun '{nodryrun}'")
        count = self.wipeService.purgeRemovedEntities(dbLocation=dbLocation, nodryrun=nodryrun)
        if nodryrun:
            if force:
                result, elapsedTime = self.fileSystem.commitDelete(override="yes")
                log.info(f"Deleted {count} folders with removed entities in the Shared folder, elapsed time: {elapsedTime}")
            else:
                try:
                    result, elapsedTime = self.fileSystem.commitDelete()
                    log.info(f"Deleted {count} folders with removed entities in the Shared folder, elapsed time: {elapsedTime}")
                except UserAbortedException as ex:
                    log.warning("User aborted operation, nothing was deleted.")

    def purgeWipedPlayfields(self, nodryrun=False, leavetemplates=False, force=False):
        """
        search for wipeinfo.txt containing "all" for all playfields and purge those (and their templates) completely.
        """
        if nodryrun and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not purge wiped playfields with --nodryrun if the server is running. Please stop it first.")

        log.info(f"Executing purge on wiped playfields: nodryrun '{nodryrun}', leavetemplates '{leavetemplates}', force '{force}'")
        with Timer() as timer:
            wipedPlayfieldNames, playfieldCount, templateCount = self.wipeService.purgeWipedPlayfields(leavetemplates)
        log.info(f"Marked {playfieldCount} playfield folders and {templateCount} template folders for deletion, time elapsed: {timer.elapsedTime}")

        if len(wipedPlayfieldNames) < 1:
            log.info(f"Nothing to purge")
            return

        if nodryrun:
            if force:
                result, elapsedTime = self.fileSystem.commitDelete(override="yes")
                log.info(f"Purged {playfieldCount} playfield and {templateCount} template folders, time elapsed: {elapsedTime}.")
            else:
                try:
                    result, elapsedTime = self.fileSystem.commitDelete()
                    log.info(f"Purged {playfieldCount} playfield and {templateCount} template folders, time elapsed: {elapsedTime}.")
                except UserAbortedException as ex:
                    log.warning("User aborted operation, nothing was deleted.")
        else:
            fileName = f"esm-purgewipedplayfields.lst"
            with open(fileName, "w", encoding='utf-8') as file:
                file.writelines([line + '\n' for line in wipedPlayfieldNames])
            log.warning(f"Dry mode is active, exported list of playfields to purge as {fileName}")
    
    def cleanupSharedFolder(self, dbLocation=None, nodryrun=False, force=False):
        """
        will clean up the shared folder, after checking the entries against the entities table in the db.
        """
        if nodryrun and self.dedicatedServer.isRunning():
            raise ServerNeedsToBeStopped("Can not clean up shared folders with --nodryrun if the server is running. Please stop it first.")

        if dbLocation is None:
            dbLocation = self.fileSystem.getAbsolutePathTo("saves.games.savegame.globaldb")
        else:
            dbLocationPath = Path(dbLocation).resolve().absolute()
            if dbLocationPath.exists():
                dbLocation = str(dbLocationPath)
            else:
                raise WrongParameterError(f"DbLocation '{dbLocation}' is not a valid database location path.")

        log.info(f"Cleaning up shared folder for dbLocation: '{dbLocation}', nodryrun '{nodryrun}', force '{force}'")
        try:
            self.wipeService.cleanUpSharedFolder(dbLocation=dbLocation, nodryrun=nodryrun, force=force)
        except UserAbortedException:
            log.info(f"User aborted clean up execution.")

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
                    log.warning(f"Port {port} probably already bound, is the script already running? Will wait {interval} seconds to retry. Time left for tries: {timeLeft}")
                    time.sleep(interval)
                    timeLeft = timeLeft - interval
                elif timeLeft == 0:
                    log.error(f"Giving up on waiting. You will have to check yourself why there is another script running.")
                    timeLeft = -1
                    if raiseException:
                        raise AdminRequiredException(f"Giving up on waiting. You will have to check yourself why there is another script running.")
                    exit(ExitCodes.INSTANCE_RUNNING_GAVE_UP)
                else:
                    log.debug(f"If you need to use another port for this application, set it in the config.")
                    log.error(f"Looks like the tool is already running!")
                    if raiseException:
                        raise AdminRequiredException("Looks like the tool is already running!")
                    exit(ExitCodes.INSTANCE_RUNNING)

    def checkIntegrity(self, noadmin=False):
        """
        does a series of tests for integrity of the scripts, config, game, os and whatnot.
        """
        self.fileSystem.check8Dot3NameGeneration()

        self.fileSystem.testLinkGeneration()

        try:
            path = self.ramdiskManager.checkAndGetOsfMountPath()
            log.info(f"{path} found")
        except RequirementsNotFulfilledError as ex:
            log.error(f"{ex}")

        try:
            path = self.backupService.checkAndGetPeaZipPath()
            log.info(f"{path} found")
        except RequirementsNotFulfilledError as ex:
            log.error(f"{ex}")

        erc = ServiceRegistry.get(EsmEpmRemoteClientService)
        try:
            path = erc.checkAndGetEpmRemoteClientPath()
            log.info(f"{path} found")
        except RequirementsNotFulfilledError as ex:
            log.error(f"{ex}")

        try:
            path = self.steamService.checkAndGetSteamCmdExecutable()
            log.info(f"{path} found")
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

        if not noadmin and self.config.general.useRamdisk:
            log.info(f"Checking if you have the required privileges to run access ramdisks at all")
            ramdriveMounted = self.ramdiskManager.checkRamdrive(simpleCheck=False)
            if not ramdriveMounted:
                log.error(f"Could either not execute or not access the ramdisk with osf mount. You require admin privileges for ramdisk mode.")

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
