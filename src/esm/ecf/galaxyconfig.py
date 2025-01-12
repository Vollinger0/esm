from pathlib import Path
from typing import List, Tuple
from esm.ecf.parser import EcfBlock, EcfChildBlock, EcfFile, EcfParser
import logging

log = logging.getLogger(__name__)

class GalaxyConfig:
    """
        simple wrapper for the galaxy config for convenience
    """
    def __init__(self, pathToScenario: Path, filename: str = "GalaxyConfig.ecf"):
        self._pathToFile: Path = Path(pathToScenario).joinpath(filename)
        self._ecfFile: EcfFile = EcfParser.readFromFile(self._pathToFile)
    
    def getTerritories(self) -> List[Tuple[str, str, Tuple[float, float, float], int]]:
        """
            Returns a list of tuples (id, faction, center, radius)
        """
        block: EcfBlock = self.findBlockByType("GalaxyConfig")
        childBlocks = self.findChildBlocksById(block.children, "Territory_")
        territories = []
        for childBlock in childBlocks:
            id = childBlock.id
            faction = self.findProperty(childBlock, "Faction")

            centerString = self.findProperty(childBlock, "Center")
            center = (float(centerString.split(",")[0]), float(centerString.split(",")[1]), float(centerString.split(",")[2])) if centerString else None
            radiusString = self.findProperty(childBlock, "Radius")
            radius = int(radiusString) if radiusString else None

            territories.append((id, faction, center, radius))
        return territories

    def findProperty(self, block: EcfChildBlock, key):
        for property in block.properties:
            if property.key == key:
                return getattr(property, "value", None)

    def findChildBlocksById(self, blocks: List[EcfChildBlock], id) -> List[EcfChildBlock]:
        found = []
        for block in blocks:
            if block.id.startswith(id):
                found.append(block)
        return found        

    def findBlockByType(self, type: str) -> EcfBlock:
        for block in self._ecfFile.blocks:
            if block.type == type:
                return block
