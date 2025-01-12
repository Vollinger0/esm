
import logging
import time
import unittest

from esm.EsmGameChatService import EsmGameChatService
from esm.EsmLogger import EsmLogger
from esm.ServiceRegistry import ServiceRegistry

EsmLogger.setUpLogging(streamLogLevel=logging.DEBUG)
log = logging.getLogger(__name__)

class test_EsmGameChatService(unittest.TestCase):

    def test_getServiceFromRegistry(self):
        cs = ServiceRegistry.get(EsmGameChatService)
        self.assertIsNotNone(cs)

    def test_StartsUp(self):
        cs = ServiceRegistry.get(EsmGameChatService)
        cs.initialize()
        # if egs is not running, this will probably cause an error (since emprc will not be able to connect), but the test will still succeed, thats fine for this test
        response = cs.getMessage(timeout=1)
        self.assertIsNone(response)
        cs.shutdown()
