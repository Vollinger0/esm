
import logging
from pathlib import Path
import unittest
from esm.EsmConfigService import EsmConfigService

from esm.EsmMain import EsmMain
from esm.ServiceRegistry import ServiceRegistry
from esm.Tools import Timer
from esm.exceptions import AdminRequiredException

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

    def test_EsmMain_binding_to_port_blocks(self):
        esm = EsmMain(caller="bar", waitForPort=False, customConfigFilePath=Path("esm-custom-config.yaml"))
        esm.openSocket(raiseException=True)
        self.assertIsNotNone(esm)

        esm2 = EsmMain(caller="bar", waitForPort=False, customConfigFilePath=Path("esm-custom-config.yaml"))
        with self.assertRaises(AdminRequiredException):
            esm2.openSocket(raiseException=True)
            self.assertIsNotNone(esm2)

    def test_EsmMain_binding_to_port_waiting_works(self):
        esm = EsmMain(caller="bar", waitForPort=False, customConfigFilePath=Path("esm-custom-config.yaml"))
        esm.openSocket(raiseException=True)
        self.assertIsNotNone(esm)

        esm2 = EsmMain(caller="bar", waitForPort=True, customConfigFilePath=Path("esm-custom-config.yaml"))
        with Timer() as timer:
            with self.assertRaises(AdminRequiredException):
                esm2.openSocket(raiseException=True, interval=1, tries=2)
        log.debug(f"elapsed time: {timer.elapsedTime}")
        # with 2 retries and an interval of 1, the exception should take at least 2 seconds to happen, which is not the case if the retries wouldn't work.
        self.assertGreaterEqual(timer.elapsedTime.seconds, 2)
