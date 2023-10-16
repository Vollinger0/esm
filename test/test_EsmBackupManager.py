
import logging
import unittest

log = logging.getLogger(__name__)

class test_EsmBackupManager(unittest.TestCase):
    pass
    # def test_getTargetBackupFolder(self):
    #     self.config = EsmConfigService(configFilePath="test/esm-test-config.yaml")
    #     self.fs = EsmFileSystem()
    #     self.bm = EsmBackupManager()

    #     backupParent = self.fs.getAbsolutePathTo("backup.backupmirrors")
    #     actual = self.bm.getTargetBackupFolder()
    #     expected = f"{backupParent}/{self.config.foldernames.backupmirrorprefix}1"
    #     self.assertEquals(expected, actual)
