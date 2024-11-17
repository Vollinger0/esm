import logging
from pathlib import Path

log = logging.getLogger(__name__)

class TestTools:
    """
    provides some helpers for tests
    """

    TESTRAMDRIVELETTER = "R:"

    @classmethod
    def ramdiskAvailable(*args):
        """
        returns True if the ramdisk is available at the driveletter R:
        use this like this:
            @unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")

        to skip the test if the ramdisk is not available at the driveletter R:
        since we usually have that mounted while developing this, just use it.
        """
        result = Path(TestTools.TESTRAMDRIVELETTER).exists()
        log.info(f"testing if ramdisk is available for a unittest: {result}")
        return result
    
    def createFileStructure(structure: dict, basedir: Path, callback=None, ctime=None):
        """
        creates the filestructure given in the basedir. This is to create a test fixture that can be safely deleted afterwards by deleting the base dir
        structure is a dictionary that will be walked through recursively. if a value is a dictionary, a directory will be created, otherwise a file and the string will be the content.
        """
        basedir.mkdir(parents=True, exist_ok=True)
        callback(basedir, ctime)

        for key in structure.keys():
            subStructure = structure.get(key)
            subPath = Path(f"{basedir}/{key}")
            if isinstance(subStructure, dict):
                TestTools.createFileStructure(subStructure, subPath, callback, ctime)
            else:
                # no dict, then create a file
                subPath.write_text(str(subStructure))
                callback(subPath, ctime)
        return True
        
