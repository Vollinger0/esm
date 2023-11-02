
from datetime import datetime
from functools import cached_property
import logging
from pathlib import Path
import shutil
from esm.Exceptions import AdminRequiredException
from esm.EsmBackupService import EsmBackupService
from esm.EsmConfigService import EsmConfigService
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmDeleteService:

    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)
    
    @cached_property
    def ramdiskManager(self) -> EsmRamdiskManager:
        return ServiceRegistry.get(EsmRamdiskManager)
    
    @cached_property
    def backupService(self) -> EsmBackupService:
        return ServiceRegistry.get(EsmBackupService)

    def deleteAll(self):
        """
        Marks everything that belongs to a savegame for deletion, including:
        - the savegame (or the ramdisk, if enabled)
        - the backups (not the static ones)
        - the mirrors
        - the eah tool data
        - the logs from the game, tool and esm
        - any additional paths that were configured

        After all that, the user will be shown the list of files that are marked and asked a last time before deletion.
        All logfiles will be backed up as a static zip though.
        """
        if self.config.general.useRamdisk:
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
            savegamePath = self.fileSystem.getAbsolutePathTo("saves.games.savegame")
            log.info(f"Marking for deletion: savegame at {savegamePath}")
            self.fileSystem.markForDelete(savegamePath, native=True)

        # delete backups
        backups = self.fileSystem.getAbsolutePathTo("backup")
        backupMirrors = self.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        # delete all hardlinks to the backupmirrors first
        log.debug(F"Marking for deletion: all links to the rolling backups")
        for entry in backups.iterdir():
            if FsTools.isHardLink(entry):
                rollingBackup = FsTools.getLinkTarget(entry)
                if self.config.foldernames.backupmirrorprefix in rollingBackup.name:
                    # the link points to a rolling backup, delete it
                    self.fileSystem.markForDelete(entry)
        log.info(f"Marking for deletion: all rolling backups at {backupMirrors}")
        self.fileSystem.markForDelete(backupMirrors, native=True)

        # delete game mirrors
        gamesmirrors = self.fileSystem.getAbsolutePathTo("saves.gamesmirror")
        log.info(f"Marking for deletion: all hdd mirrors at {gamesmirrors}")
        self.fileSystem.markForDelete(gamesmirrors, native=True)

        # delete the cache
        cache = self.fileSystem.getAbsolutePathTo("saves.cache")
        cacheSavegame = f"{cache}/{self.config.server.savegame}"
        log.info(f"Marking for deletion: the cache at {cacheSavegame}")
        self.fileSystem.markForDelete(cacheSavegame)
        
        #delete eah tool data
        eahToolDataPattern = Path(f"{self.config.paths.eah}/Config/").absolute().joinpath("*.dat")
        deglobbedPaths = FsTools.resolveGlobs([eahToolDataPattern])
        for entry in deglobbedPaths:
            log.info(f"Marking for deletion: eah tool data at {entry}")
            self.fileSystem.markForDelete(entry)

        # delete additionally configured stuff
        additionalDeletes = self.config.deletes.additionalDeletes
        if additionalDeletes and len(additionalDeletes)>0:
            absolutePaths = FsTools.toAbsolutePaths(additionalDeletes, parent=self.config.paths.install)
            deglobbedPaths = FsTools.resolveGlobs(absolutePaths)
            for path in deglobbedPaths:
                log.info(f"Marking for deletion: configured additional path at {path}")
                self.fileSystem.markForDelete(path)
        
        # backupAllLogs
        self.backupAllLogs()

        log.info(f"Will start deletion tasks now. Depending on savegame size and amount of backup mirrors, this might take a while!")
        comitted, elapsedTime = self.fileSystem.commitDelete()
        if comitted:
            log.info(f"Deleting all took {elapsedTime}. You can now start a fresh game.")
        else:
            self.fileSystem.clearPendingDeletePaths()
            log.warning("Deletion cancelled")

    def backupAllLogs(self):
        backupDir = self.fileSystem.getAbsolutePathTo("backup")
        logBackupFolder = Path(f"{backupDir}/alllogs")
        logBackupFolder.mkdir(exist_ok=True)
        if self.config.deletes.backupGameLogs:
            source = f"{self.config.paths.install}/Logs/*"
            self.backupLogs(source, logBackupFolder, "GameLogs")
        if self.config.deletes.backupEahLogs:
            source = f"{self.config.paths.eah}/logs/*"
            self.backupLogs(source, logBackupFolder, "EAHLogs")
        if self.config.deletes.backupEsmLogs:            
            source = f"{self.config.paths.install}/*.log"
            self.backupLogs(source, logBackupFolder, "ESMLogs")
            source = f"{self.config.paths.install}/esm/*.log"
            self.backupLogs(source, logBackupFolder, "ESMLogs")

        # zip the target folder and remove it afterwards
        zipFileName = self.getLogsBackupFileName()
        self.backupService.createZip(source=logBackupFolder, backupDirectory=backupDir, zipFileName=zipFileName)
        # we can delete this folder directly at this point, since we backed them up and to not confuse the user later
        FsTools.deleteDir(logBackupFolder, recursive=True)
        log.info(f"All logs backed up and zipped as {zipFileName}")

    def backupLogs(self, sourcePath, backupFolderPath, folderName):
        """
        move the content of given source path to the backup folder path, putting the contents into the folder called foldername at the target
        """
        sourcePaths = []
        # if source is glob, get list of sources.
        if FsTools.isGlobPattern(sourcePath):
            sourcePaths.extend(FsTools.resolveGlobs(paths=[sourcePath]))
        else:
            sourcePaths.append(sourcePath)

        for source in sourcePaths:
            # move source into backupfolder as requested.
            target = backupFolderPath.joinpath(folderName);
            FsTools.createDir(target)
            # if we're trying to move our own logfile, just create a copy instead.
            if Path(self.config.context.logFile).samefile(source):
                shutil.copy(src=source, dst=target)
            else:
                shutil.move(src=source, dst=target)
        
    def getLogsBackupFileName(self, date=None):
        """
        returns a filename for the static zip file looking like: 20231002_2359_savegame_logs.zip
        """
        if date:
            date = date
        else:
            date = datetime.now()
        formattedDate = date.strftime("%Y%m%d_%H%M%S")
        return f"{formattedDate}_{self.config.server.savegame}_logs.zip"
