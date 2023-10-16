import unittest
import os
import logging
from esm.EsmConfig import EsmConfig

class test_EsmConfig(unittest.TestCase):

    log = logging.getLogger(__name__)

    def test_accessibleConfig(self):
        configFile = os.path.abspath("./test/test.yaml")
        config = EsmConfig(configFile)
        self.log.debug(f"read config: {config}")
        print(f"read config: {config}")

        # database_host = config.database.host
        # app_name = config.app.name
        # debug_mode = config.app.debug

        # print(f"Database Host: {database_host}")
        # print(f"App Name: {app_name}")
        # print(f"Debug Mode: {debug_mode}")

        # self.assertEquals(config.database.host, "localhost")
