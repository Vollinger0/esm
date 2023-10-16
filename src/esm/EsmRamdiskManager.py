import logging
from pathlib import Path
from esm import NoSaveGameFoundException, SaveGameMirrorExistsException
from esm.EsmFileStructure import EsmFileStructure

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

        Moves a savegame to the hdd savegame mirror location, helps you create the savegame if there is none.
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
        
    def setup(self):
        """
        sets up the ramdisk itself, and copies over the data from the hdd mirror
        optionally also sets up the externalized template stuff, if its enabled
        """
        raise NotImplementedError("not implemented yet")
    
        # TODO: check and mount the ramdisk

        # create the link savegame -> ramdisk
        link = self.fs.getAbsolutePathTo("saves.games.savegame")
        linkTarget = self.fs.getAbsolutePathTo("ramdisk.savegame", prefixInstallDir=False)
        self.fs.createJointpoint(link, linkTarget)

        # TODO: set up the link from ramdisk/templates -> hddmirror_templates
        # TODO: sync the mirror to the ramdisk

    def syncMirrorToRam(self):
        """
        syncs the mirror to ram once
        """
        self.fs.copyFileTree("saves.gamesmirror.savegamemirror", "saves.games.savegame",
                             f"Mirror copying savegame from hdd mirror to ramdisk")

    def syncRamToMirror(self):
        """
        syncs the ram to mirror once
        """
        self.fs.copyFileTree("saves.games.savegame", "saves.gamesmirror.savegamemirror",
                             f"Mirror copying savegame from ramdisk to hdd mirror")

    def uninstall(self):
        """
        reverts the changes made by the install, basically moving the savegame back to its original place
        """
        raise NotImplementedError("not implemented yet")
       

