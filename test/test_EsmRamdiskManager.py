import logging
from pathlib import Path
from shutil import rmtree
import sys
import unittest
from esm import EsmLogger
from esm.EsmConfig import EsmConfig
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.Jointpoint import Jointpoint

log = logging.getLogger(__name__)

class test_EsmRamdiskManager(unittest.TestCase):

    def test_install(self):
        self.config = EsmConfig.fromConfigFile("test/esm-test-config.yaml")
        self.fs = EsmFileSystem(self.config)
        self.ds = EsmDedicatedServer.withConfig(self.config)
        self.rdm = EsmRamdiskManager(self.config, dedicatedServer=self.ds)

        # prepare folders
        self.createTestFileSystem()
        savegamePath = self.fs.getAbsolutePathTo("saves.games.savegame")
        savegameMirror = self.fs.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        self.assertTrue(savegamePath.exists())
        self.assertFalse(savegameMirror.exists())

        # do the install
        self.rdm.install()

        self.assertFalse(savegamePath.exists())
        self.assertTrue(savegameMirror.exists())

        # remove testing trash
        rmtree(self.config.paths.install)

    @unittest.skip("only execute this manually, since it requires admin privileges and will pop up that window for the user.")
    def test_setup(self):
        self.config = EsmConfig.fromConfigFile("test/esm-test-config.yaml")
        self.fs = EsmFileSystem(self.config)
        self.ds = EsmDedicatedServer.withConfig(self.config)
        self.rdm = EsmRamdiskManager(self.config, dedicatedServer=self.ds)

        # prepare folders
        self.createTestFileSystem()
        savegamePath = self.fs.getAbsolutePathTo("saves.games.savegame")
        savegameTemplates = self.fs.getAbsolutePathTo("saves.games.savegame.templates")
        savegameTemplates.mkdir(parents=True, exist_ok=True)
        savegameMirror = self.fs.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        self.rdm.install()
        self.assertFalse(savegamePath.exists())
        self.assertTrue(savegameMirror.exists())

        self.rdm.setup()

        # check ramdisk exists
        self.assertTrue(self.rdm.checkRamdrive(self.config.ramdisk.drive))
        ramdiskSavegame = self.fs.getAbsolutePathTo("ramdisk.savegame", prefixInstallDir=False)
        self.assertTrue(ramdiskSavegame.exists())
        self.assertTrue(savegamePath.exists())
        self.assertTrue(Jointpoint.isHardLink(linkPath=savegamePath))
        self.assertTrue(savegameMirror.exists())

        # check externalizeTemplate worked
        savegameTemplates = self.fs.getAbsolutePathTo("saves.games.savegame.templates")
        self.assertTrue(Jointpoint.isHardLink(linkPath=savegameTemplates))
        templateshddcopy = self.fs.getAbsolutePathTo("saves.gamesmirror.savegametemplate")
        self.assertTrue(templateshddcopy.exists())

        rmtree(self.config.paths.install)

    def createTestFileSystem(self):
        if Path(self.config.paths.install).exists():
            rmtree(self.config.paths.install)

        self.createDir("saves.games.savegame")
        self.createFile(self.config.filenames.buildNumber, "4243 ")

    def createDir(self, dir):
        dir = self.fs.getAbsolutePathTo(dir)
        dir.mkdir(parents=True, exist_ok=True)

    def createFile(self, fileName, content):
        filePath = Path(f"{self.config.paths.install}/{fileName}").absolute()
        with open(filePath, "w") as file:
            print(content, file=file)

