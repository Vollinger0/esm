import os
import shutil
import subprocess
import logging
from pathlib import Path

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
        # looks like none of the python-libararies can do this without running into problems
        # calling the shell command works flawlessly...
        return subprocess.run(f"mklink /H /J {linkPath} {targetPath}", capture_output=True, shell=True)

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
    def createDir(dirPath):
        dirPath.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def deleteDir(dirPath: Path, recursive=False):
        if dirPath.exists():
            if recursive:
                shutil.rmtree(dirPath)
            else:
                dirPath.rmdir()


    @staticmethod
    def createFile(filePath, content):
        with open(filePath, "w") as file:
            print(content, file=file)

    @staticmethod
    def deleteFile(filePath: Path):
        filePath.unlink()
