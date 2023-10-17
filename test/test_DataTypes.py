import logging
import unittest

from esm.DataTypes import WipeType

log = logging.getLogger(__name__)

class test_DataTypes(unittest.TestCase):

    def test_WipeTypes(self):
        expected = ['all', 'poi', 'deposit', 'terrain', 'player']
        actual = WipeType.valueList()
        self.assertListEqual(sorted(actual),sorted(expected))

    def test_WipeTypeValue_accessible(self):
        test = WipeType.ALL

        self.assertTrue(isinstance(test.value.name, str))
        self.assertEqual(test.value.name, "all")
        