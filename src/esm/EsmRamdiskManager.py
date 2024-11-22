from functools import cached_property
import logging
import subprocess
import time
from pathlib import Path
from threading import Event, Thread
from esm.ConfigModels import MainConfig
from esm.EsmCommunicationService import EsmCommunicationService
from esm.exceptions import AdminRequiredException, NoSaveGameFoundException, NoSaveGameMirrorFoundException, RequirementsNotFulfilledError, NoSaveGameMirrorFoundException, SaveGameFoundException
from esm.EsmConfigService import EsmConfigService
from esm.EsmFileSystem import EsmFileSystem
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import Timer

log = logging.getLogger(__name__)

@Service
class EsmRamdiskManager:
    """
    class that manages anything related to the ramdisk, that includes install, setup, deinstall, syncs and so on.
    
    """
    def __init__(self, config=None, fileSystem=None):
        if config:
            self.config = config
        if fileSystem:
            self.fileSystem = fileSystem

        self.synchronizerShutdownEvent = None
        self.synchronizerThread = None

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config

    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)

    @cached_property
    def communication(self) -> EsmCommunicationService:
        return ServiceRegistry.get(EsmCommunicationService)

    def prepare(self):
        """
        Actually takes a non-ramdisk filestructure and converts it into a ramdisk filestructure

        Moves a savegame to the hdd savegame mirror location. Will throw exceptions of there is no savegame, the mirror exists or ramdisk is disabled.
        """
        if not self.config.general.useRamdisk:
            log.error("Ramdisk usage is disabled in the configuration, can not prepare for ramdisk usage when it is disabled.")
            raise AdminRequiredException("Ramdisk usage is disabled in the configuration, can not prepare for ramdisk usage when it is disabled.")

        savegameExists, savegameFolderPath = self.existsSavegame()
        # check that there is a savegame
        if savegameExists:
            log.debug(f"Savegame exists at '{savegameFolderPath}'")
        else:
            log.error(f"Savegame does not exist at '{savegameFolderPath}'. Either the configuration is wrong or you may want to create one.")
            raise NoSaveGameFoundException(f"no savegame found at {savegameFolderPath}")

        mirrorExists, mirrorFolderPath = self.existsMirror()
        # check that there is no savegame mirror
        if not mirrorExists:
            log.debug(f"{mirrorFolderPath} does not exist yet")
        else:
            log.error(f"Savegame mirror does exist already at '{mirrorFolderPath}'. Either the configuration is wrong or this has been installed already, or the folder needs to be deleted.")
            raise NoSaveGameMirrorFoundException(f"savegame mirror at '{mirrorFolderPath}' already exists.")

        # move the savegame to the hddmirror folder
        self.fileSystem.moveFileTree("saves.games.savegame", "saves.gamesmirror.savegamemirror", 
                            f"Moving savegame to new location, this may take some time if your savegame is large already!")
        
    def setup(self):
        """
        sets up the ramdisk itself, and copies over the data from the hdd mirror
        optionally also sets up the externalized template stuff, if its enabled
        """
        # check and mount the ramdisk
        log.debug("check and mount ramdisk")
        ramdiskDrive = Path(self.config.ramdisk.drive)
        ramdiskSize = Path(self.config.ramdisk.size)
        if ramdiskDrive.exists(): 
            log.info(f"{ramdiskDrive} already exists as a drive, assuming this is our ramdrive. If its not, please use another drive letter in the configuration.")
        else:
            log.info(f"{ramdiskDrive} does not exist")
            self.mountRamdrive(ramdiskDrive, ramdiskSize)

        # create the link savegame -> ramdisk
        link = self.fileSystem.getAbsolutePathTo("saves.games.savegame")
        linkTarget = self.fileSystem.getAbsolutePathTo("ramdisk.savegame", prefixInstallDir=False)
        if not linkTarget.exists():
            linkTarget.mkdir()
        if FsTools.isHardLink(link):
            log.debug(f"{link} exists and is already a hardlink")
        else:
            self.fileSystem.createHardLink(link, linkTarget)

        log.debug("check for externalizing templates")
        # set up the link from ramdisk/templates -> hddmirror_templates
        if self.config.general.externalizeTemplates==True:
            self.externalizeTemplates()
        else:
            log.warning("externalizing templates is disabled. If you have a huge savegame, consider enabling this to reduce ramdisk usage.")

        # sync the mirror to the ramdisk
        mirrorExists, mirrorPath = self.existsMirror()
        if not mirrorExists:
            raise NoSaveGameMirrorFoundException(f"{mirrorPath} does not exist! Is the configuration correct? Did you call the install action before calling the setup?")
        log.info("Syncing mirror to ram")
        with Timer() as timer:
            self.syncMirrorToRam()
        log.info(f"Syncing mirror to ram took {timer.elapsedTime}.")
        log.info("Setup completed, you may now start the server")

    def externalizeTemplates(self):
        """
        will move the savegame template folder from the ram back to the hdd, in a separate mirror folder and create a hardlink
        """
        savegameTemplatesPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.templates")
        mirrorTemplatesPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegametemplate")
        doCreateLink = True
        doMoveFolder = True

        if FsTools.isHardLink(savegameTemplatesPath):
            log.info(f"Templates folder in savegame at {savegameTemplatesPath} is already a hardlink.")
            doCreateLink = False
    
        if mirrorTemplatesPath.exists():
            log.info(f"There is already a template mirror at {mirrorTemplatesPath}.")
            doMoveFolder = False
            
        if doMoveFolder:
            log.info(f"Externalizing Templates folder to hdd")
            # move template folder to hdd template mirror
            with Timer() as timer:
                self.fileSystem.moveFileTree(
                    sourceDotPath="saves.games.savegame.templates", 
                    destinationDotPath="saves.gamesmirror.savegametemplate", 
                    info=f"Moving Templates from ram to hdd. If your savegame is big already, this can take a while"
                    )
            log.info(f"Moved templates from {savegameTemplatesPath} to {mirrorTemplatesPath} in {timer.elapsedTime}")
        
        if doCreateLink:
            # create link from savegame back to hdd template mirror
            self.fileSystem.createHardLink(linkPath=savegameTemplatesPath, linkTargetPath=mirrorTemplatesPath)

    def mountRamdrive(self, driveLetter, driveSize):
        """
        mounts a ramdrive as driveLetter with driveSize with osfmount, will call a subprocess for this
        requires osfmount to be available at the path and admin privileges
        """
        osfMount = self.checkAndGetOsfMountPath()
        cmd = [osfMount]
        #-a -t vm -m T -o format:ntfs:'Ramdisk',logical -s 2G
        args = f"-a -t vm -m {driveLetter} -o format:ntfs:'Ramdisk',logical -s {driveSize}"
        cmd.extend(args.split(" "))
        log.info(f"Executing {cmd}. This will require admin privileges")
        process = subprocess.run(cmd, capture_output=True, shell=True)
        if process.check_returncode():
            log.info(f"Successfully mounted ramdisk as {driveLetter} with size {driveSize}")

    def checkRamdrive(self, ramdiskDriveLetter=None, simpleCheck=False):
        """
        returns True if there is a drive mounted as 'driveLetter' and it is a osfmount ramdrive, by calling osfmount (requires admin privileges)
        if simpleCheck==True, will only check if the driveletter exists.
        """
        driveLetter = ramdiskDriveLetter
        if ramdiskDriveLetter == None:
            driveLetter = self.config.ramdisk.drive

        if simpleCheck: 
            # just check if the drive is there, no way to check if its proper osf mounted ramdrive?
            return Path(driveLetter).exists()

        osfMount = self.checkAndGetOsfMountPath()
        cmd = [osfMount, "-l", "-m", driveLetter]
        log.info(f"Executing {cmd}. This will require admin privileges")
        try:
            subprocess.run(cmd, capture_output=True, shell=True, check=True)
            log.debug(f"There is an osf mounted ramdrive as {driveLetter}")
            return True
        except subprocess.CalledProcessError as ex:
            log.debug(f"No osf mounted ramdrive found as '{driveLetter}'. Ex: {ex}")
            return False
        
    def checkAndGetOsfMountPath(self):
        """
        returns the path to osfmount, making sure the target file exists. raises a exception if it doesn't, since we won't be able to continue without it.
        """
        osfMount = self.config.paths.osfmount
        if Path(osfMount).exists(): 
            return osfMount
        raise RequirementsNotFulfilledError(f"osfmount not found in the configured path at {osfMount}. Please make sure it is installed and the configuration points to it.")

    def syncMirrorToRam(self):
        """
        syncs the mirror to ram once
        """
        # the target should be the hardlink to ramdisk at this point, so we'll use the link as target
        self.fileSystem.copyFileTree("saves.gamesmirror.savegamemirror", "saves.games.savegame")

    def syncRamToMirror(self):
        """
        syncs the ram to mirror once
        """
        # the source should be the hardlink to ramdisk at this point, so we'll use the link as target
        self.fileSystem.copyFileTree("saves.games.savegame", "saves.gamesmirror.savegamemirror")

    def uninstall(self, force=False):
        """
        reverts the changes made by the prepare, basically moving the savegame back to its original place, removing the mirror

        if mirror and nosave: deletelink, moveback, 
        if mirror and save: delete mirror?
        if nomirror and nosave: nothing to do
        if nomirror and save: nothing to do
        """
        if not force and self.config.general.useRamdisk:
            log.error("Ramdisk usage is enabled in the configuration, can not uninstall the ramdisk usage when it is enabled.")
            raise AdminRequiredException("Ramdisk usage is enabled in the configuration, can not uninstall when it is enabled.")

        mirrorExists, mirrorFolderPath = self.existsMirror()
        savegameExists, savegameFolderPath = self.existsSavegame()

        if mirrorExists:
            log.info(f"Mirror at {mirrorFolderPath} exists")
        else:
            log.warn(f"Mirror at {mirrorFolderPath} does not exist")
            raise NoSaveGameMirrorFoundException(f"Mirror at {mirrorFolderPath} does not exist")

        if savegameExists:
            log.error(f"Savegame exists at '{savegameFolderPath}'")
            raise SaveGameFoundException(f"savegame found at {savegameFolderPath}")
        else:
            log.info(f"No Savegame at {savegameFolderPath} found")

        # check and unmount ramdrive, if its there
        ramdiskDriveLetter = self.config.ramdisk.drive
        if Path(ramdiskDriveLetter).exists():
            log.info(f"Unmounting ramdisk at {ramdiskDriveLetter}.")
            try:
                self.unmountRamdisk(driveLetter=ramdiskDriveLetter)
            except Exception as ex:
                raise AdminRequiredException(f"could not unmount ramdisk {ex}")

        isLink = FsTools.isHardLink(savegameFolderPath)
        if isLink:
            FsTools.deleteLink(savegameFolderPath)

        # move the mirror to the savegame folder
        self.fileSystem.moveFileTree("saves.gamesmirror.savegamemirror", "saves.games.savegame", 
                            f"Moving savegamemirror to old location, this may take some time if your savegame is large!")
        
        # remove the template mirror if there is one
        templateMirrorPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegametemplate")
        if templateMirrorPath.exists():
            self.fileSystem.markForDelete(templateMirrorPath)
            self.fileSystem.commitDelete()
    
    def startSynchronizer(self, syncInterval):
        """
        starts a separate thread for the synchronizer, that will call syncram2mirror every $syncInterval
        """
        if not self.config.general.useRamdisk:
            log.warning("useRamdisk is set to False, there is no much sense in using the synchronizer. Please check that the code is being used properly.")
        if syncInterval==0:
            log.debug(f"synchronizer is disabled, syncInterval was {syncInterval}")
            return False
        self.synchronizerShutdownEvent = Event()
        self.synchronizerThread = Thread(target=self.syncTask, args=(self.synchronizerShutdownEvent, syncInterval), daemon=True)
        self.synchronizerThread.start()
        log.debug(f"ram to mirror synchronizer started with an interval of {syncInterval}")
    
    def syncTask(self, event: Event, syncInterval):
        timePassed = 0
        while True:
            time.sleep(1)
            timePassed = timePassed + 1
            if timePassed % syncInterval == 0:
                announceSync = self.communication.shallAnnounceSync()
                if announceSync:
                    self.communication.announceSyncStart()
                log.info(f"Synchronizing from ram to mirror")
                with Timer() as timer:
                    self.syncRamToMirror()
                log.info(f"Sync done, will wait for {syncInterval} seconds. Time needed {timer.elapsedTime}")
                if announceSync:
                    self.communication.announceSyncEnd()
            if event.is_set():
                break
        log.debug("synchronizer shut down")

    def stopSynchronizer(self):
        if not self.synchronizerShutdownEvent:
            log.warning("Can not stop synchronizer thread since there is probably no synchronizer thread running.")
            return
        
        # set the shared boolean, which will make the synchronizer stop
        self.synchronizerShutdownEvent.set()
        # wait for the thread to join the main thread
        log.debug("waiting for synchronizer thread to finish")
        self.synchronizerThread.join()
        log.debug(f"ram to mirror synchronizer stopped")

    def unmountRamdisk(self, driveLetter):
        """
        dismount ramdisk, deleting all its content in the process.
        """
        osfMount = self.checkAndGetOsfMountPath()
        cmd = [osfMount, "-d", "-m", driveLetter]
        log.info(f"Executing {cmd}. This could require admin privileges")
        try:
            process = subprocess.run(cmd, capture_output=True, shell=True, check=True)
            if process.check_returncode():
                log.info(f"Ramdisk {driveLetter} unmounted!")
                return True
        except subprocess.CalledProcessError:
            log.debug(f"No osf mounted ramdrive found as {driveLetter} or some other error happened.")
            raise AdminRequiredException(f"could not unmount ramdrive at {driveLetter}. Please check the logs")

    def existsSavegame(self, checkGlobalDb=True):
        """
        checks that the savegamefolder exists and optionally contains a global.db
        returns true/false and the path of the folder as a tuple
        """
        savegamePath = self.fileSystem.getAbsolutePathTo("saves.games.savegame")
        if checkGlobalDb:
            savegameExists = self.fileSystem.existsDotPath("saves.games.savegame.globaldb")
            return savegameExists, savegamePath
        else:
            return savegamePath.exists(), savegamePath
            
    def existsMirror(self, checkGlobalDb=True):
        """
        checks that the savegamemirror exists and optionally contains a global.db
        returns true/false and the path of the folder as a tuple
        """
        mirrorPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        if checkGlobalDb:
            mirrorExists = self.fileSystem.existsDotPath("saves.gamesmirror.savegamemirror.globaldb")
            return mirrorExists, mirrorPath
        else:
            return mirrorPath.exists(), mirrorPath

    def existsRamdisk(self, raiseException=True):
        """
        make sure the ramdisk exists if ramdisk is enabled. Does only check for drive letter, not driver itself.
        """
        ramdiskEnabled = self.config.general.useRamdisk
        if ramdiskEnabled:
            ramdiskDrive = Path(self.config.ramdisk.drive)
            if ramdiskDrive.exists():
                return True
            else:
                if raiseException:
                    raise AdminRequiredException(f"Ramdisk is enabled but it does not exist as drive {ramdiskDrive}. Make sure to run the ramdisk setup first!")
                else:
                    return False
