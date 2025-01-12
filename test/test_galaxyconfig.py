import logging
import unittest

from esm.ecf.galaxyconfig import GalaxyConfig

logging.basicConfig(level=logging.DEBUG)
log = logging.getLogger(__name__)

class test_galaxyconfig(unittest.TestCase):

    def testReadingGalaxyConfigTerritories(self):
        galaxy = GalaxyConfig("test", filename="test_GalaxyConfig.ecf")
        territories = galaxy.getTerritories()
        for id, faction, center, radius in territories:
            log.info(f"Block: {id}, Faction: {faction} Center: {center}, Radius: {radius}")

        # Child Territory_5
        #  Faction: Pirates
        #  Center: "375, 0, 60"
        #  Radius: 75  # in LY        

        # get specific territory
        territory = [t for t in territories if t[1] == "Pirates"][0]
        self.assertEqual("Territory_5", territory[0])
        self.assertEqual("Pirates", territory[1])
        self.assertEqual((375, 0, 60), territory[2])
        self.assertEqual(75, territory[3])
