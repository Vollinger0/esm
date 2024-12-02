import logging
import unittest
from pathlib import Path

from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.EsmGalaxyConfigReader import EsmGalaxyConfigReader

log = logging.getLogger(__name__)

class test_EsmGalaxyConfigReader(unittest.TestCase):

    def test_galaxyconfig_reads_territories(self):
        config = EsmConfigService.getTestConfig({
            "server": {
                "dedicatedYaml": "esm-dedicated.yaml"
            },
            "paths": {
                "install": "D:\\Servers\\Empyrion"
            }
        })
        config.dedicatedConfig.GameConfig.CustomScenario = "ProjectA"
        self.assertEqual(config.paths.install, Path("D:\Servers\Empyrion"))
        reader = EsmGalaxyConfigReader(config)
        self.assertEqual(Path("D:/Servers/Empyrion/Content/Scenarios/ProjectA/Content/Configuration"), reader.pathToScenario)
        
        territories = reader.retrieveTerritories()
        self.assertIsNotNone(territories)
        self.assertEqual(16, len(territories))
