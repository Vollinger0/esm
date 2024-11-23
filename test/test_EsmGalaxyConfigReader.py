import logging
import unittest

from esm.EsmGalaxyConfigReader import EsmGalaxyConfigReader

log = logging.getLogger(__name__)

class test_EsmGalaxyConfigReader(unittest.TestCase):

    def test_reader_reads(self):
        reader = EsmGalaxyConfigReader("./test/test_GalaxyConfig.ecf")
        self.assertIsNotNone(reader)
