import math
import os
import shutil
import subprocess
import logging
from pathlib import Path

import humanize

log = logging.getLogger(__name__)

class FsTools:
    """
    Tools to work with the file system, includes handling of hardlink/jointpoint
    """
    @staticmethod
    def createLink(linkPath, targetPath):
        """
        create a windows hardlink (jointpoint) as link to the linktarget using mklink
        """
        # looks like none of the python-libraries can do this without running into problems
        # calling the shell command works flawlessly...
        log.debug(f"mklink /H /J \"{linkPath}\" \"{targetPath}\"")
        return subprocess.run(f"mklink /H /J \"{linkPath}\" \"{targetPath}\"", capture_output=True, shell=True)

    @staticmethod
    def deleteLink(linkPath):
        linkPath = Path(linkPath)
        if linkPath.is_dir:
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
                linkInfo = entry.readlink()
                fixedLinkInfo = Path(linkInfo.as_posix()[4:]).resolve()
                target = targetFolder.resolve()
                #log.debug(f"entry: '{entry}', fixedLinkInfo: '{fixedLinkInfo}', targetFolder: '{targetFolder}', target '{target}'")
                if fixedLinkInfo.exists():
                    #log.debug(f"fixedLinkInfo: '{fixedLinkInfo}' exists")
                    if fixedLinkInfo.samefile(target):
                        #log.debug(f"fixedLinkInfo: '{fixedLinkInfo}' and '{target}' are the same file")
                        links.append(entry)
        return links

    # @staticmethod
    # def isHardLink(link):
    #     # this won't work on windows. looks like there is no other way than to use low-level winapi calls to check that :facepalm:
    #     return Path(link).is_symlink()
        
    @staticmethod
    def quickDelete(targetPath):
        """
        quickly delete a folder and all its content
        """
        shutil.rmtree(ignore_errors=True, path=targetPath)

    @staticmethod
    def createDir(dirPath: Path):
        dirPath.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def deleteDir(dirPath: Path, recursive=False):
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
        checks if given drive has enough free space, returns True if yes, otherwise False
        """
        minimumSpace = FsTools.humanToRealFileSize(minimumSpaceHuman)
        freeSpace = shutil.disk_usage(path=driveToCheck).free
        freeSpaceHuman = FsTools.realToHumanFileSize(freeSpace)
        log.debug(f"Free space on drive {driveToCheck} is {freeSpaceHuman}. Configured minimum for start up is {minimumSpaceHuman}")
        if freeSpace < minimumSpace:
            return False
        else:
            return True

