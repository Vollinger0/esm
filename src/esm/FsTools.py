from glob import glob
import math
import os
import re
import shutil
import subprocess
import logging
from pathlib import Path
from typing import List

import humanize

from esm.Exceptions import SafetyException
from esm.Tools import byteArrayToString

log = logging.getLogger(__name__)

class FsTools:
    """
    Tools to work with the file system, includes handling of hardlink/jointpoint
    """
    MIN_PATH_DEPTH_FOR_DELETE = 3 
    """used to check that a path has at least 3 parts before we delete it, just to make sure no error/misconfiguriation deletes a whole drive."""

    @staticmethod
    def createLink(linkPath, targetPath):
        """
        create a windows hardlink (jointpoint) as link to the linktarget using mklink

        return True if creating the link was successful
        """
        # looks like none of the python-libraries can do this without running into problems
        # calling the shell command works flawlessly...
        log.debug(f"mklink /H /J \"{linkPath}\" \"{targetPath}\"")
        process = subprocess.run(f"mklink /H /J \"{linkPath}\" \"{targetPath}\"", capture_output=True, shell=True)
        if process.returncode > 0:
            stdout = byteArrayToString(process.stdout).strip()
            stderr = byteArrayToString(process.stderr).strip()
            if len(stdout)>0 or len(stderr)>0:
                log.error(f"error executing the mklink command: stdout: '{stdout}', stderr: '{stderr}'")
            else:
                log.error(f"error executing the mklink command, but no output was provided")
            return False
        else:
            return True

    @staticmethod
    def deleteLink(linkPath):
        linkPath = Path(linkPath)
        if linkPath.is_dir():
            linkPath.rmdir()
        else:
            linkPath.unlink(missing_ok=True)

    @staticmethod
    def isHardLink(linkPath):
        try:
            if os.readlink(linkPath):
                return True
            else:
                return False
        except OSError:
            return False
        
    @staticmethod
    def getLinksToTarget(directory: Path, targetFolder: Path):
        """
        return a list of links in the given directory that point to the given target folder, empty list if there are none
        """
        links = []
        for entry in directory.iterdir():
            if FsTools.isHardLink(entry):
                # check if the link points to our target
                linkTarget = FsTools.getLinkTarget(entry)
                target = targetFolder.resolve()
                if linkTarget.exists():
                    if linkTarget.samefile(target):
                        links.append(entry)
        return links

    @staticmethod
    def getLinkTarget(link):
        """
        returns the link target path of a given link
        """
        linkInfo = link.readlink()
        linkTarget = Path(linkInfo.as_posix()[4:]).resolve()
        return linkTarget

    # @staticmethod
    # def isHardLink(link):
    #     # this won't work on windows. looks like there is no other way than to use low-level winapi calls to check that :facepalm:
    #     return Path(link).is_symlink()
        
    @staticmethod
    def quickDelete(targetPath):
        """
        quickly delete a folder and all its content. May be slow. use #quickDeleteNative for the fastest but native method.
        """
        if len(Path(targetPath).resolve().parts) < FsTools.MIN_PATH_DEPTH_FOR_DELETE:
            log.warn(f"prevented delete of path {targetPath} since it has a depth lower than {FsTools.MIN_PATH_DEPTH_FOR_DELETE}")
            raise SafetyException(f"prevented delete of path {targetPath} since it has a depth lower than {FsTools.MIN_PATH_DEPTH_FOR_DELETE}")

        shutil.rmtree(ignore_errors=True, path=targetPath)
    
    @staticmethod
    def quickDeleteNative(targetPath: Path):
        """
        quickly delete a folder and all its content, using the del /f/q/s and rmdir /s/q shell commands 
        """
        if len(Path(targetPath).resolve().parts) < FsTools.MIN_PATH_DEPTH_FOR_DELETE:
            log.warn(f"prevented delete of path {targetPath} since it has a depth lower than {FsTools.MIN_PATH_DEPTH_FOR_DELETE}")
            raise SafetyException(f"prevented delete of path {targetPath} since it has a depth lower than {FsTools.MIN_PATH_DEPTH_FOR_DELETE}")

        cmd = ["del", "/F", "/Q", "/S", targetPath]
        log.debug(f"executing {cmd}")
        process = subprocess.run(cmd, shell=True)
        log.debug(f"process returned: {process}")
        cmd = ["rmdir", "/S", "/Q", targetPath]
        log.debug(f"executing {cmd}")
        process = subprocess.run(cmd, shell=True)
        log.debug(f"process returned: {process}")

    @staticmethod
    def createDirs(dirPaths: [Path]):
        for dirPath in dirPaths:
            FsTools.createDir(dirPath)

    @staticmethod
    def createDir(dirPath: Path):
        dirPath.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def deleteDir(dirPath: Path, recursive=False):
        if len(Path(dirPath).parts) < FsTools.MIN_PATH_DEPTH_FOR_DELETE:
            log.warning(f"prevented delete of path {dirPath} since it has a depth lower than {FsTools.MIN_PATH_DEPTH_FOR_DELETE}")
            raise SafetyException(f"prevented delete of path {dirPath} since it has a depth lower than {FsTools.MIN_PATH_DEPTH_FOR_DELETE}")
        
        if dirPath.exists():
            if recursive:
                shutil.rmtree(dirPath)
            else:
                dirPath.rmdir()

    @staticmethod
    def createFileWithContent(filePath, content):
        with open(filePath, "w") as file:
            print(content, file=file)

    @staticmethod
    def deleteFile(filePath: Path):
        filePath.unlink()

    @staticmethod
    def copy(source: Path, destination: Path):
        """ destination may be a directory """
        shutil.copy(source, destination)

    @staticmethod
    def copyFile(source: Path, destination: Path):
        """ both src and dst must be files """
        shutil.copyfile(source, destination)

    @staticmethod
    def copyDir(source: Path, destination: Path):
        """ recursively copy source *into* destination """
        if destination.is_dir() and destination.exists():
            destination = Path(f"{destination}/{source.name}")
        shutil.copytree(source, destination, dirs_exist_ok=True)

    @staticmethod
    def realToHumanFileSize(size: int) -> str:
        return humanize.naturalsize(size, gnu=True)

    @staticmethod
    def humanToRealFileSize(size: str) -> int:
        gnuSizes = "KMGTPEZY"
        number = float(size.rstrip(gnuSizes))
        unit = size[-1:]
        idx = gnuSizes.index(unit) + 1      # index in list of sizes determines power to raise it to
        factor = 1024 ** idx                # ** is the "exponent" operator - you can use it instead of math.pow()
        return math.floor(number * factor)
    
    @staticmethod
    def hasEnoughFreeDiskSpace(driveToCheck, minimumSpaceHuman):
        """
        checks if given drive has enough free space, returns a tuple with True if yes, otherwise False
        The returned tuple is (bool, freeSpace, freeSpaceHuman)
        """
        minimumSpace = FsTools.humanToRealFileSize(minimumSpaceHuman)
        freeSpace = shutil.disk_usage(path=driveToCheck).free
        freeSpaceHuman = FsTools.realToHumanFileSize(freeSpace)
        if freeSpace < minimumSpace:
            return False, freeSpace, freeSpaceHuman
        else:
            return True, freeSpace, freeSpaceHuman

    @staticmethod        
    def isGlobPattern(path):
        # Define a regex pattern to match any glob metacharacters
        glob_patterns = r"[*?[\]{}!]"
        return bool(re.search(glob_patterns, str(path)))        
    
    @staticmethod
    def toAbsolutePaths(paths: [Path], parent: Path) -> List[Path]:
        """
        returns the list of paths given, but all relative links will be joined with the given parent path.
        """
        absolutePaths = []
        for path in paths:
            if Path(path).is_absolute():
                absolutePaths.append(Path(path))
            else:
                absolutePaths.append(Path(parent).joinpath(path).absolute())
        return absolutePaths

    @staticmethod    
    def resolveGlobs(paths: List[Path]) -> List[Path]:
        """
        will resolve any glob pattern given in the list of paths and add them to the resulting list. Any non-pattern path will be added as is.
        """
        resolvedPaths = []
        for path in paths:
            if FsTools.isGlobPattern(path):
                globResult = glob(pathname=Path(path).as_posix(), recursive=True)
                for entry in globResult:
                    resolvedPaths.append(Path(entry).resolve())
                
            else:
                resolvedPaths.append(Path(path).resolve())
        return resolvedPaths
    
    @staticmethod
    def pathContainsSubPath(path: Path, subPath: Path):
        """
        returns true if subPath is contained in path.
        """
        try:
            child = Path(subPath).resolve()
            parent = Path(path).resolve()
        except FileNotFoundError:
            return False
        return child.parts[:len(parent.parts)] == parent.parts

