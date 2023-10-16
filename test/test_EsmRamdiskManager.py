import logging
from pathlib import Path
from shutil import rmtree
import sys
import unittest
from esm import EsmLogger
from esm.EsmConfig import EsmConfig
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmFileStructure import EsmFileStructure
from esm.EsmRamdiskManager import EsmRamdiskManager

log = logging.getLogger(__name__)

class test_EsmRamdiskManager(unittest.TestCase):

    def test_install(self):
        self.config = EsmConfig.fromConfigFile("test/esm-test-config.yaml")
        self.fs = EsmFileStructure(self.config)
        self.ds = EsmDedicatedServer.withConfig(self.config)
        self.rdm = EsmRamdiskManager(self.config, dedicatedServer=self.ds)

        # prepare folders
        self.createTestFileSystem()
        savegamePath = self.fs.getAbsolutePathTo("saves.games.savegame")
        savegameMirror = self.fs.getAbsolutePathTo("saves.gamesmirror.savegamemirror")

        self.assertTrue(savegamePath.exists())
        self.assertFalse(savegameMirror.exists())

        self.rdm.install()

        self.assertFalse(savegamePath.exists())
        self.assertTrue(savegameMirror.exists())

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

