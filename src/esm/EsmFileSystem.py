import logging
import os
import dotsi
from functools import cached_property
from pathlib import Path
from esm import UserAbortedException, robocopy
from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import askUser, getElapsedTime, getTimer, isDebugMode

log = logging.getLogger(__name__)

@Service
class EsmFileSystem:

    """
    Represents the filesystem with the relevant bits that we manage

    allows to decorate this with convenient functions and operations, aswell as resolve
    them according to the configuration automatically
    """
    def __init__(self, config=None):
        if config:
            self.config = config
        self.clearPendingDeletePaths()

    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    @cached_property
    def structure(self) -> dotsi.Dict:
        return self.getStructureFromConfig(self.config)

    def getStructureFromConfig(self, config):
        """
        read the config info about folders and filenames, and populate the filestructure
        """
        dotPathStructure = {
            "ramdisk": {
                "_parent": config.ramdisk.drive,
                "savegame": config.server.savegame
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
                "_parent": config.foldernames.saves, 
                "cache": "Cache",
                "games": {
                    "_parent": config.foldernames.games,
                    "savegame": {
                        "_parent": config.server.savegame,
                        "templates": config.foldernames.templates,
                        "playfields": config.foldernames.playfields,
                        "globaldb": config.filenames.globaldb
                    }
                },
                "gamesmirror": {
                    "_parent": config.foldernames.gamesmirror,
                    "savegamemirror": {
                        "_parent": f"{config.server.savegame}{config.foldernames.savegamemirrorpostfix}",
                        "globaldb": config.filenames.globaldb
                    },
                    "savegametemplate": f"{config.server.savegame}{config.foldernames.savegametemplatepostfix}"
                }
            }
        }
        # put all in a dot-navigatable dict
        return dotsi.Dict(dotPathStructure)

    def getAbsolutePathTo(self, dotPath, prefixInstallDir=True):
        """
        returns the relative path to the configured path, as requested by the dotpath
        """
        relativePath = self.getPathTo(dotPath)
        if prefixInstallDir:
            return Path(f"{self.config.paths.install}/{relativePath}").absolute()
        else:
            return Path(relativePath).absolute()

    def getPathTo(self, dotPath, parts=None, index=None, tree=None, segments=None):
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
        options = self.config.robocopy.options.get(operation).split(" ")
        logFile = Path(self.getCaller()).stem + "_robocopy.log"
        if not isDebugMode(self.config):
            process=robocopy.execute(sourcePath, destinationPath, options, logFile, encoding=self.config.robocopy.encoding)
            return process
        else:
            log.debug(f"debugmode: robocopy {sourcePath} {destinationPath} {options}")

    def existsDotPath(self, dotPath, prefixInstallDir=True):
        path = self.getAbsolutePathTo(dotPath=dotPath, prefixInstallDir=prefixInstallDir)
        return Path(path).exists()

    def getCaller(self):
        """
        return the caller from the context or __name__ is not given.
        """
        try:
            return self.config.context.caller
        except KeyError:
            return __name__

    def createHardLink(self, linkPath, linkTargetPath):
        """
        creates a hardlink (jointpoint) from given source to given destination
        """
        log.info(f"Creating link from {linkPath} -> {linkTargetPath}")
        FsTools.createLink(linkPath, linkTargetPath)

    def markForDelete(self, targetPath, native=False):
        """
        mark a file, folder or hardlink and all its content for deletion, use #commitDelete to actually delete the stuff
        """
        if isinstance(targetPath, Path):
            path = targetPath.absolute()
        else:
            path = Path(targetPath).absolute()
          
        if not path.exists():
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

    def commitDelete(self, override=None):
        """
        actually deletes the list of paths that we are saving in the listOfPathstoDelete
        returns bool, elapsedTime - bool containing True if the deletion was comitted and the time taken to delete.
        """
        if len(self.pendingDeletePaths) <= 0:
            log.info("There is nothing to delete")
            return False, None
        
        print(f"List of files marked for deletion:")
        for path, targetPath, native in self.pendingDeletePaths:
            print(f"   {path}")

        if not askUser("Proceed? [yes/no] ", "yes", override=override):
            log.info("Will not delete the listed files.")
            raise UserAbortedException("User aborted file deletion.")
            # return False, None

        start = getTimer()
        for path, targetPath, native in self.pendingDeletePaths:
            if FsTools.isHardLink(path):
                log.debug(f"deleting link at {path}")
                FsTools.deleteLink(path)
            else:
                # for some reason, Path.is_dir() somtimes returns true on files. What a crappy quirk is that!
                # This forces us to check twice with two different implementations...
                if path.is_dir() and os.path.isdir(path):
                    log.debug(f"deleting dir at {targetPath}")
                    if native:
                        FsTools.quickDeleteNative(path)
                    else:
                        FsTools.quickDelete(path)
                else:
                    log.debug(f"deleting file {targetPath}")
                    FsTools.deleteFile(path)
        log.debug(f"done deleting")
        elapsedTime = getElapsedTime(start)
        # empty list of pending deletes
        self.clearPendingDeletePaths()
        return True, elapsedTime
