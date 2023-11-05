
import logging
import subprocess
import time
import unittest

from esm.EsmCommunicationService import EsmCommunicationService, Priority
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


    @unittest.skip("only for manual execution, since you won't see anything if you aren't looking ingame.")
    def test_serverChatAndAnnouncements(self):
        esmConfig = EsmConfigService(configFilePath='esm-base-config.yaml')
        ServiceRegistry.register(esmConfig)
        cs = ServiceRegistry.get(EsmCommunicationService)
        # no way to assert this, start the game and look at the chat.
        cs.serverChat(message=f"hello from esm, dear watcher of the server chat!", quietMode=False)
        time.sleep(3)
        cs.announce(message="alert from an esm test", priority=Priority.ALERT, quietMode=False)
        time.sleep(3)
        cs.announce(message="warning from an esm test", priority=Priority.WARNING, quietMode=False)
        time.sleep(3)
        cs.announce(message="info from an esm test", priority=Priority.INFO, quietMode=False)
        time.sleep(3)
        cs.announce(message="just some text from an esm test", priority=Priority.OTHER, quietMode=False)

