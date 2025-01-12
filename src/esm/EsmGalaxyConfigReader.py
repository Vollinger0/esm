from functools import cached_property
import logging
from pathlib import Path
from typing import List
from esm.ConfigModels import MainConfig
from esm.DataTypes import Territory
from esm.ecf.galaxyconfig import GalaxyConfig

log = logging.getLogger(__name__)

class EsmGalaxyConfigReader:
    """
        class that reads the galaxy configuration and provides the parsed data
    """
    @cached_property
    def galaxyConfig(self) -> GalaxyConfig:
        return self.getGalaxyConfig()

    def __init__(self, config: MainConfig) -> None:
        self.scenarioName = config.dedicatedConfig.GameConfig.CustomScenario
        self.pathToScenario = Path(f"{config.paths.install}/Content/Scenarios/{self.scenarioName}/Content/Configuration").resolve()

    def getGalaxyConfig(self):
        return GalaxyConfig(pathToScenario=self.pathToScenario)

    def retrieveTerritories(self) -> List[Territory]:
        """
            returns a list of all the territories in the galaxy config file
        """
        territories = []
        ecfTerritories = self.galaxyConfig.getTerritories()
        for id, faction, center, radius in ecfTerritories:
            #log.debug(f"Block: {id}, Faction: {faction} Center: {center}, Radius: {radius}")
            name = f"{id}_{faction}"
            if center and radius:
                territories.append(Territory(name, center[0], center[1], center[2], radius))
        return territories
