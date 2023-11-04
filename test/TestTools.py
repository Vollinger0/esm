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
        does skip the test if the ramdisk is not available at the driveletter R:
        since we usually have that mounted while developing this, just use it.
        """
        log.info(f"testing if ramdisk is available for a unittest")
        return Path(TestTools.TESTRAMDRIVELETTER).exists()
        
