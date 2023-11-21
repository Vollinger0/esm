
import logging
from pathlib import Path
import unittest

from esm.EsmCommunicationService import EsmCommunicationService
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import ServiceRegistry

log = logging.getLogger(__name__)

class test_EsmCommunicationService(unittest.TestCase):

    def test_getServiceFromRegistry(self):
        cs = ServiceRegistry.get(EsmCommunicationService)
        self.assertIsNotNone(cs)

    def test_getSyncChatLines(self):
        cs = EsmCommunicationService()
        lines = cs.getSyncChatLines()
        self.assertEqual(len(lines), 64)

    def test_getRandomSyncChatLine(self):
        cs = EsmCommunicationService()
        start, end = cs.getRandomSyncChatLine()
        log.debug(f"start: {start}")
        log.debug(f"end: {end}")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)

    def test_shallAnnounceSyncIsTrueOnTestConfig(self):
        config = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"))
        cs = EsmCommunicationService()

        result = cs.shallAnnounceSync()
        self.assertTrue(result)

    def test_shallAnnounceSyncIsTrue(self):
        config = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"))
        config.communication.announceSyncEvents = True
        config.communication.announceSyncProbability = 1.0
        cs = EsmCommunicationService()
        result = cs.shallAnnounceSync()
        self.assertTrue(result)

    def test_shallAnnounceSyncIsFalse(self):
        config = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"))
        config.communication.announceSyncEvents = False
        config.communication.announceSyncProbability = 1.0
        cs = EsmCommunicationService()
        result = cs.shallAnnounceSync()
        self.assertFalse(result)

    def test_shallAnnounceSyncIsRandom(self):
        config = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"))
        config.communication.announceSyncEvents = True
        config.communication.announceSyncProbability = 0.3
        cs = EsmCommunicationService()

        count = 0
        for i in range(10000):
            if cs.shallAnnounceSync():
                count +=1
        self.assertTrue(count > 1)
        self.assertTrue(count < 10000)
        log.debug(f"count was: {count}")

    def test_syncStartAndEndMatch(self):
        config = EsmConfigService.fromCustomConfigFile(Path("test/esm-test-config.yaml"))
        cs = EsmCommunicationService()
        cs.syncChatLines = [("start1", "end1"), ("start2", "end2"), ("start3", "end3")]
        (start, end) = cs.getRandomSyncChatLine()
        log.debug(f"start: {start}, end: {end} - {start[-1:]}")
        self.assertEqual(start[-1:], end[-1:])
