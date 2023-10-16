import logging
from pathlib import Path
import shutil
import dotsi

from esm import isDebugMode, robocopy
from esm.Jointpoint import Jointpoint

log = logging.getLogger(__name__)

class EsmFileStructure:
    """
    Represents the filesystem with the relevant bits that we manage

    allows to decorate this with convenient functions and operations, aswell as resolve
    them according to the configuration automatically
    """
    def __init__(self, config):
        self.config = config
        self.readFromConfig(config)

    def readFromConfig(self, conf):
        """
        read the config info about folders and filenames, and populate the filestructure
        """
        structure = {
            "ramdisk": {
                "_parent": f"{conf.ramdisk.drive}:",
                "savegame": conf.server.savegame
            },
            "backup": {
                "_parent": conf.foldernames.backup,
                "backupmirrors": conf.foldernames.backupmirrors,
                "backupmirrorprefix": conf.foldernames.backupmirrorprefix
            },
            "dedicatedserver": {
                "_parent": conf.foldernames.dedicatedserver
            },
            "logs" : {
                "_parent": conf.foldernames.logs

            },
            "saves": {
                "_parent": conf.foldernames.saves, 
                "cache": "Cache",
                "games": {
                    "_parent": conf.foldernames.games,
                    "savegame": {
                        "_parent": conf.server.savegame,
                        "templates": conf.foldernames.templates
                    }
                },
                "gamesmirror": {
                    "_parent": conf.foldernames.gamesmirror,
                    "savegamemirror": f"{conf.server.savegame}{conf.foldernames.savegamemirrorpostfix}",
                    "savegametemplate": f"{conf.server.savegame}{conf.foldernames.savegametemplatepostfix}"
                }
            }
        }
        # put all in a dot-navigatable dict
        self.structure = dotsi.Dict(structure)

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
            index=0
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
    
    def moveFileTree(self, source, destination, info=None):
        """
        moves a complete filetree from source to destination using robocopy
        """
        self.executeRobocopy(source, destination, info, "move")

    def copyFileTree(self, source, destination, info=None):
        """
        copies a complete filetree from source to destination using robocopy
        """
        self.executeRobocopy(source, destination, info, "copy")

    def executeRobocopy(self, source, destination, info=None, operation="copy"):
        """
        executes a robocopy command for the given operation
        """
        sourcePath = self.getAbsolutePathTo(source)
        destinationPath = self.getAbsolutePathTo(destination)
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

    def getCaller(self):
        """
        return the caller from the context or __name__ is not given.
        """
        try:
            return self.config.context.caller
        except KeyError:
            return __name__

    def createJointpoint(self, link, linkTarget):
        """
        creates a jointpoint from given source to given destination
        """
        log.info(f"Creating link from {link} -> {linkTarget}")
        Jointpoint.create(link, linkTarget)

    def quickDelete(self, target):
        """
        quickly delete a folder and all its content
        """
        log.debug(f"deleting {target} with shutil.rmtree")
        shutil.rmtree(ignore_errors=True, path=target)
        log.debug(f"done deleting")
