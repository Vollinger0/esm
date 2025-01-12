
import logging
import unittest

from esm.EsmLogger import EsmLogger
from esm.EsmSharedDataServer import EsmSharedDataServer
from esm.ServiceRegistry import ServiceRegistry

EsmLogger.setUpLogging(streamLogLevel=logging.DEBUG)
log = logging.getLogger(__name__)

class test_EsmSharedDataServer(unittest.TestCase):

    def test_getServiceFromRegistry(self):
        sds = ServiceRegistry.get(EsmSharedDataServer)
        self.assertIsNotNone(sds)

    @unittest.skip("this needs a ton of fs mocks")
    def test_ensureZipsWorks(self):
        sds = ServiceRegistry.get(EsmSharedDataServer)
        #sds.ensureZipFilesAreUpToDate()