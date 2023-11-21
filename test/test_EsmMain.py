
import logging
from pathlib import Path
import unittest
from esm.EsmConfigService import EsmConfigService

from esm.EsmMain import EsmMain
from esm.ServiceRegistry import ServiceRegistry

log = logging.getLogger(__name__)

class test_EsmMain(unittest.TestCase):
    
    def test_EsmMainLoads(self):
        esm = EsmMain()
        self.assertIsNotNone(esm)

    def test_EsmMainLoadsAlsoContext(self):
        EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"), True)
        esm = EsmMain(caller="foo")
        self.assertIsNotNone(esm)
        self.assertEqual(esm.config.context.get("caller"), "foo")
        self.assertEqual(esm.config.context.get("configFilePath"), Path("test/esm-test-config.yaml"))
        self.assertEqual(esm.config.context.get("logFile"), "foo.log")

    def test_EsmMainWithParamOverwritesDefaultConfig(self):
        EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"), True)

        esm = EsmMain(caller="bar", waitForPort=True, customConfigFilePath=Path("esm-custom-config.yaml"))
        self.assertIsNotNone(esm)
        self.assertEqual(esm.config.context.get("caller"), "bar")
        self.assertEqual(esm.config.context.get("logFile"), "bar.log")
        self.assertEqual(esm.config.context.get("waitForPort"), True)
        self.assertEqual(esm.config.context.get("customConfigFilePath"), Path("esm-custom-config.yaml"))
        self.assertEqual(esm.config.server.dedicatedYaml, Path("esm-dedicated.yaml"))
        self.assertEqual(esm.config.dedicatedConfig.GameConfig.GameName, "EsmDediGame")
