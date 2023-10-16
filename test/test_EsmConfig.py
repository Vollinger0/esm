import logging
from pathlib import Path
import unittest
from esm.EsmConfig import EsmConfig

log = logging.getLogger(__name__)

class test_EsmConfig(unittest.TestCase):

    def test_accessibleConfig(self):
        configFile = Path("./test/test.yaml").absolute()
        config = EsmConfig.fromConfigFile(configFile)
        log.debug(f"config: {config}")
        log.debug(f"config.database: {config.database}")
        log.debug(f"config.database.host: {config.database.host}")
        log.debug(f"config.app: {config.app}")
        log.debug(f"config.app.name: {config.app.name}")
        self.assertEqual(config.database.host, "localhost")
        self.assertEqual(config.app.name, "My App")
        self.assertEqual(config.app.sub_config.value1, "abc")
        self.assertEqual(config.numbers.integers, [1,2,3])
