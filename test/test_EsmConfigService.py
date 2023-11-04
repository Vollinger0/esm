import logging
from pathlib import Path
import unittest
from esm.EsmConfigService import EsmConfigService
from esm.Exceptions import AdminRequiredException
from esm.ServiceRegistry import ServiceRegistry

log = logging.getLogger(__name__)

class test_EsmConfigService(unittest.TestCase):

    def test_accessibleConfig(self):
        configFile = Path("./test/test.yaml").absolute()
        config = EsmConfigService(configFilePath=configFile, raiseExceptionOnMissingDedicated=False)
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
        self.assertEqual(config.ramdisk.drive, "T:")

    def test_loadFromRegistry(self):
        instance = EsmConfigService(configFilePath="test/esm-test-config.yaml")
        ServiceRegistry.register(instance)
        config = ServiceRegistry.get(EsmConfigService)
        self.assertEqual(config.backups.amount, 4)
        self.assertEqual(config.ramdisk.drive, "T:")

    def test_containsContext(self):
        configFilePath="test/esm-test-config.yaml"
        config = EsmConfigService(configFilePath=configFilePath)
        self.assertEqual(config.context.configFilePath, configFilePath)
        self.assertEqual(config.backups.amount, 4)
        self.assertEqual(config.ramdisk.drive, "T:")

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
        self.assertEqual(config.ramdisk.drive, "T:")

    def test_loadingCustomConfig(self):
        configFile = Path("./test/test.yaml").absolute()
        config = EsmConfigService(configFilePath=configFile, raiseExceptionOnMissingDedicated=False)
        self.assertEqual(config.app.name, "My App")
        self.assertIsNone(config.onlyInCustom)
        self.assertEqual(config.onlyInBase, "bar")
        self.assertListEqual(config.overwrite.this.nested, ["value1", "value2", "value3"])
        self.assertEqual(config.context.configFilePath, configFile)
        with self.assertRaises(KeyError):
            self.assertIsNone(config.context.customConfigFilePath, configFile)

        # now with custom config overwriting the base config
        newConfigFile = Path("./test/test.yaml").absolute()
        newCustomFile = Path("./test/custom.yaml").absolute()
        newConfig = EsmConfigService(configFilePath=newConfigFile, customConfigFilePath=newCustomFile, raiseExceptionOnMissingDedicated=False)
        self.assertEqual(newConfig.app.name, "My Custom App Config")
        self.assertEqual(newConfig.onlyInCustom, "foo")
        self.assertEqual(newConfig.onlyInBase, "bar")
        self.assertListEqual(newConfig.overwrite.this.nested, ["newvalue2"])

        self.assertEqual(newConfig.context.configFilePath, configFile)
        self.assertEqual(newConfig.context.customConfigFilePath, newCustomFile)

        self.assertEqual(newConfig.app.sub_config.value1, "abc")
        self.assertEqual(newConfig.numbers.integers, [1,2,3])

    def test_loadingRealConfig(self):
        config = EsmConfigService(configFilePath="esm-base-config.yaml", customConfigFilePath="esm-custom-config.yaml")
        self.assertEqual(config.dedicatedYaml.GameConfig.GameName, "EsmDediGame")
        self.assertEqual(config.server.minDiskSpaceForStartup, "500M")

    def test_loadingConfigReadsDedicatedYaml(self):
        configFilePath="test/esm-test-config.yaml"
        config = EsmConfigService(configFilePath=configFilePath)
        
        with self.assertRaises(KeyError):
            self.assertIsNone(config.server.savegame)
        with self.assertRaises(KeyError):            
            self.assertIsNone(config.foldernames.saves)
        
        self.assertEqual(config.dedicatedYaml.GameConfig.GameName, "EsmDediGame")
        self.assertEqual(config.dedicatedYaml.ServerConfig.AdminConfigFile, "adminconfig.yaml")
        self.assertEqual(config.dedicatedYaml.ServerConfig.SaveDirectory, "Saves")

    def test_loadingConfigReadsDedicatedYamlBreaksWhenNotAvailable(self):
        configFilePath="test/esm-test-broken-config.yaml"
        
        with self.assertRaises(AdminRequiredException):
            config = EsmConfigService(configFilePath=configFilePath, raiseExceptionOnMissingDedicated=True)
