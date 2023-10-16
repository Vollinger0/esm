import logging
import os
from pathlib import Path
import unittest
from esm.EsmConfig import EsmConfig

from esm.EsmFileStructure import EsmFileStructure
from esm.Jointpoint import Jointpoint

log = logging.getLogger(__name__)

class test_EsmFileStructure(unittest.TestCase):

    def test_walkablePathTree(self):
        esmConfig = EsmConfig.fromConfigFile("esm-config.yaml")
        esmfs = EsmFileStructure(config=esmConfig)
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

    def test_createJointPoint(self):
        esmConfig = EsmConfig.fromConfigFile("esm-config.yaml")
        esmfs = EsmFileStructure(config=esmConfig)
        target = Path("test-linktarget")
        link = Path("test-link")

        # make sure its cleaned up first
        self.cleanTestFolders(target, link)
        
        target.mkdir()
        esmfs.createJointpoint(link=link, linkTarget=target)

        self.assertTrue(target.exists())
        self.assertTrue(link.exists())
        self.assertTrue(Jointpoint.isHardLink(link))
        self.assertFalse(Jointpoint.isHardLink(target))

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
