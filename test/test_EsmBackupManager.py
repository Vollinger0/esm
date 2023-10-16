
import logging
import unittest
from esm.EsmBackupManager import EsmBackupManager

from esm.EsmConfig import EsmConfig
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmRamdiskManager import EsmRamdiskManager


log = logging.getLogger(__name__)

class test_EsmBackupManager(unittest.TestCase):

    def test_getTargetBackupFolder(self):
        self.config = EsmConfig.fromConfigFile("test/esm-test-config.yaml")
        self.fs = EsmFileSystem(self.config)
        self.bm = EsmBackupManager(self.config)

        return

        backupParent = self.fs.getAbsolutePathTo("backup.backupmirrors")
        actual = self.bm.getTargetBackupFolder()
        expected = f"{backupParent}/{self.config.foldernames.backupmirrorprefix}1"
        self.assertEquals(expected, actual)
