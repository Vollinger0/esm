import logging
import os
from pathlib import Path
import unittest
from esm.EsmConfigService import EsmConfigService

from esm.EsmFileSystem import EsmFileSystem
from esm.FsTools import FsTools

log = logging.getLogger(__name__)

class test_EsmFileSystem(unittest.TestCase):

    def test_walkablePathTree(self):
        esmConfig = EsmConfigService(configFilePath="esm-config.yaml")
        esmfs = EsmFileSystem(config=esmConfig)
        log.debug(f"esmfs: {esmfs}")
        log.debug(f"esmfs.structure: {esmfs.structure}")

        path = esmfs.getPathTo("saves.games.savegame")
        self.assertEqual("Saves/Games/EsmDediGame", path)

        path = esmfs.getPathTo("saves.games.savegame.templates")
        self.assertEqual("Saves/Games/EsmDediGame/Templates", path)

        path = esmfs.getPathTo("saves")
        self.assertEqual("Saves", path)

        path = esmfs.getPathTo("saves.gamesmirror.savegamemirror")
        self.assertEqual("Saves/GamesMirror/EsmDediGame_Mirror", path)

        path = esmfs.getPathTo("saves.gamesmirror.savegametemplate")
        self.assertEqual("Saves/GamesMirror/EsmDediGame_Templates", path)

        path = esmfs.getPathTo("ramdisk.savegame")
        self.assertEqual("R:/EsmDediGame", path)

    def test_createHardLink(self):
        esmConfig = EsmConfigService(configFilePath="esm-config.yaml")
        esmfs = EsmFileSystem(config=esmConfig)
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

    def test_deleteByPattern(self):
        esmConfig = EsmConfigService(configFilePath="esm-config.yaml")
        esmfs = EsmFileSystem(config=esmConfig)
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

        esmfs.deleteByPattern("pattern_test/", "foo/*.txt")

        for entry in [dir1, file3]:
            self.assertTrue(entry.exists())
        self.assertFalse(file1.exists())
        self.assertFalse(file2.exists())

        FsTools.quickDelete("pattern_test")        
