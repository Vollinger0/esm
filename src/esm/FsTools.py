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
    def copyFile(source: Path, destination: Path):
        shutil.copyfile(source, destination)

