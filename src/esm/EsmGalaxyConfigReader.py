
from pathlib import Path
from typing import List
from esm.DataTypes import Territory
from esm.EcfReader import EcfReader
from esm.exceptions import WrongParameterError

class EsmGalaxyConfigReader:
    """
        class that reads the galaxy configuration and provides the parsed date
    """
    def __init__(self, filePath: str):
        self.filePath = Path(filePath)
        if not self.filePath.exists():
            raise WrongParameterError(f"File '{self.filePath}' does not exist, can not read galaxy configuration")

    def retrieveTerritories(self) -> List[Territory]:
        """
            returns a list of all the territories in the galaxy config file
        """
        territories = []
        ecfReader = EcfReader(self.filePath)
        return territories
    
   