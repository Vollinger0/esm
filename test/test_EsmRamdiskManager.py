import logging
from pathlib import Path
from shutil import rmtree
import unittest
from esm.EsmMain import EsmMain
from esm.EsmConfigService import EsmConfigService
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmFileSystem import EsmFileSystem
from esm.EsmRamdiskManager import EsmRamdiskManager
from esm.FsTools import FsTools
from esm.ServiceRegistry import ServiceRegistry
from TestTools import TestTools

log = logging.getLogger(__name__)

@unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
class test_EsmRamdiskManager(unittest.TestCase):

    @unittest.skip("only execute this manually, since it is too easy to break things")
    def test_install(self):
        ServiceRegistry.register(EsmMain)
        # TODO: set own configservice, or mock it
        #self.config = EsmConfigService(configFilePath="test/esm-test-config.yaml")
        self.fs = EsmFileSystem(self.config)
        self.rdm = EsmRamdiskManager(config=self.config, fileSystem=self.fs)

        # prepare folders
        self.createTestFileSystem()
        savegamePath = self.fs.getAbsolutePathTo("saves.games.savegame")
        savegameMirror = self.fs.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        self.assertTrue(savegamePath.exists())
        self.assertFalse(savegameMirror.exists())

        # do the install
        self.rdm.prepare()

        self.assertFalse(savegamePath.exists())
        self.assertTrue(savegameMirror.exists())

        # remove testing trash
        #TODO: nope, too dangerous.
        #rmtree(self.config.paths.install)

    @unittest.skip("only execute this manually, since it requires admin privileges and will pop up that window for the user.")
    def test_setup(self):
        ServiceRegistry.register(EsmMain)
        self.config = EsmConfigService(configFilePath="test/esm-test-config.yaml")
        self.fs = EsmFileSystem(self.config)
        self.rdm = EsmRamdiskManager(config=self.config, fileSystem=self.fs)

        # prepare folders
        self.createTestFileSystem()
        savegamePath = self.fs.getAbsolutePathTo("saves.games.savegame")
        savegameTemplates = self.fs.getAbsolutePathTo("saves.games.savegame.templates")
        savegameTemplates.mkdir(parents=True, exist_ok=True)
        savegameMirror = self.fs.getAbsolutePathTo("saves.gamesmirror.savegamemirror")
        self.rdm.prepare()
        self.assertFalse(savegamePath.exists())
        self.assertTrue(savegameMirror.exists())

        self.rdm.setup()

        # check ramdisk exists
        self.assertTrue(self.rdm.checkRamdrive(self.config.ramdisk.drive))
        ramdiskSavegame = self.fs.getAbsolutePathTo("ramdisk.savegame", prefixInstallDir=False)
        self.assertTrue(ramdiskSavegame.exists())
        self.assertTrue(savegamePath.exists())
        self.assertTrue(FsTools.isHardLink(savegamePath))
        self.assertTrue(savegameMirror.exists())

        # check externalizeTemplate worked
        savegameTemplates = self.fs.getAbsolutePathTo("saves.games.savegame.templates")
        self.assertTrue(FsTools.isHardLink(savegameTemplates))
        templateshddcopy = self.fs.getAbsolutePathTo("saves.gamesmirror.savegametemplate")
        self.assertTrue(templateshddcopy.exists())

        rmtree(self.config.paths.install)

    def createTestFileSystem(self):
        if Path(self.config.paths.install).exists():
            rmtree(self.config.paths.install)

        self.createDir("saves.games.savegame")
        self.fs.getAbsolutePathTo("saves.games.savegame.globaldb").write_text("blabla")
        self.createFile(self.config.filenames.buildNumber, "4243 ")

    def createDir(self, dir):
        dirPath = self.fs.getAbsolutePathTo(dir)
        FsTools.createDirs([dirPath])

    def createFile(self, fileName, content):
        filePath = Path(f"{self.config.paths.install}/{fileName}").absolute()
        FsTools.createFileWithContent(filePath, content=content)

    @unittest.skip("only execute this manually, since it requires admin privileges and will pop up that window for the user.")
    def test_mountAndUnmountRamdisk(self):
        ServiceRegistry.register(EsmMain)
        self.config = EsmConfigService(configFilePath="test/esm-test-config.yaml")
        self.fs = EsmFileSystem(self.config)
        self.rdm = EsmRamdiskManager(config=self.config, fileSystem=self.fs)

        driveLetter = self.config.ramdisk.drive
        driveSize = self.config.ramdisk.size
        self.rdm.mountRamdrive(driveLetter=driveLetter, driveSize=driveSize)
        self.assertTrue(self.rdm.checkRamdrive(driveLetter=driveLetter))
        self.rdm.unmountRamdisk(driveLetter=driveLetter)
        self.assertFalse(self.rdm.checkRamdrive(driveLetter=driveLetter))
