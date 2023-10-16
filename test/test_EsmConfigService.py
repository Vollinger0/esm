import logging
from pathlib import Path
import unittest
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import ServiceRegistry

log = logging.getLogger(__name__)

class test_EsmConfigService(unittest.TestCase):

    def test_accessibleConfig(self):
        configFile = Path("./test/test.yaml").absolute()
        config = EsmConfigService(configFilePath=configFile)
        log.debug(f"config: {config}")
        log.debug(f"config.database: {config.database}")
        log.debug(f"config.database.host: {config.database.host}")
        log.debug(f"config.app: {config.app}")
        log.debug(f"config.app.name: {config.app.name}")
        self.assertEqual(config.database.host, "localhost")
        self.assertEqual(config.app.name, "My App")
        self.assertEqual(config.app.sub_config.value1, "abc")
        self.assertEqual(config.numbers.integers, [1,2,3])

    def test_loadsCustomPath(self):
        config = EsmConfigService(configFilePath="test/esm-test-config.yaml")
        self.assertEqual(config.backups.amount, 4)
        self.assertEqual(config.ramdisk.drive, "T")

    def test_loadFromRegistry(self):
        instance = EsmConfigService(configFilePath="test/esm-test-config.yaml")
        ServiceRegistry.register(instance)
        config = ServiceRegistry.get(EsmConfigService)
        self.assertEqual(config.backups.amount, 4)
        self.assertEqual(config.ramdisk.drive, "T")

    def test_containsContext(self):
        configFilePath="test/esm-test-config.yaml"
        config = EsmConfigService(configFilePath=configFilePath)
        self.assertEqual(config.context.configFilePath, configFilePath)
        self.assertEqual(config.backups.amount, 4)
        self.assertEqual(config.ramdisk.drive, "T")

    def test_containsMoreContext(self):
        configFilePath="test/esm-test-config.yaml"
        context = {
            'foo': 'bar',
            'baz': 42
        }
        config = EsmConfigService(configFilePath=configFilePath, context=context)
        self.assertEqual(config.context.configFilePath, configFilePath)
        self.assertEqual(config.context.foo, "bar")
        self.assertEqual(config.context.baz, 42)
        self.assertEqual(config.backups.amount, 4)
        self.assertEqual(config.ramdisk.drive, "T")