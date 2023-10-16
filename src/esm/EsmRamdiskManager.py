import logging
from pathlib import Path
import subprocess
from esm import NoSaveGameFoundException, SaveGameMirrorExistsException
from esm.EsmFileStructure import EsmFileStructure
from esm.Jointpoint import Jointpoint

log = logging.getLogger(__name__)

class EsmRamdiskManager:
    """
    class that manages anything related to the ramdisk, that includes install, setup, deinstall, syncs and so on.
    
    """
    def __init__(self, config, dedicatedServer) -> None:
        self.config = config
        self.dedicatedServer = dedicatedServer
        self.fs = EsmFileStructure(config)

    def install(self):
        """
        actually takes a non-ramdisk filestructure and converts it into a ramdisk filestructure

        Moves a savegame to the hdd savegame mirror location
        """
        savegameFolderPath = self.fs.getAbsolutePathTo("saves.games.savegame")
        # check that there is a savegame
        if not Path(savegameFolderPath).exists():
            log.info(f"Savegame does not exist at '{savegameFolderPath}'. Either the configuration is wrong or you may want to create one.")
            raise NoSaveGameFoundException("no savegame found nor created")
        log.info(f"savegame exists at '{savegameFolderPath}'")

        savegameMirrorFolderPath = self.fs.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        # check that there is no savegame mirror
        if Path(savegameMirrorFolderPath).exists():
            log.info(f"Savegame mirror does exist already at '{savegameMirrorFolderPath}'. Either the configuration is wrong or this has been installed already, or the folder needs to be deleted.")
            raise SaveGameMirrorExistsException(f"savegame mirror at '{savegameMirrorFolderPath}' already exists.")
        log.debug(f"{savegameMirrorFolderPath} does not exist yet")

        # move the savegame to the hddmirror folder
        self.fs.moveFileTree("saves.games.savegame", "saves.gamesmirror.savegamemirror", 
                            f"Moving savegame to new location, this may take some time if your savegame is large already!")
        
        log.info("install compelte, you may now start the ramdisk setup")
        
    def setup(self):
        """
        sets up the ramdisk itself, and copies over the data from the hdd mirror
        optionally also sets up the externalized template stuff, if its enabled
        """
        # check and mount the ramdisk
        log.debug("check and mount ramdisk")
        ramdiskDrive = Path(self.config.ramdisk.drive + ":")
        ramdiskSize = Path(self.config.ramdisk.size)
        if ramdiskDrive.exists(): 
            log.debug(f"{ramdiskDrive} already exists as a drive")
            if self.checkRamdrive(ramdiskDrive):
                log.debug(f"there is an osfmounted ramdrive, assuming this is our ramdrive.")
        else:
            log.debug(f"{ramdiskDrive} does not exist")
            self.mountRamdrive(ramdiskDrive, ramdiskSize)

        # create the link savegame -> ramdisk
        log.debug("create link savegame -> ramdisk")
        link = self.fs.getAbsolutePathTo("saves.games.savegame")
        linkTarget = self.fs.getAbsolutePathTo("ramdisk.savegame", prefixInstallDir=False)
        if not linkTarget.exists():
            linkTarget.mkdir()
        if Jointpoint.isHardLink(link):
            log.debug(f"{link} exists and is already a hardlink")
        else:
            self.fs.createJointpoint(link, linkTarget)
            log.debug(f"{link} link created")

        log.debug("check for externalizing templates")
        # set up the link from ramdisk/templates -> hddmirror_templates
        if self.config.general.externalizeTemplates==True:
            self.externalizeTemplates()

        # sync the mirror to the ramdisk
        self.syncMirrorToRam()
        log.info("Setup completed, you may now start the server")

    def externalizeTemplates(self):
        """
        will move the savegame template folder from the ram back to the hdd, in a separate mirror folder and create a hardlink
        """
        log.info(f"externalizing Templates folder")
        # TODO: move template folder to hdd template mirror
        # TODO: create link from ram to hdd template mirror

    def mountRamdrive(self, driveLetter, driveSize):
        """
        mounts a ramdrive as driveLetter with driveSize with osfmount, will call a subprocess for this
        requires osfmount to be available at the path and admin privileges
        """
        osfMount = self.config.paths.osfmount
        # osfMount = checkAndGetOsfMountPath()
        cmd = [osfMount]
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
        osfMount = self.config.paths.osfmount
        cmd = [osfMount, "-l", "-m", str(driveLetter)]
        log.info(f"Executing {cmd}. This will require admin privileges")
        process = subprocess.run(cmd, capture_output=True, shell=True)
        try:
            process.check_returncode()
            log.debug(f"There is an osf mounted ramdrive as {driveLetter}")
            return True
        except subprocess.CalledProcessError:
            log.debug(f"No osf mounted ramdrive found as {driveLetter}")
            return False

    def syncMirrorToRam(self):
        """
        syncs the mirror to ram once
        """
        # the target should be the hardlink to ramdisk at this point, so we'll use the link as target
        self.fs.copyFileTree("saves.gamesmirror.savegamemirror", "saves.games.savegame",
                             f"Mirror copying savegame from hdd mirror to ramdisk")

    def syncRamToMirror(self):
        """
        syncs the ram to mirror once
        """
        # the source should be the hardlink to ramdisk at this point, so we'll use the link as target
        self.fs.copyFileTree("saves.games.savegame", "saves.gamesmirror.savegamemirror",
                             f"Mirror copying savegame from ramdisk to hdd mirror")

    def uninstall(self):
        """
        reverts the changes made by the install, basically moving the savegame back to its original place
        """
        raise NotImplementedError("not implemented yet")
       

