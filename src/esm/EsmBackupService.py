import logging
from datetime import datetime
from functools import cached_property
from pathlib import Path
from esm import ServerNeedsToBeStopped

from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmFileSystem import EsmFileSystem
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmBackupService:
    """
    Provides a blazing fast backup system, keeping a configured amount of rolling mirror copies as backups in a separate folder.
    Backups are updated in a rolling fashion using robocopy, the links to the backups are created and updated in the original backup folder.

    Automatically manages creating the file structure needed and updating it as needed. Also supports two modes, for ramdisk mode or without.
    """

    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)

    @cached_property
    def dedicatedServer(self) -> EsmDedicatedServer:
        return ServiceRegistry.get(EsmDedicatedServer)

    def createRollingBackup(self):
        """
        create a rolling mirror backup
        """
        savegameSourceFolder = self.getSaveGameSource()
        self.assertBackupFilestructure()
        # find out what the target backup folder number is
        previousBackupNumber = self.getPreviousBackupNumber()
        if previousBackupNumber is None:
            previousBackupNumber = 0
        previousBackupFolder = self.getRollingBackupFolder(previousBackupNumber)
        nextBackupNumber = self.getNextBackupNumber(previousBackupNumber)
        targetBackupFolder = self.getRollingBackupFolder(nextBackupNumber)

        log.info(f"Starting backup to {targetBackupFolder}")
        self.backupSavegame(savegameSourceFolder, targetBackupFolder)
        log.debug(f"copying tool data")
        self.backupToolData(targetBackupFolder)
        log.debug(f"copying server config")
        self.backupGameConfig(targetBackupFolder)
    
        # save more stuff, as listed in configuration. Useful to backup custom mod data
        additionalBackupPaths = self.config.backups.additionalBackupPaths
        if additionalBackupPaths and len(additionalBackupPaths) > 0:
            log.debug(f"copying additional data")
            self.backupAdditionalPaths(additionalBackupPaths, targetBackupFolder)

        self.createMarkerFile(targetBackupFolder)
        if previousBackupNumber > 0:
            self.removeMarkerFile(previousBackupFolder)

        deletedLinks = self.removeDeprecatedBackupFolderLink(targetBackupFolder)
        if deletedLinks and len(deletedLinks) > 0:
            linkList = ",".join(map(str,deletedLinks))
            log.info(f"Removed now deprecated hardlinks: {linkList}")

        linkPath = self.createBackupLink(targetBackupFolder)
        log.info(f"Created link to latest backup as '{linkPath}' -> '{targetBackupFolder}'")

    def getPreviousBackupNumber(self):
        """
        find out which was the latest backup by searching for the marker file
        """
        backupParentDir = self.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        markerFileName = self.config.backups.marker
        backupAmount = self.config.backups.amount
        folderPrefix = self.config.foldernames.backupmirrorprefix
        for i in range(1, backupAmount + 1):
            folderName = f"{folderPrefix}{i}"
            markerFile = Path(f"{backupParentDir}/{folderName}/{markerFileName}")
            if markerFile.exists():
                log.debug(f"found marker at {markerFile}")
                return i
    
    def getNextBackupNumber(self, previousNumber):
        backupAmount = self.config.backups.amount
        return (previousNumber % backupAmount) + 1
    
    def getRollingBackupFolder(self, backupNumber):
        """
        get the rolling backup folder path for the given number
        """
        backupParentDir = self.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        folderPrefix = self.config.foldernames.backupmirrorprefix
        backupFolderPath = Path(f"{backupParentDir}/{folderPrefix}{backupNumber}")
        return backupFolderPath

    def removeDeprecatedBackupFolderLink(self, targetBackupFolder):
        """
        Delete any links in the backup folder that might point to our targetBackupFolder
        
        returns the list of deleted links
        """
        backupParentDir = self.fileSystem.getAbsolutePathTo("backup")
        links = FsTools.getLinksToTarget(directory=backupParentDir, targetFolder=targetBackupFolder)
        if links:
            for link in links:
                FsTools.deleteLink(link)
        return links

    def createMarkerFile(self, targetBackupFolder):
        """
        will create the marker file in the target folder
        """
        markerFile = Path(f"{targetBackupFolder}/{self.config.backups.marker}")
        FsTools.createFileWithContent(markerFile, "This is just a marker file for ESM so it knows which is the latest backup. Don't delete")

    def removeMarkerFile(self, targetBackupFolder):
        """
        just deletes the marker file from specified folder
        """
        markerFile = Path(f"{targetBackupFolder}/{self.config.backups.marker}")
        if markerFile.exists:
            FsTools.deleteFile(markerFile)

    def getSaveGameSource(self):
        """
        returns the path to the savegame to use for backup according to current configuration
        """
        if self.config.general.useRamdisk:
            log.info("Ramdisk mode is enabled, will use the hdd mirror as backup source")
            savegameSource = self.getBackupSourceFromHddMirror()
        else:
            log.info("Ramdisk mode is disabled, will use the savegame as backup source. This requires the server to be stopped!")
            # make sure the server is not running
            if self.dedicatedServer.isRunning():
                log.warn("The server is currently running, creating a backup from the savegame in use may be problematic, please shut down the server first.")
                raise ServerNeedsToBeStopped("Can not create backup from an active savegame while the server is running. Please shut down server first.")
            savegameSource = self.getBackupSourceFromSavegame()
        return savegameSource
    
    def assertBackupFilestructure(self):
        """
        makes sure the backup file structure exists, creates all required folders if not
        """
        backupParentDir = self.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        FsTools.createDir(backupParentDir)
        for i in range(1, self.config.backups.amount + 1):
            folderName=f"{self.config.foldernames.backupmirrorprefix}{i}"
            FsTools.createDir(Path(f"{backupParentDir}/{folderName}"))

    def getBackupSourceFromHddMirror(self):
        """
        return the folder path of the source to use for backup from hdd mirror
        """
        return self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
    
    def getBackupSourceFromSavegame(self):
        """
        return the folder path of the source to use for backup from the active savegame
        """
        return self.fileSystem.getAbsolutePathTo("saves.games.savegame")
    
    def backupSavegame(self, savegameSource, targetBackupFolder):
        """
        actually back up the savegame using the source given
        """
        targetBackupFolderSaves = f"{targetBackupFolder}/{self.config.foldernames.saves}/{self.config.server.savegame}"
        self.fileSystem.executeRobocopy(sourcePath=savegameSource, destinationPath=targetBackupFolderSaves)
    
    def backupGameConfig(self, targetBackupFolder):
        """
        backs up some important game configs, like dedicated.yaml, adminconfig.yaml, etc.
        """
        # saves/adminconfig.yaml
        adminConfig = Path(f"{self.fileSystem.getAbsolutePathTo('saves')}/adminconfig.yaml")
        targetAdminConfig = Path(f"{targetBackupFolder}/{self.config.foldernames.saves}/adminconfig.yaml")
        FsTools.copyFile(adminConfig, targetAdminConfig)

        # dedicated.yaml
        dedicatedYaml = Path(f"{self.config.paths.install}/{self.config.server.dedicatedYaml}")
        targetDedicatedYaml = Path(f"{targetBackupFolder}/{self.config.server.dedicatedYaml}")
        FsTools.copyFile(dedicatedYaml, targetDedicatedYaml)
    
    def backupToolData(self, targetBackupFolder):
        """
        backs up the EAH tool data, so that can be restored too
        """
        toolDataFolder = f"{self.config.paths.eah}/Config" 
        targetBackupFolderTool = f"{targetBackupFolder}/Tool"
        self.fileSystem.executeRobocopy(sourcePath=toolDataFolder, destinationPath=targetBackupFolderTool)

    def backupAdditionalPaths(self, additionalBackupPaths, targetBackupFolder):
        """
        saves any configured additional paths to the backup in a "additional" folder.
        """
        targetPath = Path(f"{targetBackupFolder}/Additional/")
        FsTools.createDir(targetPath)
        for additionalBackupPath in additionalBackupPaths:
            sourcePath = Path(additionalBackupPath)
            if sourcePath.is_dir():
                # copy dir as is
                dirName = Path(sourcePath).name
                targetDirPath = f"{targetPath}/{dirName}"
                log.debug(f"Copying additional dir from {sourcePath} -> {targetDirPath}")
                self.fileSystem.executeRobocopy(sourcePath=sourcePath, destinationPath=targetDirPath)
            else:
                # copy file
                fileName = Path(sourcePath).name
                targetFilePath = f"{targetPath}/{fileName}"
                log.debug(f"Copying additional file from {sourcePath} -> {targetFilePath}")
                FsTools.copyFile(source=sourcePath, destination=targetFilePath)
    
    def createBackupLink(self, targetBackupFolder):
        """
        create the symlink in the parent backup folder to the rolling backup, returns its path
        """
        parentDir = self.fileSystem.getAbsolutePathTo("backup")
        linkName = self.getBackupFolderLinkName()
        linkPath = Path(f"{parentDir}/{linkName}")
        FsTools.createLink(linkPath=linkPath, targetPath=targetBackupFolder)
        return linkPath

    def getBackupFolderLinkName(self, date=None):
        """
        creates a folder name like: '20230930 222420 Backup'
        """
        if date:
            date = date
        else:
            date = datetime.now()
        formattedDate = date.strftime("%Y%m%d %H%M%S")
        return f"{formattedDate} Backup"

    def createStaticBackup(self):
        """
        create a static backup to zip
        """
        raise NotImplementedError("not yet implemented")