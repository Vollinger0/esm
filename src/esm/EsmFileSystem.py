import logging
import os
from functools import cached_property
from pathlib import Path
from esm import robocopy
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import askUser, getElapsedTime, getTimer
from esm.Exceptions import AdminRequiredException, UserAbortedException

log = logging.getLogger(__name__)

@Service
class EsmFileSystem:

    pendingDeletePaths = []

    """
    Represents the filesystem with the relevant bits that we manage

    allows to decorate this with convenient functions and operations, aswell as resolve
    them according to the configuration automatically
    """
    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config
    
    @cached_property
    def structure(self) -> dict:
        return self.getStructureFromConfig(self.config)

    def getStructureFromConfig(self, config: MainConfig):
        """
        read the config info about folders and filenames, and populate the filestructure
        """
        dotPathStructure = {
            "ramdisk": {
                "_parent": config.ramdisk.drive,
                "savegame": config.dedicatedConfig.GameConfig.GameName
            },
            "backup": {
                "_parent": config.foldernames.backup,
                "backupmirrors": config.foldernames.backupmirrors,
                "backupmirrorprefix": config.foldernames.backupmirrorprefix
            },
            "dedicatedserver": {
                "_parent": config.foldernames.dedicatedserver
            },
            "saves": {
                "_parent": config.dedicatedConfig.ServerConfig.SaveDirectory, 
                "cache": "Cache",
                "games": {
                    "_parent": config.foldernames.games,
                    "savegame": {
                        "_parent": config.dedicatedConfig.GameConfig.GameName,
                        "templates": config.foldernames.templates,
                        "playfields": config.foldernames.playfields,
                        "shared": config.foldernames.shared,
                        "globaldb": config.filenames.globaldb
                    }
                },
                "gamesmirror": {
                    "_parent": config.foldernames.gamesmirror,
                    "savegamemirror": {
                        "_parent": f"{config.dedicatedConfig.GameConfig.GameName}{config.foldernames.savegamemirrorpostfix}",
                        "globaldb": config.filenames.globaldb
                    },
                    "savegametemplate": f"{config.dedicatedConfig.GameConfig.GameName}{config.foldernames.savegametemplatepostfix}"
                }
            }
        }
        return dotPathStructure

    def getAbsolutePathTo(self, dotPath, prefixInstallDir=True):
        """
        returns the relative path to the configured path, as requested by the dotpath
        """
        relativePath = self.getPathTo(dotPath)
        if prefixInstallDir:
            return Path(f"{self.config.paths.install}/{relativePath}").absolute()
        else:
            return Path(relativePath).absolute()

    def getPathTo(self, dotPath: str, parts=None, index=None, tree: dict=None, segments=None):
        """
        recursive function to create a path from the given dotPath and the given filestructure tree
        """
        if tree is None:
            tree = self.structure
        if index is None:
            index = 0
        if segments is None:
            segments = []
        if parts is None:
            parts = dotPath.split(".")
        if len(parts)<=index:
            return
        part = parts[index]
        subtree = tree.get(part)
        if isinstance(subtree, str):
            segments.append(subtree)
            return
        foldername = subtree.get("_parent")
        segments.append(foldername)
        self.getPathTo(dotPath=dotPath, parts=parts, index=index+1, tree=subtree, segments=segments)
        return "/".join(segments)
    
    def moveFileTree(self, sourceDotPath, destinationDotPath, info=None):
        """
        moves a complete filetree from source to destination using robocopy
        """
        self.executeRobocopyDotPaths(sourceDotPath, destinationDotPath, info, "move")

    def copyFileTree(self, sourceDotPath, destinationDotPath, info=None):
        """
        copies a complete filetree from source to destination using robocopy
        """
        self.executeRobocopyDotPaths(sourceDotPath, destinationDotPath, info, "copy")

    def executeRobocopyDotPaths(self, sourceDotPath, destinationDotPath, info=None, operation="copy"):
        """
        executes a robocopy command for the given operation
        """
        sourcePath = self.getAbsolutePathTo(sourceDotPath)
        destinationPath = self.getAbsolutePathTo(destinationDotPath)
        self.executeRobocopy(sourcePath=sourcePath, destinationPath=destinationPath, info=info, operation=operation)

    def executeRobocopy(self, sourcePath, destinationPath, info=None, operation="copy"):
        """
        executes a robocopy command for the given operation
        """
        if info is not None: 
            log.info(info)
        log.debug(f"will {operation} from '{sourcePath}' -> '{destinationPath}'")
        options = getattr(self.config.robocopy.options, f"{operation}options")
        logFile = Path(self.getCaller()).stem + "_robocopy.log"
        if not self.config.general.debugMode:
            process=robocopy.execute(sourcePath, destinationPath, [options], logFile, encoding=self.config.robocopy.encoding)
            return process
        else:
            log.debug(f"debugmode: robocopy {sourcePath} {destinationPath} {options}")

    def existsDotPath(self, dotPath, prefixInstallDir=True):
        path = self.getAbsolutePathTo(dotPath=dotPath, prefixInstallDir=prefixInstallDir)
        return Path(path).exists()

    def getCaller(self) -> str:
        """
        return the caller from the context or __name__ is not given.
        """
        return self.config.context.get('caller', __name__)

    def createHardLink(self, linkPath, linkTargetPath):
        """
        creates a hardlink (jointpoint) from given source to given destination
        """
        log.info(f"Creating link from {linkPath} -> {linkTargetPath}")
        FsTools.createLink(linkPath, linkTargetPath)

    def markForDelete(self, targetPath, native=False):
        """
        mark a file, folder or hardlink and all its content for deletion, use #commitDelete to actually delete the stuff
        if native is True, the path will be deleted with native shell commands on commit.
        """
        if isinstance(targetPath, Path):
            path = targetPath.absolute()
        else:
            path = Path(targetPath).absolute()
          
        if not path.exists(follow_symlinks=False):
            return
        # add path to the list of paths to delete
        self.pendingDeletePaths.append((path, targetPath, native))

    def getPendingDeletePaths(self):
        paths = []
        for path, targetPath, native in self.pendingDeletePaths:
            paths.append(path)
        return paths

    def clearPendingDeletePaths(self):
        self.pendingDeletePaths = []

    def commitDelete(self, override=None, additionalInfo=None):
        """
        actually deletes the list of paths that we are saving in the listOfPathstoDelete
        returns bool, elapsedTime - bool containing True if the deletion was comitted and the time taken to delete.
        """
        if len(self.pendingDeletePaths) <= 0:
            log.info("There is nothing to delete")
            return False, None
        
        print(f"List of paths marked for deletion:")
        for path, targetPath, native in self.pendingDeletePaths:
            print(f"   {path}")

        if additionalInfo:
            log.info(additionalInfo)
            
        if not askUser("Proceed? [yes/no] ", "yes", override=override):
            log.info("Will not delete the listed files.")
            raise UserAbortedException("User aborted file deletion.")

        start = getTimer()
        for path, targetPath, native in self.pendingDeletePaths:
            if FsTools.isHardLink(path):
                log.debug(f"deleting link at '{path}'")
                FsTools.deleteLink(path)
            else:
                # for some reason, Path.is_dir() somtimes returns true on files. What a crappy quirk is that!
                # This forces us to check twice with two different implementations...
                if path.is_dir() and os.path.isdir(path):
                    log.debug(f"deleting dir at '{targetPath}'")
                    if native:
                        FsTools.quickDeleteNative(path)
                    else:
                        FsTools.quickDelete(path)
                else:
                    log.debug(f"deleting file '{targetPath}'")
                    FsTools.deleteFile(path)
        log.debug(f"done deleting")
        elapsedTime = getElapsedTime(start)
        # empty list of pending deletes
        self.clearPendingDeletePaths()
        return True, elapsedTime
    
    def check8Dot3NameGeneration(self):
        """
        will check if 8dot3name (aka shortname) generation on the game's installation drive is enabled

        for this we create a temporary directory in the FS, then one with a very long name and try to access it via its short name

        returns True if generation is disabled (which is good), False if is enabled (which is bad)
        """
        testParentDir = Path(f"{self.config.paths.install}/{self.config.foldernames.esmtests}").resolve()
        driveLetter = testParentDir.drive
        testDir = Path(f"{testParentDir}/thisisalongdirectoryname-check8Dot3NameGeneration")
        testDir.mkdir(parents=True, exist_ok=True)
        checkDir = Path(f"{testParentDir}/THISIS~1")
        result = checkDir.exists()
        if result:
            log.warning(f"8dot3name generation on drive '{driveLetter}' is enabled. This is not bad, but if you disable it, this will make file operations for large amount of files and directories up to ~3 times faster! See https://learn.microsoft.com/de-de/archive/blogs/josebda/windows-server-2012-file-server-tip-disable-8-3-naming-and-strip-those-short-names-too")
        else:
            log.info(f"8dot3name generation is disabled on '{driveLetter}'. This is good.")
        return not result

    def testLinkGeneration(self):
        """
        will check if we are able to create hardlinks, because if not, ramdisk mode will not be possible.
        
        returns true if successful
        """
        testParentDir = Path(f"{self.config.paths.install}/{self.config.foldernames.esmtests}").resolve()

        targetPath = Path(f"{testParentDir}/this-is-the-link-target-directory")
        targetPath.mkdir(parents=True, exist_ok=True)
        linkPath = Path(f"{testParentDir}/this-is-the-link")
        FsTools.deleteLink(linkPath)
        result = FsTools.createLink(linkPath=linkPath, targetPath=targetPath)
        if not result:
            log.warning(f"could not create hardlinks")
            return False
        
        result = FsTools.isHardLink(linkPath)
        if result:
            log.info(f"Creating a hardlink (jointpoint) with mklink successful")
        else:
            log.error(f"Creating a hardlink (jointpoint) with mklink failed. Will not be able to run the game in ramdisk mode.")
        return result
    
    def testRobocopy(self):
        """
        creates some random stuff, copies that and makes sure the process did not fail
        """
        testParentDir = Path(f"{self.config.paths.install}/{self.config.foldernames.esmtests}").resolve()
        sourcePath = testParentDir.joinpath("this-is-the-robocopy-source-directory")
        sourcePath.mkdir(parents=True, exist_ok=True)
        testFile = sourcePath.joinpath("testfileforrobocopytest")
        testFile.write_text("robocopytest")
        destinationPath = testParentDir.joinpath("this-is-the-robocopy-target-directory")
        process = self.executeRobocopy(sourcePath=sourcePath, destinationPath=destinationPath)
        if process.returncode > 3:
            log.error(f"Failed copying with robocopy from '{sourcePath}' to '{destinationPath}'. Please check the robocopy logfile.")
        else:
            log.info("Robocopy copy test successful.")

    def copyAdditionalUpdateStuff(self):
        """
        copies any additionally configured stuff in the config under updates.additional
        """
        additionalStuffList = self.config.updates.additional
        if additionalStuffList is None:
            return
        if len(additionalStuffList) == 0:
            return
        
        copiedFiles = 0
        copiedDirs = 0
        
        for additionalStuff in additionalStuffList:
            sourcePath = Path(additionalStuff.src)
            if not Path(sourcePath).is_absolute():
                sourcePath = Path(f"{self.config.paths.install}/{sourcePath}")
            
            destinationPath = Path(additionalStuff.dst)
            if not Path(destinationPath).is_absolute():
                destinationPath = Path(f"{self.config.paths.install}/{destinationPath}")

            log.info(f"copying '{sourcePath}' to '{destinationPath}'")
            
            sourcePaths = FsTools.resolveGlobs([sourcePath])
            for source in sourcePaths:
                if source.exists():
                    if source.is_dir():
                        # its a dir
                        log.debug(f"copying directory '{source}' into '{destinationPath}'")  
                        FsTools.copyDir(source=source, destination=destinationPath)
                        copiedDirs += 1
                    else:
                        # its a file
                        log.debug(f"copying file '{source}' into '{destinationPath}'")  
                        FsTools.copy(source=source, destination=destinationPath)
                        copiedFiles += 1
                else:
                    log.warning(f"Configured additional path '{source}' does not exist.")
        log.info(f"Copied '{copiedDirs}' folders and '{copiedFiles}' files.")

    def synchronize(self, sourcePath: Path, destinationPath: Path):
        """
        synchronizes sourcePath with destinationPath
        only new files or files whose size or content differ are copied, deleted files in the destination are removed.
        """
        if not sourcePath.is_dir():
            raise AdminRequiredException(f"'{sourcePath}' is not a directory. Please check the configuration.")
        
        if not destinationPath.is_dir():
            raise AdminRequiredException(f"'{destinationPath}' is not a directory. Please check the configuration.")

        # use this strange old library to sync the directories.
        from dirsync import sync
        sync(sourcePath, destinationPath, action='sync', purge=True, create=True, content=True, verbose=True)
