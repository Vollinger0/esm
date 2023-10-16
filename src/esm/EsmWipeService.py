from functools import cached_property
import logging
from typing import List
from esm.DataTypes import Territory
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmWipeService:

    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    def wipeEmptyPlayfields(self, dbLocation, territory, wipeType, dryMode):
        """
        wipe given territory with given wipetype and mode using the given db
        """
        raise NotImplementedError()

    def getAvailableTerritories(self) -> List[Territory]:
        """
        return the list of available territories from config
        """
        territories = []
        for territory in self.config.galaxy.territories:
            territories.append(Territory(territory["faction"].capitalize(), territory["center-x"], territory["center-y"], territory["center-z"], territory["radius"]))
        return territories        

