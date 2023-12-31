import logging
import subprocess
from datetime import datetime
from functools import cached_property
from pathlib import Path
from esm.ConfigModels import MainConfig
from esm.exceptions import AdminRequiredException, RequirementsNotFulfilledError, ServerNeedsToBeStopped
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmFileSystem import EsmFileSystem
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import getElapsedTime, getTimer

log = logging.getLogger(__name__)

@Service
class EsmBackupService:
    """
    Provides a blazing fast backup system, keeping a configured amount of rolling mirror copies as backups in a separate folder.
    Backups are updated in a rolling fashion using robocopy, the links to the backups are created and updated in the original backup folder.

    Automatically manages creating the file structure needed and updating it as needed. Also supports two modes, for ramdisk mode or without.
    """

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config
    
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

        start = getTimer()
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
            # no globbing will be supported here, since the sources would potentially all end up in one folder, creating a mess in the backup.
            self.backupAdditionalPaths(additionalBackupPaths, targetBackupFolder)

        self.createMarkerFile(targetBackupFolder)
        if previousBackupNumber > 0:
            self.removeMarkerFile(previousBackupFolder)

        deletedLinks = self.removeLinksToTargetBackupFolder(targetBackupFolder)
        if deletedLinks and len(deletedLinks) > 0:
            linkList = ",".join(map(str,deletedLinks))
            log.info(f"Removed now deprecated hardlinks: '{linkList}'")

        linkPath = self.createBackupLink(targetBackupFolder)
        log.info(f"Created link to latest backup as '{linkPath}' -> '{targetBackupFolder}'")
        elapsedTime = getElapsedTime(start)
        log.info(f"Creating rolling backup done, time needed: {elapsedTime}")

    def getPreviousBackupNumber(self):
        """
        find out which was the latest backup by searching for the marker file, return its number or None if not found
        """
        backupParentDir = self.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        markerFileName = self.config.backups.marker
        backupAmount = self.config.backups.amount
        folderPrefix = self.config.foldernames.backupmirrorprefix
        for i in range(1, backupAmount + 1):
            folderName = f"{folderPrefix}{i}"
            markerFile = backupParentDir.joinpath(folderName).joinpath(markerFileName)
            if markerFile.exists():
                log.debug(f"found marker at {markerFile}")
                return i
        log.debug(f"no marker file named {markerFileName} found")
        return None
    
    def getNextBackupNumber(self, previousNumber):
        backupAmount = self.config.backups.amount
        return (previousNumber % backupAmount) + 1
    
    def getRollingBackupFolder(self, backupNumber):
        """
        get the rolling backup folder path for the given number
        """
        backupParentDir = self.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        folderPrefix = self.config.foldernames.backupmirrorprefix
        backupFolderPath = backupParentDir.joinpath(f"{folderPrefix}{backupNumber}")
        return backupFolderPath

    def removeLinksToTargetBackupFolder(self, targetBackupFolder: Path):
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

    def createMarkerFile(self, targetBackupFolder: Path):
        """
        will create the marker file in the target folder
        """
        markerFile = targetBackupFolder.joinpath(self.config.backups.marker)
        FsTools.createFileWithContent(markerFile, "This is just a marker file for ESM so it knows which is the latest backup. Don't delete")

    def removeMarkerFile(self, targetBackupFolder: Path):
        """
        just deletes the marker file from specified folder
        """
        markerFile = targetBackupFolder.joinpath(self.config.backups.marker)
        if markerFile.exists:
            FsTools.deleteFile(markerFile)

    def getSaveGameSource(self):
        """
        returns the path to the savegame to use for backup according to current configuration
        """
        if self.config.general.useRamdisk:
            log.info("Ramdisk mode is enabled, will use the hdd mirror as backup source")
            savegameSource = self.fileSystem.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        else:
            log.info("Ramdisk mode is disabled, will use the savegame as backup source. This requires the server to be stopped!")
            # make sure the server is not running
            if self.dedicatedServer.isRunning():
                log.warn("The server is currently running, creating a backup from the savegame in use may be problematic, please shut down the server first.")
                raise ServerNeedsToBeStopped("Can not create backup from an active savegame while the server is running. Please shut down server first.")
            savegameSource = self.fileSystem.getAbsolutePathTo("saves.games.savegame")
        return savegameSource
    
    def assertBackupFilestructure(self):
        """
        makes sure the backup file structure exists, creates all required folders if not
        """
        backupParentDir = self.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        FsTools.createDir(backupParentDir)
        for i in range(1, self.config.backups.amount + 1):
            folderName=f"{self.config.foldernames.backupmirrorprefix}{i}"
            FsTools.createDir(backupParentDir.joinpath(folderName))

    def backupSavegame(self, savegameSource: Path, targetBackupFolder: Path):
        """
        actually back up the savegame using the source given
        """
        targetBackupFolderSaves = targetBackupFolder.joinpath(self.config.dedicatedConfig.ServerConfig.SaveDirectory).joinpath(self.config.foldernames.games).joinpath(self.config.dedicatedConfig.GameConfig.GameName)
        self.fileSystem.executeRobocopy(sourcePath=savegameSource, destinationPath=targetBackupFolderSaves)
    
    def backupGameConfig(self, targetBackupFolder: Path):
        """
        backs up some important game configs, like dedicated.yaml, adminconfig.yaml, etc.
        """
        # saves/adminconfig.yaml
        adminConfigFileName = self.config.dedicatedConfig.ServerConfig.AdminConfigFile
        adminConfig = self.fileSystem.getAbsolutePathTo('saves').joinpath(adminConfigFileName)
        targetAdminConfig = targetBackupFolder.joinpath(self.config.dedicatedConfig.ServerConfig.SaveDirectory).joinpath(adminConfigFileName)
        targetAdminConfig.parent.mkdir(exist_ok=True, parents=True)
        if adminConfig.exists():
            FsTools.copyFile(adminConfig, targetAdminConfig)
        else:
            log.warning(f"{adminConfigFileName} at '{adminConfig}' does not exist. You probably should have one or something is misconfigured.")

        # dedicated.yaml
        dedicatedYaml = self.config.paths.install.joinpath(self.config.server.dedicatedYaml)
        targetDedicatedYaml = targetBackupFolder.joinpath(self.config.server.dedicatedYaml)
        if dedicatedYaml.exists():
            FsTools.copyFile(dedicatedYaml, targetDedicatedYaml)
        else:
            log.warning(f"dedicated yaml at '{dedicatedYaml}' does not exist. This shouldn't happen")
    
    def backupToolData(self, targetBackupFolder: Path):
        """
        backs up the EAH tool data, so that can be restored too
        """
        toolDataFolder = self.config.paths.eah.joinpath("Config")
        targetBackupFolderTool = targetBackupFolder.joinpath("Tool")
        self.fileSystem.executeRobocopy(sourcePath=toolDataFolder, destinationPath=targetBackupFolderTool)

    def backupAdditionalPaths(self, additionalBackupPaths, targetBackupFolder: Path):
        """
        saves any configured additional paths to the backup in a "additional" folder.
        """
        targetPath = targetBackupFolder.joinpath("Additional")
        FsTools.createDir(targetPath)
        for additionalBackupPath in additionalBackupPaths:
            sourcePath = Path(additionalBackupPath)
            if sourcePath.is_dir():
                # copy dir as is
                dirName = Path(sourcePath).name
                targetDirPath = targetPath.joinpath(dirName)
                log.debug(f"Copying additional dir from {sourcePath} -> {targetDirPath}")
                self.fileSystem.executeRobocopy(sourcePath=sourcePath, destinationPath=targetDirPath)
            else:
                # copy file
                fileName = Path(sourcePath).name
                targetFilePath = targetPath.joinpath(fileName)
                log.debug(f"Copying additional file from {sourcePath} -> {targetFilePath}")
                if sourcePath.exists():
                    FsTools.copyFile(source=sourcePath, destination=targetFilePath)
                else:
                    log.warn(f"Configured additional backup source at {sourcePath} does not exist.")

    def createBackupLink(self, targetBackupFolder: Path):
        """
        create the symlink in the parent backup folder to the rolling backup, returns its path
        """
        parentDir = self.fileSystem.getAbsolutePathTo("backup")
        linkName = self.getBackupFolderLinkName()
        linkPath = parentDir.joinpath(linkName)
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
        create a static backup to zip, this will use the latest rolling backup mirror as source.
        """
        latestBackupNumber = self.getPreviousBackupNumber()
        if latestBackupNumber is None:
            log.error("Could not find the latest backup, this means the rolling backups do either not exist or are not valid. Please create a rolling backup first!")
            raise AdminRequiredException("Could not create static backup, since there is no valid latest rolling backup to use. Please create a backup first.")
        latestBackupFolder = self.getRollingBackupFolder(latestBackupNumber)

        staticBackupFileName = self.getStaticBackupFileName()
        parentBackupDir = self.fileSystem.getAbsolutePathTo("backup")
        log.info(f"Creating static backup from {latestBackupFolder.as_posix()} as '{parentBackupDir}/{staticBackupFileName}'. Depending on savegame size, this might take a while.")
        self.createZip(latestBackupFolder, parentBackupDir, staticBackupFileName)

    def getStaticBackupFileName(self, date=None):
        """
        returns a filename for the static zip file looking like: 20231002_2359_savegame.zip
        """
        if date:
            date = date
        else:
            date = datetime.now()
        formattedDate = date.strftime("%Y%m%d_%H%M%S")
        return f"{formattedDate}_{self.config.dedicatedConfig.GameConfig.GameName}.zip"

    def createZip(self, source, backupDirectory, zipFileName):
        """
        Create a zipfile of the given source folder, saved under the name given in zipFile.

        This will use the parameters defined in the configuration. Speed is of essence, compression rate is not very important.

        Example: "%zipcmd%" a -tzip -mtp=0 -mm=Deflate64 -mmt=on -mx1 -mfb=32 -mpass=1 -sccUTF-8 -mcu=on -mem=AES256 -bb0 -bse0 -bsp2 -w"workingdir" "zip" "dir"
        """
        self.assertEnoughFreeSpace()

        zipFile = f"{backupDirectory}\\{zipFileName}"
        peaZipExecutable = self.checkAndGetPeaZipPath()
        cmd = [peaZipExecutable]
        cmd.extend(str(self.config.backups.staticBackupPeaZipOptions).split(" "))
        cmd.extend([f"-w{backupDirectory}", zipFile, f"{source}\\*"])
        log.debug(f"executing {cmd}")
        start = getTimer()
        process = subprocess.run(cmd)
        elapsedTime = getElapsedTime(start)
        log.debug(f"process returned: {process} after {elapsedTime}")
        # this returns when peazip finishes
        if process.returncode > 0:
            log.error(f"error executing peazip: stdout: \n{process.stdout}\n, stderr: \n{process.stderr}\n")
        
        fileSize = Path(zipFile).stat().st_size
        log.info(f"Static zip created at '{zipFile}', size: {FsTools.realToHumanFileSize(fileSize)}, time to create: {elapsedTime}")
        return Path(zipFile)

        # we'll use a method that is extremely fast, but has a low compression rate
        # on test: 250MB savegame -> 1 second, 70MB
        # on test: 500MB savegame -> 2 second, 140MB
        # "%zipCmdPath%" a -tzip -mtp=0 -mm=Deflate64 -mmt=on -mx1 -mfb=32 -mpass=1 -sccUTF-8 -mcu=on -mem=AES256 -bb0 -bse0 -bsp2 "-w%backupDirPath%" "%backupDirPath%\%backupZipName%" "!backupDir!" >>%zipLogfile%

        # on test: 250MB savegame -> 1 second, 71MB
        # on test: 500MB savegame -> 2 second, 140MB
        # "%zipCmdPath%" a -tzip -mtp=0 -mm=Deflate -mmt=on -mx1 -mfb=32 -mpass=1 -sccUTF-8 -mcu=on -mem=AES256 -bb0 -bse0 -bsp2 "-w%backupDirPath%" "%backupDirPath%\%backupZipName%" "!backupDir!" >>%zipLogfile%

        # on test: 250MB savegame -> 3 seconds, 9MB - not supported by tcmd :(
        # on test: 500MB savegame -> 7 seconds, 12MB - not supported by tcmd :(
        # "%zipCmdPath%" a -t7z -m0=Zstd -mmt=on -mx1 -ms=8m -mqs=on -sccUTF-8 -bb0 -bse0 -bsp2 "-w%backupDirPath%" "%backupDirPath%\%backupZipName%" "!backupDir!" >>%zipLogfile%

        # on test: 250MB savegame -> 4 seconds, 23MB
        # on test: 250MB savegame -> 5 seconds, 23MB
        # on test: 500MB savegame -> 9 seconds, 41MB
        # "%zipCmdPath%" a -t7z -m0=Deflate64 -mmt=on -mx1 -mfb=32 -mpass=1 -ms=8m -mqs=on -sccUTF-8 -bb0 -bse0 -bsp2 "-w%backupDirPath%" "%backupDirPath%\%backupZipName%" "!backupDir!" >>%zipLogfile%

        # on test: 250MB savegame -> 5 seconds, 34MB
        # on test: 500MB savegame -> 9 seconds, 66MB
        # "%zipCmdPath%" a -t7z -m0=Deflate -mmt=on -mx1 -mfb=32 -mpass=1 -ms=8m -mqs=on -sccUTF-8 -bb0 -bse0 -bsp2 "-w%backupDirPath%" "%backupDirPath%\%backupZipName%" "!backupDir!" >>%zipLogfile%

    def checkAndGetPeaZipPath(self):
        """
        checks that the pea zip executable exists and returns its path.
        """
        peaZip = self.config.paths.peazip
        if Path(peaZip).exists():
            return peaZip
        raise RequirementsNotFulfilledError(f"PeaZip not found in the configured path at {peaZip}. Please make sure it exists and the configuration points to it.")

    def assertEnoughFreeSpace(self):
        """
        make sure there is enough space left on the disk, checking against the configured minimum required space. raises an error if there's not enough
        """
        drive = self.fileSystem.getAbsolutePathTo("backup").drive
        minimum = self.config.backups.minDiskSpaceForStaticBackup
        hasSpace, freeSpace, freeSpaceHuman = FsTools.hasEnoughFreeDiskSpace(drive, minimum)
        log.debug(f"Free space on drive {drive} is {freeSpaceHuman}. Configured minimum to create a backup is {minimum}")
        if not hasSpace:
            log.error(f"The drive {drive} has not enough free disk space, the minimum required to create a static backup is configured to be {minimum}")
            raise AdminRequiredException("Space on the drive is running out, will not create a static backup")
