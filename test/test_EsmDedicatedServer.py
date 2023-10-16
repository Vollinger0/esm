import logging
from pathlib import Path
import unittest
from esm.EsmDedicatedServer import EsmDedicatedServer, GfxMode, StartMode
from esm.EsmConfigService import EsmConfigService

log = logging.getLogger(__name__)

class test_EsmDedicatedServer(unittest.TestCase):

    def test_createLogFileName(self):
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml')
        
        # create the buildnumber file in the testdata first
        self.createBuildNumberFile(esmConfig)

        esmDS = EsmDedicatedServer(config=esmConfig)
        logFileName = esmDS.createLogFileName()
        logFileNameFirst23 = logFileName[:23]
        logFileNameLast4 = logFileName[-4:]
        self.assertEqual("../Logs/4243/Dedicated_", logFileNameFirst23)
        self.assertEqual(".log", logFileNameLast4)

    def createBuildNumberFile(self, esmConfig):
        filePath = Path(f"{esmConfig.paths.install}/{esmConfig.filenames.buildNumber}").absolute()
        filePath.parent.mkdir(parents=True, exist_ok=True)
        with open(filePath, "w") as file:
            file.write("4243 ")

    def test_getGfxMode(self):
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml')
        esmDS = EsmDedicatedServer(config=esmConfig)
        self.assertEqual(esmConfig.server.gfxMode, True)
        mode = esmDS.gfxMode
        self.assertEqual(mode, GfxMode.ON)
        
        esmDS.gfxMode = GfxMode.OFF
        mode = esmDS.gfxMode
        self.assertEqual(mode, GfxMode.OFF)

    def test_getStartModeByString(self):
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml')
        esmDS = EsmDedicatedServer(config=esmConfig)

        mode = esmDS.startMode
        self.assertEqual(mode, StartMode.LAUNCHER)

        esmDS.startMode = StartMode.DIRECT
        mode = esmDS.startMode
        self.assertEqual(mode, StartMode.DIRECT)

    def test_getCommandForLauncherMode(self):
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml')
        esmDS = EsmDedicatedServer(config=esmConfig)
        esmDS.gfxMode = GfxMode.ON

        command = esmDS.getCommandForLauncherMode()
        commandStrings = []
        for thing in command:
            commandStrings.append(str(thing))
        self.assertEqual(f"{esmConfig.paths.install}\\EmpyrionLauncher.exe -startDediWithGfx -dedicated esm-dedicated.yaml", " ".join(commandStrings))

    def test_getCommandForDirectMode(self):
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml')
        # create the buildnumber file in the testdata first
        self.createBuildNumberFile(esmConfig)
        esmDS = EsmDedicatedServer(config=esmConfig)
        esmDS.gfxMode = GfxMode.ON

        command = esmDS.getCommandForDirectMode()
        commandStrings = []
        for thing in command:
            commandStrings.append(str(thing))
        expected = f"{esmConfig.paths.install}\\DedicatedServer\\EmpyrionDedicated.exe -dedicated esm-dedicated.yaml -logFile ../Logs/4243/"
        actual = " ".join(commandStrings)
        log.debug(f"expected: {expected}")
        log.debug(f"actual: {actual}")
        #self.assertEqual(expected, actual)
        self.assertTrue(actual.startswith(expected))

    def test_getCommandForDirectModeNoGfx(self):
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml')
        # create the buildnumber file in the testdata first
        self.createBuildNumberFile(esmConfig)
        esmDS = EsmDedicatedServer(config=esmConfig)
        esmDS.gfxMode = GfxMode.OFF

        command = esmDS.getCommandForDirectMode()
        commandStrings = []
        for thing in command:
            commandStrings.append(str(thing))
        expected = f"{esmConfig.paths.install}\\DedicatedServer\\EmpyrionDedicated.exe -batchmode -nographics -dedicated esm-dedicated.yaml -logFile ../Logs/4243/"
        actual = " ".join(commandStrings)
        log.debug(f"expected: {expected}")
        log.debug(f"actual: {actual}")
        #self.assertEqual(expected, actual)
        self.assertTrue(actual.startswith(expected))

