import logging

from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmBackupManager:

    def __init__(self, config=None):
        if config is None:
            self.config = ServiceRegistry.get(EsmConfigService)
        else:
            self.config = config
        # self.backupAmount = self.config.backups.amount

    def createRollingBackup(self):
        """
        create a rolling mirror backup
        """
        # find out what the target backup folder is
        self.assertFilestructure()
        targetBackupFolder = self.getTargetBackupFolder()

        if self.config.general.useRamdisk:
            log.debug("ramdisk mode is enabled, will use the hdd mirror as backup source")
            self.backupFromHddMirror(targetBackupFolder)
        else:
            # TODO: make sure the server is not running
            self.backupFromSavegame(targetBackupFolder)

        self.backupToolData(targetBackupFolder)
        self.backupGameConfig(targetBackupFolder)
        raise NotImplementedError("not yet implemented")
    
    def assertFilestructure(self):
        """
        makes sure the backup file structure exists, creates the folders if not.
        """
        #TODO gather all dir names to create
        # fs = self.config.context.filesystem
        backupdirAbsolute = self.fs.getAbsolutePath("backups")
        dirs = [
            "backups.backupmirrors"
        ]
        for i in range(self.backupAmount):
            folderName=f"{self.config.foldernames.backupmirrorprefix}{i}"

        #TODO bulk-create all directories needed.


        raise NotImplementedError("not yet implemented")

    def getTargetBackupFolder(self):
        """
        get the path to the backup folder to use
        """
        raise NotImplementedError("not yet implemented")
    
    def backupFromHddMirror(self):
        """
        create a rolling mirror backup using the hdd mirror as source
        """
        # TODO: create file structure if its not there yet
        raise NotImplementedError("not yet implemented")
    
    def backupFromSavegame(self):
        """
        create a rolling mirror backup using the savegame itself as source
        """
    
    def backupGameConfig(self, targetBackupFolder):
        """
        backs up some important game configs, like dedicated.yaml, adminconfig.yaml, etc.
        """
        raise NotImplementedError("not yet implemented")
    
    def backupToolData(self, targetBackupFolder):
        """
        backs up the EAH tool data, so that can be restored too
        """
        raise NotImplementedError("not yet implemented")

    def createStaticBackup(self):
        """
        create a static backup to zip
        """
        raise NotImplementedError("not yet implemented")