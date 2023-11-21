
import logging
from pathlib import Path
import unittest
from esm.EsmBackupService import EsmBackupService

from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from TestTools import TestTools

log = logging.getLogger(__name__)

@unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
class test_EsmBackupService(unittest.TestCase):

    @unittest.skip("this needs a rewrite, use a fresh created virtual filesystem instead")
    def test_assertFileStructure(self):
        config = EsmConfigService.fromCustomConfigFile("test/esm-test-config.yaml")
        bm = EsmBackupService()
        self.assertEqual(config.backups.amount, 4)
        backupParentDir = bm.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        FsTools.quickDelete(backupParentDir)

        for i in range(1, 5):
            expected = f"{backupParentDir}/{config.foldernames.backupmirrorprefix}{i}"
            self.assertFalse(Path(expected).exists())

        bm.assertBackupFilestructure()

        for i in range(1, 5):
            expected = f"{backupParentDir}/{config.foldernames.backupmirrorprefix}{i}"
            self.assertTrue(Path(expected).exists())

    @unittest.skip("this needs a rewrite, use a fresh created virtual filesystem instead")
    def test_getPreviousBackupNumberNoMarker(self):
        config = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"))
        bm = EsmBackupService()
        self.assertEqual(config.backups.amount, 4)
        backupParentDir = bm.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        FsTools.quickDelete(backupParentDir)
        bm.assertBackupFilestructure()
        actual = bm.getPreviousBackupNumber()
        self.assertEqual(actual, None)

    @unittest.skip("this needs a rewrite, use a fresh created virtual filesystem instead")
    def test_getPreviousBackupNumberWithMarker(self):
        config = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"))
        bm = EsmBackupService()
        self.assertEqual(config.backups.amount, 4)
        backupParentDir = bm.fileSystem.getAbsolutePathTo("backup.backupmirrors")
        FsTools.quickDelete(backupParentDir)
        bm.assertBackupFilestructure()
        backupFolder = bm.getRollingBackupFolder(3)
        bm.createMarkerFile(backupFolder)
        actual = bm.getPreviousBackupNumber()
        self.assertEqual(3, actual)

    @unittest.skip("this needs a rewrite, use a fresh created virtual filesystem instead")
    def test_getNextBackupNumber(self):
        config = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"))
        bm = EsmBackupService()
        self.assertEqual(config.backups.amount, 4)

        self.assertEqual(bm.getNextBackupNumber(0), 1)
        self.assertEqual(bm.getNextBackupNumber(1), 2)
        self.assertEqual(bm.getNextBackupNumber(2), 3)
        self.assertEqual(bm.getNextBackupNumber(3), 4)
        self.assertEqual(bm.getNextBackupNumber(4), 1)

    
