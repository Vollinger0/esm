from functools import cached_property
import logging
from math import sqrt
from pathlib import Path
from typing import List
from esm import WrongParameterError
from esm.DataTypes import Playfield, SolarSystem, Territory, WipeType
from esm.EsmConfigService import EsmConfigService
from esm.EsmDatabaseWrapper import EsmDatabaseWrapper
from esm.EsmFileSystem import EsmFileSystem
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import Timer

log = logging.getLogger(__name__)

@Service
class EsmWipeService:
    """
    Service class that provides some functionality to wipe playfields

    optimized for huge savegames, just when you need to wipe a whole galaxy without affecting players.
    """
    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)

    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)

    def wipeEmptyPlayfields(self, dbLocation, territoryString, wipeType: WipeType, nodrymode):
        """
        wipe given territory with given wipetype and mode using the given db
        """
        database = EsmDatabaseWrapper(dbLocation)
        with Timer() as timer:
            allSolarSystems = database.retrieveAllSolarSystems()
            if territoryString == Territory.GALAXY:
                territory = Territory(Territory.GALAXY,0,0,0,0)
                solarSystems = allSolarSystems
            else:
                territory = self.getCustomTerritoryByName(territoryString)
                solarSystems = self.getSolarSystemsInCustomTerritory(allSolarSystems, territory)
            log.info(f"The amount of stars is: {len(solarSystems)}")
            emptyPlayfields = database.retrieveEmptyPlayfields(solarSystems)
            log.info(f"The amount of empty but discovered playfields that can be wiped is: {len(emptyPlayfields)}")
            database.closeDbConnection()
        log.info(f"Connection to database closed. Time elapsed reading from the database: {timer.elapsedTime}")

        if len(emptyPlayfields) < 1:
            log.warn(f"There is nothing to wipe!")
            return

        if nodrymode:
            self.wipePlayfields(emptyPlayfields, wipeType)
        else:
            self.printoutPlayfields(territoryString, emptyPlayfields, wipeType)
        
    def wipePlayfields(self, playfields: List[Playfield], wipeType: WipeType):
        """
        actually wipe the given playfields with the wipeType.
        """
        playfieldsFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.playfields")
        log.info(f"Starting wipe for {len(playfields)} playfields with wipe type '{wipeType}' in folder '{playfieldsFolderPath}'")
        with Timer() as timer:
            counter=0
            for playfield in playfields:
                log.debug(f"wiping playfield: {playfield.name}")
                playfieldPath = playfieldsFolderPath.joinpath(playfield.name)
                self.createWipeInfo(playfieldPath, wipeType)
                counter+=1
                if counter % 1000 == 0:
                    log.info(f"processed {counter} playfields")
        log.info(f"Done with wiping {len(playfields)} PFs in {timer.elapsedTime}! Playfields are wiped when loaded, so to actually see if something has been wiped, you have to visit a playfield.")

    def printoutPlayfields(self, territory, playfields: List[Playfield], wipeType: WipeType):
        """
        creates a csv with the playfields that would have been wiped, to verify the results if needed, or whatever.        
        """
        csvFilename = Path(f"esm-wipe_{territory}_{wipeType}.csv").absolute()
        log.info(f"Will output the list of playfields that would have been wiped as '{csvFilename}'")
        self.printListOfPlayfieldsAsCSV(csvFilename=csvFilename, playfields=playfields)

    def getAvailableTerritories(self) -> List[Territory]:
        """
        return the list of available territories from config
        """
        territories = []
        for territory in self.config.galaxy.territories:
            territories.append(Territory(territory["faction"].capitalize(), territory["center-x"], territory["center-y"], territory["center-z"], territory["radius"]))
        return territories        

    def getCustomTerritoryByName(self, territoryName):
        for ct in self.getAvailableTerritories():
            if ct.name == territoryName:
                return ct

    def createWipeInfo(self, path: Path, wipeType: WipeType):
        if path.exists():
            filePath = path.joinpath("/wipeinfo.txt")
            if filePath.exists():
                log.debug(f"File '{str(filePath)}' already exists in the directory - will overwrite old info")
            filePath.write_text(wipeType.value.val)
        else:
            log.debug(f"playfield path {path} doesn't exist! If the playfield doesn't exist on the filesystem, there's no need to wipe it, since its bugged anyways.")

    def getSolarSystemsInCustomTerritory(self, solarsystems: List[SolarSystem], customTerritory: Territory):
        log.debug(f"filtering solarsystems for custom territory: {customTerritory.name}")
        customTerritorySolarSystems = []
        for solarsystem in solarsystems:
            if self.isInCustomTerritory(solarsystem, customTerritory):
                customTerritorySolarSystems.append(solarsystem)
        log.debug(f"solarsystems in custom territory: {len(customTerritorySolarSystems)}")
        return customTerritorySolarSystems
    
    def isInCustomTerritory(self, solarsystem: SolarSystem, customTerritory: Territory):
        # calculate distance of given star to center of the custom territory. if its bigger than its radiuis, we assume its outside.
        distance = sqrt(((solarsystem.x - customTerritory.x)**2) + ((solarsystem.y - customTerritory.y)**2) + ((solarsystem.z - customTerritory.z)**2))
        return (distance <= customTerritory.radius)

    def clearDiscoveredByInfoForSolarSystems(self, solarsystems: List[SolarSystem], nodrymode, database=None, dbLocation=None):
        """
        clears the discoveredbyInfo for the solarsystems, by resolving the list of playfields first.
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        # get the list of playfields for the solarsystems
        playfields = database.retrieveDiscoveredPlayfieldsForSolarSystems(solarsystems);
        return self.clearDiscoveredByInfoForPlayfields(playfields, nodrymode, database=database)
        
    def clearDiscoveredByInfoForPlayfields(self, playfields: List[Playfield], nodrymode, database=None, dbLocation=None):
        """
        clears the discoveredbyInfo for the given playfields
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        if nodrymode:
            log.debug("will delete given playfields from the discovered playfields table")
            database.deleteFromDiscoveredPlayfields(playfields=playfields)
            database.closeDbConnection()
        else:
            csvFilename = Path(f"esm-cleardiscoveredby.csv").absolute()
            log.info(f"Will output the list of playfields whose discoverd by info would have been cleared '{csvFilename}'")
            self.printListOfPlayfieldsAsCSV(csvFilename=csvFilename, playfields=playfields)
    
    def printListOfPlayfieldsAsCSV(self, csvFilename, playfields):
        """
        creates a csv with the given playfields that would have been altered, to verify the results if needed, or whatever.
        """
        with open(csvFilename, 'w') as file:
            file.write("playfield_id,playfield_name,system_id,system_name\n")
            for playfield in playfields:
                file.write(f"{playfield.pfid},{playfield.name},{playfield.ssid},{playfield.starName}\n")
        log.info("CSV file written. Nothing was changed in the current savegame. Please remember that this list gets instantly outdated once players play the game.")
