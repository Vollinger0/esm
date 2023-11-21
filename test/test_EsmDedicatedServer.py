import logging
from pathlib import Path
import unittest
from esm.ConfigModels import MainConfig
from esm.EsmDedicatedServer import EsmDedicatedServer
from esm.EsmConfigService import EsmConfigService
from TestTools import TestTools
from esm.FsTools import FsTools

log = logging.getLogger(__name__)

class test_EsmDedicatedServer(unittest.TestCase):

    @unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
    @classmethod
    def setUpClass(self):
        sourcePath = "test/test-dedicated.yaml"
        destinationPath = Path("R:/Servers/Empyrion")
        destinationPath.mkdir(parents=True,exist_ok=True)
        FsTools.copyFile(sourcePath, f"{destinationPath}/esm-dedicated.yaml")

    @unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
    def test_createLogFileName(self):
        esmConfig = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"), True)

        # create the buildnumber file in the testdata first
        self.createBuildNumberFile(esmConfig)
        esmDS = EsmDedicatedServer()
        logFileName = esmDS.createLogFileName()
        logFileNameFirst23 = logFileName[:23]
        logFileNameLast4 = logFileName[-4:]
        self.assertEqual("../Logs/4243/Dedicated_", logFileNameFirst23)
        self.assertEqual(".log", logFileNameLast4)

    def createBuildNumberFile(self, esmConfig: MainConfig):
        filePath = Path(f"{esmConfig.paths.install}/{esmConfig.filenames.buildNumber}").absolute()
        filePath.parent.mkdir(parents=True, exist_ok=True)
        with open(filePath, "w") as file:
            file.write("4243 ")

    def test_getCommandForLauncherMode(self):
        esmConfig = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"), True)
        esmDS = EsmDedicatedServer()
        esmConfig.server.gfxMode = True

        command = esmDS.getCommandForLauncherMode()
        commandStrings = []
        for thing in command:
            commandStrings.append(str(thing))
        self.assertEqual(f"{esmConfig.paths.install}\EmpyrionLauncher.exe -startDediWithGfx -dedicated test\\test-dedicated.yaml", " ".join(commandStrings))

    @unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
    def test_getCommandForDirectMode(self):
        esmConfig = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"), True)
        # create the buildnumber file in the testdata first
        self.createBuildNumberFile(esmConfig)
        esmDS = EsmDedicatedServer()
        esmConfig.server.gfxMode = True

        command = esmDS.getCommandForDirectMode()
        commandStrings = []
        for thing in command:
            commandStrings.append(str(thing))
        expected = f"{esmConfig.paths.install}\DedicatedServer\EmpyrionDedicated.exe -dedicated test\\test-dedicated.yaml -logFile ../Logs/4243/Dedicated_yymmdd-hhmmss.log"
        actual = " ".join(commandStrings)
        log.debug(f"expected: {expected}")
        log.debug(f"actual: {actual}")
        self.assertEqual(expected[:-17], actual[:-17])

    @unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
    def test_getCommandForDirectModeNoGfx(self):
        esmConfig = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"), True)
        # create the buildnumber file in the testdata first
        self.createBuildNumberFile(esmConfig)
        esmDS = EsmDedicatedServer()
        esmConfig.server.gfxMode = False

        command = esmDS.getCommandForDirectMode()
        commandStrings = []
        for thing in command:
            commandStrings.append(str(thing))
        expected = f"{esmConfig.paths.install}\DedicatedServer\EmpyrionDedicated.exe -batchmode -nographics -dedicated test\\test-dedicated.yaml -logFile ../Logs/4243/Dedicated_yymmdd-hhmmss.log"
        actual = " ".join(commandStrings)
        log.debug(f"expected: {expected}")
        log.debug(f"actual: {actual}")
        self.assertEqual(expected[:-17], actual[:-17])
