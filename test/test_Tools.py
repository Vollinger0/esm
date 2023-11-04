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

    def test_byteArrayToString(self):
        input = b'asdfadfasdf aadf adsf adf s'
        expected = "asdfadfasdf aadf adsf adf s"
        actual = Tools.byteArrayToString(input)
        self.assertEqual(expected, actual)

        input = b'  \t  asdfadfasdf aadf adsf adf s   \n'
        expected = "asdfadfasdf aadf adsf adf s"
        actual = Tools.byteArrayToString(input).strip()
        self.assertEqual(expected, actual)