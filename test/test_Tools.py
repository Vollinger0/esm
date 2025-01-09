import logging
import unittest

from esm import Tools
from esm.DataTypes import ZipFile

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

    def test_findZipFileByName(self):
        zip1 = ZipFile(name="foobar_moep.zip")
        zip2 = ZipFile(name="SharedData.zip")
        list = [zip1, zip2]

        result = Tools.findZipFileByName(list, "/SharedData.zip", None)
        self.assertEqual(result, zip2)

        result = Tools.findZipFileByName(list, None, "Shared")
        self.assertEqual(result, zip2)

    def test_sentenceSplitter(self):
        parts = Tools.splitSentence("Hello, how are you? This is a very long sentence that should be split in at least two parts, and the first part should have an ellipsis.")
        self.assertEqual(len(parts), 2)
        self.assertEqual(parts[0], "Hello, how are you? This is a very long sentence that should be split in at least two parts, and...")
        self.assertEqual(parts[1], "the first part should have an ellipsis.")
