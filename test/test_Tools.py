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

    def test_listunion(self):
        list1 = ["a", "b", "c", "p", "q"]
        list2 = ["x", "y", "z", "p", "q"]

        result = list(set(list1).union(set(list2)))
        self.assertListEqual(sorted(result), sorted(["a", "b", "c", "p", "q", "x", "y", "z"]))

        result = list(set(list1).intersection(set(list2)))
        self.assertListEqual(sorted(result), sorted(["p", "q"]))

        result = list(set(list1) - set(list2))
        self.assertListEqual(sorted(result), sorted(["a", "b", "c"]))
