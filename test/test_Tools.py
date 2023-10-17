import logging
import unittest

from esm import Tools

log = logging.getLogger(__name__)

class test_Tools(unittest.TestCase):

    def test_extractNames(self):
        names = ["SomePlayfield", "Another playfield", "Kal El-Wtf", "S:Uiii", "S:Oh la la"]
        systemNames, playfieldNames = Tools.extractSystemAndPlayfieldNames(names)

        expectedPfs = ["SomePlayfield", "Another playfield", "Kal El-Wtf"]
        expectedSSs = ["Uiii", "Oh la la"]

        self.assertListEqual(sorted(expectedSSs), sorted(systemNames))
        self.assertListEqual(sorted(expectedPfs), sorted(playfieldNames))
