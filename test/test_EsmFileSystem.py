import logging
import os
from pathlib import Path
import shutil
import time
import unittest

from esm.EsmFileSystem import EsmFileSystem
from esm.FsTools import FsTools
from TestTools import TestTools

log = logging.getLogger(__name__)

class test_EsmFileSystem(unittest.TestCase):
    
    @unittest.skip("TODO: need to inject custom configuration here")
    def test_walkablePathTree(self):
        esmfs = EsmFileSystem()
        log.debug(f"esmfs: {esmfs}")
        log.debug(f"esmfs.structure: {esmfs.structure}")

        path = esmfs.getPathTo("saves.games.savegame")
        self.assertEqual("Saves/Games/EsmDediGame", path)

        path = esmfs.getPathTo("saves.games.savegame.templates")
        self.assertEqual("Saves/Games/EsmDediGame/Templates", path)

        path = esmfs.getPathTo("saves")
        self.assertEqual("Saves", path)

        path = esmfs.getPathTo("saves.games.savegame.templates")
        self.assertEqual("Saves/Games/EsmDediGame/Templates", path)

        path = esmfs.getPathTo("saves.games.savegame.globaldb")
        self.assertEqual("Saves/Games/EsmDediGame/global.db", path)

        path = esmfs.getPathTo("saves.gamesmirror.savegamemirror.globaldb")
        self.assertEqual("Saves/GamesMirror/EsmDediGame_Mirror/global.db", path)

        path = esmfs.getPathTo("saves.gamesmirror.savegamemirror")
        self.assertEqual("Saves/GamesMirror/EsmDediGame_Mirror", path)

        path = esmfs.getPathTo("saves.gamesmirror.savegametemplate")
        self.assertEqual("Saves/GamesMirror/EsmDediGame_Templates", path)

        path = esmfs.getPathTo("ramdisk.savegame")
        self.assertEqual("R:/EsmDediGame", path)

    def test_createHardLink(self):
        esmfs = EsmFileSystem()
        target = Path("test-linktarget")
        link = Path("test-link")

        # make sure its cleaned up first
        self.cleanTestFolders(target, link)
        
        target.mkdir()
        esmfs.createHardLink(linkPath=link, linkTargetPath=target)

        self.assertTrue(target.exists())
        self.assertTrue(link.exists())
        self.assertTrue(FsTools.isHardLink(link))
        self.assertFalse(FsTools.isHardLink(target))

        # clean up
        self.cleanTestFolders(target, link)

    def cleanTestFolders(self, target, link):
        if link.exists():
            if link.is_dir():
                link.rmdir()
            else:
                os.unlink(link)
                link.unlink(missing_ok=True)
        if target.exists(): 
            target.rmdir()

    @unittest.skip("this is too dangerous to keep yet, FSTools need to make sure it doesn't delete too much!")
    def test_deleteByPattern(self):
        esmfs = EsmFileSystem()
        FsTools.quickDelete("pattern_test")

        dir1 = Path("pattern_test/foo/bar")
        file1 = Path("pattern_test/foo/baz.txt")
        file2 = Path("pattern_test/foo/moo.txt")
        file3 = Path("pattern_test/foo/moep.dat")
        FsTools.createDirs([dir1])
        for file in [file1, file2, file3]:
            file.write_text("blubb")

        for entry in [dir1, file1, file2, file3]:
            self.assertTrue(entry.exists())

        paths = FsTools.resolveGlobs(["pattern_test/foo/*.txt"])
        for path in paths:
            log.debug(f"would delete {path}")
            esmfs.markForDelete(path)
            esmfs.commitDelete("yes")

        for entry in [dir1, file3]:
            self.assertTrue(entry.exists())
        self.assertFalse(file1.exists())
        self.assertFalse(file2.exists())

        FsTools.quickDelete("pattern_test")

    @unittest.skip("this is too dangerous to keep yet, FSTools need to make sure it doesn't delete too much!")
    def test_deleteAndCommit(self):
        esmfs = EsmFileSystem()
        FsTools.quickDelete("delete_test")

        dir1 = Path("delete_test/foo/bar")
        file1 = Path("delete_test/foo/baz.txt")
        file2 = Path("delete_test/foo/moo.txt")
        file3 = Path("delete_test/foo/moep.dat")
        FsTools.createDirs([dir1])
        for file in [file1, file2, file3]:
            file.write_text("blubb")
        for entry in [dir1, file1, file2, file3]:
            self.assertTrue(entry.exists())

        esmfs.markForDelete(dir1)
        esmfs.markForDelete(file2)

        for entry in [dir1, file1, file2, file3]:
            self.assertTrue(entry.exists())

        absolutePaths = FsTools.toAbsolutePaths(paths=[dir1, file2], parent=Path("."))
        self.assertListEqual(sorted(esmfs.getPendingDeletePaths()), sorted(absolutePaths))

        esmfs.commitDelete(override="yes")

        for entry in [file1, file3]:
            self.assertTrue(entry.exists())
        self.assertFalse(dir1.exists())
        self.assertFalse(file2.exists())

        FsTools.quickDelete("delete_test")

    @unittest.skip("TODO: need to inject custom configuration here")
    def test_testLinkGeneration(self):
        esmfs = EsmFileSystem()

        result = esmfs.testLinkGeneration()        
        self.assertTrue(result)

    @unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
    def test_synchronization(self):
        def setFixedCTime(path: Path, ctime):
            os.utime(path, (ctime, ctime))

        esmfs = EsmFileSystem()
        basedir = Path(f"{TestTools.TESTRAMDRIVELETTER}/test_synchronization/")
        if basedir.exists():
            shutil.rmtree(basedir)
        sourceFileStructure = {"test_scenario": {
            "folder1": {
                "folder1.1": {
                    "folder1.1.1": {
                        "file1.1.1.1": "gnaa"
                    },
                    "file1.1.1": "schubidoo"
                },
                "file1.1.Updated": "newcontent"
            },
            "folder2": {
                "file2.1": "moep1",
                "file2.2": "moep2",
                "file2.3.New": "moep3",
            },
            "folder3": {},
            "folder4.New": {},
            "file1": "blabla",
            "file2": "blubb"
        }}
        destinationFileStructure = {"test_scenario_  destination": {
            "folder1": {
                "folder1.1": {
                    "folder1.1.1": {
                        "file1.1.1.1": "gnaa"
                    },
                    "file1.1.1": "schubidoo"
                },
                "file1.1.Updated": "oldcontent",
                "folder1.1.Old": {}
            },
            "folder2": {
                "file2.1": "moep1",
                "file2.2": "moep2",
                "file2.3.Old": "moep3"
            },
            "folder3": {},
            "file1": "blabla",
            "file2": "blubb"
        }}
        ctime = time.time()-200000
        TestTools.createFileStructure(sourceFileStructure, basedir, setFixedCTime, ctime)
        sourcePath = Path(f"{basedir}/test_scenario/")
        ctime = time.time()-300000
        TestTools.createFileStructure(destinationFileStructure, basedir, setFixedCTime, ctime)
        destinationPath = Path(f"{basedir}/test_scenario_  destination/")
        
        # differences
        self.assertTrue(Path(f"{sourcePath}/folder1/file1.1.Updated").exists()) 
        self.assertEqual(Path(f"{sourcePath}/folder1/file1.1.Updated").read_text(), "newcontent")
        self.assertTrue(Path(f"{sourcePath}/folder2/file2.3.New").exists()) 
        self.assertTrue(Path(f"{sourcePath}/folder4.New").exists()) 

        self.assertTrue(Path(f"{destinationPath}/folder1/file1.1.Updated").exists()) 
        self.assertEqual(Path(f"{destinationPath}/folder1/file1.1.Updated").read_text(), "oldcontent")
        self.assertTrue(Path(f"{destinationPath}/folder1/folder1.1.Old").exists()) 
        self.assertTrue(Path(f"{destinationPath}/folder2/file2.3.Old").exists()) 
        self.assertFalse(Path(f"{destinationPath}/folder2/file2.3.New").exists()) 
        self.assertFalse(Path(f"{destinationPath}/folder4.New").exists()) 

        # now do the actual call
        esmfs.synchronize(sourcePath=sourcePath, destinationPath=destinationPath)

        # check results
        self.assertTrue(Path(f"{destinationPath}/folder1/file1.1.Updated").exists()) # updated file still exists
        self.assertEqual(Path(f"{destinationPath}/folder1/file1.1.Updated").read_text(), "newcontent") # content has been updated
        self.assertFalse(Path(f"{destinationPath}/folder1/folder1.1.Old").exists()) # directory has been deleted
        self.assertFalse(Path(f"{destinationPath}/folder2/file2.3.Old").exists()) # file has been deleted
        self.assertTrue(Path(f"{destinationPath}/folder2/file2.3.New").exists()) # file has been created
        self.assertTrue(Path(f"{destinationPath}/folder4.New").exists()) # directory has been created
