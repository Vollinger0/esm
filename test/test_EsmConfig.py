import unittest
import os
import logging
from esm.EsmConfig import EsmConfig

class test_EsmConfig(unittest.TestCase):

    log = logging.getLogger(__name__)

    def test_accessibleConfig(self):
        configFile = os.path.abspath("./test/test.yaml")
        config = EsmConfig.fromConfigFile(configFile)
        print(f"config: {config}")
        print(f"config.database: {config.database}")
        print(f"config.database.host: {config.database.host}")
        print(f"config.app: {config.app}")
        print(f"config.app.name: {config.app.name}")
        self.assertEqual(config.database.host, "localhost")
        self.assertEqual(config.app.name, "My App")
        self.assertEqual(config.app.sub_config.value1, "abc")
        self.assertEqual(config.numbers.integers, [1,2,3])
