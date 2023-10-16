import logging
from pathlib import Path
import shutil
import dotsi

from esm import isDebugMode, robocopy
from esm.Jointpoint import Jointpoint

log = logging.getLogger(__name__)

class EsmFileStructure:
    """
    represents the filesystem with the relevant bits that we manage

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
                    "savegame": conf.server.savegame
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
    
    def moveFileTree(self, source, destination, info, operation="move"):
        """
        moves a complete filetree from source to destination using robocopy
        """
        self.executeRobocopy(source, destination, info, "move")

    def copyFileTree(self, source, destination, info):
        """
        copies a complete filetree from source to destination using robocopy
        """
        self.executeRobocopy(source, destination, info, "copy")

    def executeRobocopy(self, source, destination, info, operation="copy"):
        """
        executes a robocopy command for the given operation
        """
        sourcePath = self.getAbsolutePathTo(source)
        destinationPath = self.getAbsolutePathTo(destination)
        log.info(info)
        log.info(f"will {operation} from '{sourcePath}' -> '{destinationPath}'")
        options = self.config.robocopy.options.get(operation).split(" ")
        logFile = Path(self.config.context.caller).stem + "_robocopy.log"
        if not isDebugMode(self.config):
            process=robocopy.execute(sourcePath, destinationPath, options, logFile, encoding=self.config.robocopy.encoding)
            return process
        else:
            log.debug(f"debugmode: robocopy {sourcePath} {destinationPath} {options}")

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
