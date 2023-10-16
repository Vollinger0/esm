
import logging
import unittest

from esm.EsmCommunicationService import EsmCommunicationService
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import ServiceRegistry


log = logging.getLogger(__name__)

class test_EsmCommunicationService(unittest.TestCase):

    def test_getSyncChatLines(self):
        esmConfig = EsmConfigService(configFilePath='esm-base-config.yaml')
        ServiceRegistry.register(esmConfig)
        cs = ServiceRegistry.get(EsmCommunicationService)

        lines = cs.getSyncChatLines()
        self.assertEqual(len(lines), 63)

    def test_getRandomSyncChatLine(self):
        esmConfig = EsmConfigService(configFilePath='esm-base-config.yaml')
        ServiceRegistry.register(esmConfig)
        cs = ServiceRegistry.get(EsmCommunicationService)

        start, end = cs.getRandomSyncChatLine()
        log.debug(f"start: {start}")
        log.debug(f"end: {end}")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)
