import logging
from pathlib import Path
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from esm.exceptions import AdminRequiredException
from esm.ServiceRegistry import ServiceRegistry
from TestTools import TestTools

log = logging.getLogger(__name__)

class test_EsmConfigService(unittest.TestCase):

    def test_ConfigWorks(self):
        cs = EsmConfigService()
        config = cs.getConfig()
        self.assertEqual(config.server.dedicatedYaml, Path("esm-dedicated.yaml"))

    def test_ConfigFailsOnUknownProperties(self):
        cs = EsmConfigService()
        config = cs.getConfig()

        with self.assertRaises(AttributeError):
            self.assertEqual(config.foo.bar, "foo")
        self.assertEqual(config.server.dedicatedYaml, Path("esm-dedicated.yaml"))

    @unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
    @patch("esm.EsmConfigService.EsmConfigService.loadDedicatedYaml", return_value=None)
    def test_loadsCustomPath(self, mock_loadDedicatedYaml):
        cs = EsmConfigService()
        config = cs.getConfig()
        self.assertEqual(config.server.dedicatedYaml, Path("esm-dedicated.yaml"))
        cs.setConfigFilePath(Path("test/esm-test-config.yaml"), True)
        config = cs.getConfig()

        self.assertEqual(config.server.dedicatedYaml, Path("test/test-dedicated.yaml"))
        self.assertEqual(config.backups.amount, 4)
        self.assertEqual(config.ramdisk.drive, "T:")

    @unittest.skipUnless(TestTools.ramdiskAvailable(), "needs the ramdrive to be mounted at r")
    @patch("esm.EsmConfigService.EsmConfigService.loadDedicatedYaml", return_value=None)
    def test_loadFromRegistry(self, mock_loadDedicatedYaml):
        instance = EsmConfigService()
        instance.setConfigFilePath(Path("test/esm-test-config.yaml"), True)
        ServiceRegistry.register(instance)
        cs = ServiceRegistry.get(EsmConfigService)
        config: MainConfig = cs.getConfig()
        self.assertEqual(config.backups.amount, 4)
        self.assertEqual(config.ramdisk.drive, "T:")

    def test_loadingConfigReadsDedicatedYaml(self):
        cs = EsmConfigService()
        config: MainConfig = cs.getConfig()

        self.assertEqual(config.dedicatedConfig.GameConfig.GameName, "EsmDediGame")
        self.assertEqual(config.dedicatedConfig.ServerConfig.AdminConfigFile, "adminconfig.yaml")
        self.assertEqual(config.dedicatedConfig.ServerConfig.SaveDirectory, "Saves")

        # check that the context contains info about the custom file that was read
        self.assertEqual(config.context.get("configFilePath"), Path("esm-custom-config.yaml"))
        
        # check that these two deprecated attributes are not read any more
        with self.assertRaises(AttributeError):
            self.assertIsNone(config.server.savegame)
        with self.assertRaises(AttributeError):
            self.assertIsNone(config.foldernames.saves)

    def test_loadingConfigReadsDedicatedYamlBreaksWhenNotAvailable(self):
        cs = EsmConfigService()
        cs.setConfigFilePath(Path("test/esm-test-missingdedi-config.yaml"))
        with self.assertRaises(AdminRequiredException):
            config = cs.getConfig()

    def test_reading_territories(self):
        cs = EsmConfigService()
        config: MainConfig = cs.getConfig()

        self.assertEqual(config.dedicatedConfig.GameConfig.GameName, "EsmDediGame")
        self.assertEqual(config.dedicatedConfig.ServerConfig.AdminConfigFile, "adminconfig.yaml")
        self.assertEqual(config.dedicatedConfig.ServerConfig.SaveDirectory, "Saves")

        # check that the context contains info about the custom file that was read
        self.assertEqual(config.context.get("configFilePath"), Path("esm-custom-config.yaml"))

        territories = cs.getAvailableTerritories()
        self.assertEqual(16, len(territories))
        for territory in territories:
            log.info(f"territory: {territory.name}, x: {territory.x/100000}, y: {territory.y/100000}, z: {territory.z/100000}, radius: {territory.radius/100000}")

    def test_editingDedicatedYamlRoundTrip(self):
        self.maxDiff = None
        cs = EsmConfigService()
        original = """
ServerConfig:
  Srv_Port: 40000
  Srv_Name: Vollingers Test Server
  Srv_Description: Running on a ramdisk managed by ESM. There's nothing to see here, please move on.
  Srv_MaxPlayers: 8
  Srv_ReservePlayfields: 1
  Srv_Public: false
  EACActive: false
  AdminConfigFile: adminconfig.yaml
  SaveDirectory: Saves
  MaxAllowedSizeClass: 21
  AllowedBlueprints: All
  HeartbeatServer: 15
  TimeoutBootingPfServer: 90
  PlayerLoginParallelCount: 5
  #PlayerLoginVipNames: 76561198086927352,123456789
  PlayerLoginFullServerQueueCount: 10
GameConfig:
  GameName: EsmTestDediGame
  Mode: Survival
  Seed: 42069420
  CustomScenario: TestProjectA
"""
        tempYamlPath = Path("test/test-dedicated-temp.yaml").resolve()
        # create the dedicated yaml
        with open(tempYamlPath, "w") as f:
            f.write(original)
        cs.upsertYamlProperty(tempYamlPath, "GameConfig.SharedDataURL", "http://example.com")

        edited = """
ServerConfig:
  Srv_Port: 40000
  Srv_Name: Vollingers Test Server
  Srv_Description: Running on a ramdisk managed by ESM. There's nothing to see here, please move on.
  Srv_MaxPlayers: 8
  Srv_ReservePlayfields: 1
  Srv_Public: false
  EACActive: false
  AdminConfigFile: adminconfig.yaml
  SaveDirectory: Saves
  MaxAllowedSizeClass: 21
  AllowedBlueprints: All
  HeartbeatServer: 15
  TimeoutBootingPfServer: 90
  PlayerLoginParallelCount: 5
  #PlayerLoginVipNames: 76561198086927352,123456789
  PlayerLoginFullServerQueueCount: 10
GameConfig:
  GameName: EsmTestDediGame
  Mode: Survival
  Seed: 42069420
  CustomScenario: TestProjectA
  SharedDataURL: http://example.com
"""
        with open(tempYamlPath, "r") as f:
            actual = f.read()
            self.assertEqual(edited.strip(), actual.strip())

        cs.removeMatchingYamlProperty(tempYamlPath, "GameConfig.SharedDataURL")

        with open(tempYamlPath, "r") as f:
            actual = f.read()
            self.assertEqual(original.strip(), actual.strip())

        tempYamlPath.unlink()
