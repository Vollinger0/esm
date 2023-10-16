from functools import cached_property
import logging
import subprocess
import time
from pathlib import Path
from threading import Event, Thread
from esm import AdminRequiredException, NoSaveGameFoundException, NoSaveGameMirrorFoundException, RequirementsNotFulfilledError, SaveGameMirrorExistsException
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmFileSystem import EsmFileSystem
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import Timer, getElapsedTime, getTimer

log = logging.getLogger(__name__)

@Service
class EsmRamdiskManager:
    """
    class that manages anything related to the ramdisk, that includes install, setup, deinstall, syncs and so on.
    
    """
    def __init__(self, config=None, dedicatedServer=None, fileSystem=None):
        if config:
            self.config = config
        if dedicatedServer:
            self.dedicatedServer = dedicatedServer
        if fileSystem:
            self.fileSystem = fileSystem

        self.synchronizerShutdownEvent = None
        self.synchronizerThread = None

    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)

    @cached_property        
    def dedicatedServer(self) -> EsmDedicatedServer:
        return ServiceRegistry.get(EsmDedicatedServer)

    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)

    def prepare(self):
        """
        actually takes a non-ramdisk filestructure and converts it into a ramdisk filestructure

        Moves a savegame to the hdd savegame mirror location
        """
        savegameFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame")
        savegameExists = False
        savegameMirrorExists = False

        # check that there is a savegame
        if not Path(savegameFolderPath).exists():
            log.info(f"Savegame does not exist at '{savegameFolderPath}'. Either the configuration is wrong or you may want to create one.")
        else:
            savegameExists = True
            log.info(f"Savegame exists at '{savegameFolderPath}'")

        savegameMirrorFolderPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        # check that there is no savegame mirror
        if Path(savegameMirrorFolderPath).exists():
            savegameMirrorExists = True
            log.info(f"Savegame mirror does exist already at '{savegameMirrorFolderPath}'. Either the configuration is wrong or this has been installed already, or the folder needs to be deleted.")
        else:
            log.debug(f"{savegameMirrorFolderPath} does not exist yet")

        if not savegameExists:
            raise NoSaveGameFoundException(f"no savegame found at {savegameFolderPath}")
        
        if savegameMirrorExists:
            raise SaveGameMirrorExistsException(f"savegame mirror at '{savegameMirrorFolderPath}' already exists.")

        # move the savegame to the hddmirror folder
        self.fileSystem.moveFileTree("saves.games.savegame", "saves.gamesmirror.savegamemirror", 
                            f"Moving savegame to new location, this may take some time if your savegame is large already!")
        
        log.info("Install complete, you may now start the ramdisk setup")
        
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
            log.debug(f"{ramdiskDrive} does not exist")
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
            log.info("externalizing templates is disabled. If you have a huge savegame, consider enabling this to reduce ramdisk usage.")

        # sync the mirror to the ramdisk
        savegamemirror = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        if not savegamemirror.exists():
            raise NoSaveGameMirrorFoundException("f{savegamemirror} does not exist! Is the configuration correct? Did you call the install action before calling the setup?")
        log.info("Syncing mirror 2 ram")
        self.syncMirrorToRam()
        log.info("Setup completed, you may now start the server")

    def externalizeTemplates(self):
        """
        will move the savegame template folder from the ram back to the hdd, in a separate mirror folder and create a hardlink
        """
        log.info(f"Externalizing Templates folder to hdd")
        savegametemplatesPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.templates")
        templateshddcopyPath = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegametemplate")
        doCreateLink = True
        doMoveFolder = True

        if FsTools.isHardLink(savegametemplatesPath):
            log.info(f"Templates folder in savegame at {savegametemplatesPath} is already a hardlink.")
            doCreateLink = False
    
        if templateshddcopyPath.exists():
            log.info(f"There is already a template hdd copy at {templateshddcopyPath}.")
            doMoveFolder = False
            
        if doMoveFolder:
            # move template folder to hdd template mirror
            with Timer() as timer:
                self.fileSystem.moveFileTree(
                    sourceDotPath="saves.games.savegame.templates", 
                    destinationDotPath="saves.gamesmirror.savegametemplate", 
                    info=f"Moving Templates back to HDD. If your savegame is big already, this can take a while"
                    )
            log.info(f"Moved templates from {savegametemplatesPath} to {templateshddcopyPath} in {timer.elapsedTime}")
        
        if doCreateLink:
            # create link from savegame back to hdd template mirror
            self.fileSystem.createHardLink(linkPath=savegametemplatesPath, linkTargetPath=templateshddcopyPath)

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

    def checkRamdrive(self, driveLetter):
        """
        returns True if there is a drive mounted as 'driveLetter' and it is a osfmount ramdrive.
        """
        osfMount = self.checkAndGetOsfMountPath()
        cmd = [osfMount, "-l", "-m", driveLetter]
        log.info(f"Executing {cmd}. This will require admin privileges")
        try:
            subprocess.run(cmd, capture_output=True, shell=True, check=True)
            log.debug(f"There is an osf mounted ramdrive as {driveLetter}")
            return True
        except subprocess.CalledProcessError:
            log.debug(f"No osf mounted ramdrive found as {driveLetter}")
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

    def uninstall(self):
        """
        reverts the changes made by the install, basically moving the savegame back to its original place, removing the mirror
        """
        raise NotImplementedError("not implemented yet")
    
    def startSynchronizer(self, syncInterval):
        """
        starts a separate thread for the synchronizer, that will call syncram2mirror every $syncInterval
        """
        if not self.config.general.useRamdisk:
            log.warn("useRamdisk is set to False, there is no much sense in using the synchronizer. Please check that the code is being used properly.")
        if syncInterval==0:
            log.debug(f"synchronizer is disabled, syncInterval was {syncInterval}")
            return False
        self.synchronizerShutdownEvent = Event()
        self.synchronizerThread = Thread(target=self.syncTask, args=(self.synchronizerShutdownEvent, syncInterval), daemon=True)
        self.synchronizerThread.start()
        log.info(f"ram to mirror synchronizer started with an interval of {syncInterval}")
    
    def syncTask(self, event, syncInterval):
        timePassed = 0
        while True:
            time.sleep(1)
            timePassed = timePassed + 1
            if timePassed % syncInterval == 0:
                log.info(f"Synchronizing from ram to mirror")
                with Timer() as timer:
                    self.syncRamToMirror()
                log.info(f"Sync done. Time needed {timer.elapsedTime}")
            if event.is_set():
                break
        log.debug("synchronizer shut down")

    def stopSynchronizer(self):
        # set the shared boolean, which will make the synchronizer
        self.synchronizerShutdownEvent.set()
        # wait for the thread to join the main thread
        log.debug("waiting for synchronizer thread to finish")
        self.synchronizerThread.join()
        log.info(f"ram to mirror synchronizer stopped")

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

