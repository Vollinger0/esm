import logging
from pathlib import Path
import unittest
from unittest.mock import patch

from pydantic import ValidationError
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
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
