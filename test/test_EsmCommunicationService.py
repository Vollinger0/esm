
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
        # since cs may have been instantiated before, it might still point to the old config, overwrite it
        cs.config = esmConfig

        lines = cs.getSyncChatLines()
        self.assertEqual(len(lines), 64)


    def test_getRandomSyncChatLine(self):
        esmConfig = EsmConfigService(configFilePath='esm-base-config.yaml')
        ServiceRegistry.register(esmConfig)
        cs = ServiceRegistry.get(EsmCommunicationService)
        # since cs may have been instantiated before, it might still point to the old config, overwrite it
        cs.config = esmConfig

        start, end = cs.getRandomSyncChatLine()
        log.debug(f"start: {start}")
        log.debug(f"end: {end}")
        self.assertIsNotNone(start)
        self.assertIsNotNone(end)

    def test_shallAnnounceSyncIsTrueOnTestConfig(self):
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml', raiseExceptionOnMissingDedicated=False)
        ServiceRegistry.register(esmConfig)
        cs = ServiceRegistry.get(EsmCommunicationService)
        # since cs may have been instantiated before, it might still point to the old config, overwrite it
        cs.config = esmConfig

        result = cs.shallAnnounceSync()
        self.assertTrue(result)

    def test_shallAnnounceSyncIsTrue(self):
        override = {
            'communication': {
                'announceSyncEvents': True,
                'announceSyncProbability': 1.0
            }
        }
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml', override=override, raiseExceptionOnMissingDedicated=False)
        ServiceRegistry.register(esmConfig)
        cs = ServiceRegistry.get(EsmCommunicationService)
        # since cs may have been instantiated before, it might still point to the old config, overwrite it
        cs.config = esmConfig
        result = cs.shallAnnounceSync()
        self.assertTrue(result)

    def test_shallAnnounceSyncIsFalse(self):
        override = {
            'communication': {
                'announceSyncEvents': False,
                'announceSyncProbability': 1.0
            }
        }
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml', override=override, raiseExceptionOnMissingDedicated=False)
        ServiceRegistry.register(esmConfig)
        cs = ServiceRegistry.get(EsmCommunicationService)
        # since cs may have been instantiated before, it might still point to the old config, overwrite it
        cs.config = esmConfig
        result = cs.shallAnnounceSync()
        self.assertFalse(result)

    def test_shallAnnounceSyncIsRandom(self):
        override = {
            'communication': {
                'announceSyncEvents': True,
                'announceSyncProbability': 0.3
            }
        }
        esmConfig = EsmConfigService(configFilePath='test/esm-test-config.yaml', override=override, raiseExceptionOnMissingDedicated=False)
        ServiceRegistry.register(esmConfig)
        cs = ServiceRegistry.get(EsmCommunicationService)
        # since cs may have been instantiated before, it might still point to the old config, overwrite it
        cs.config = esmConfig

        count = 0
        for i in range(10000):
            if cs.shallAnnounceSync():
                count +=1
        self.assertTrue(count > 1)
        self.assertTrue(count < 10000)
        log.debug(f"count was: {count}")

    def test_syncStartAndEndMatch(self):
        ServiceRegistry.register(EsmConfigService(configFilePath='test/esm-test-config.yaml', raiseExceptionOnMissingDedicated=False))
        cs = ServiceRegistry.get(EsmCommunicationService)
        cs.syncChatLines = [("start1", "end1"), ("start2", "end2"), ("start3", "end3")]
        (start, end) = cs.getRandomSyncChatLine()
        log.debug(f"start: {start}, end: {end} - {start[-1:]}")
        self.assertEqual(start[-1:], end[-1:])
