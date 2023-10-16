import os
import subprocess
import logging
from pathlib import Path

log = logging.getLogger(__name__)

class Jointpoint:
    """
    represents hardlink/jointpoint in the file system
    """
    @staticmethod
    def create(link, target):
        """
        create a windows hardlink (jointpoint) as link to the linktarget using mklink
        """
        # looks like none of the python-libararies can do this without running into problems
        # calling the shell command works flawlessly...
        return subprocess.run(f"mklink /H /J {link} {target}", capture_output=True, shell=True)

    @staticmethod
    def delete(link):
        linkPath = Path(link)
        if linkPath.is_dir:
            linkPath.rmdir()
        else:
            linkPath.unlink(missing_ok=True)

    @staticmethod
    def isHardLink(link):
        try:
            if os.readlink(link):
                return True
            else:
                return False
        except OSError:
            return False

    # @staticmethod
    # def isHardLink(link):
    #     # this won't work on windows. looks like there is no other way than to use low-level winapi calls to check that :facepalm:
    #     return Path(link).is_symlink()
