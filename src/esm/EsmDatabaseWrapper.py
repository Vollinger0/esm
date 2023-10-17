from functools import cached_property
import logging
from pathlib import Path
import sqlite3
from typing import List
from esm.DataTypes import Playfield, SolarSystem
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import ServiceRegistry

log = logging.getLogger(__name__)

class EsmDatabaseWrapper:

    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)
    
    def __init__(self, gameDbPath: None) -> None:
        self.gameDbPath = None
        self.dbConnectString = None
        self.dbConnection = None
        self.gameDbCursor = None
        self.setGameDbPath(gameDbPath)
    
    def setGameDbPath(self, gameDbPath: Path):
        self.gameDbPath = Path(gameDbPath)

    def getGameDbPath(self) -> Path:
        if self.gameDbPath is None:
            raise FileNotFoundError("no game db path was set to connect to. call #setGameDbPath() first.")
        return self.gameDbPath
    
    def getGameDbString(self, mode="ro"):
        if not self.dbConnectString:
            self.dbConnectString = f"file:/{self.getGameDbPath().as_posix()}?mode={mode}"
        return self.dbConnectString
    
    def getGameDbConnection(self, mode="ro") -> sqlite3.Connection:
        if not self.dbConnection:
            log.debug(f"Opening game database at {self.gameDbPath}")
            dbConnectString = self.getGameDbString(mode)
            log.debug(f"using database connect string {dbConnectString}")
            self.dbConnection = sqlite3.connect(dbConnectString, uri=True)
        return self.dbConnection

    def closeDbConnection(self):
        if self.dbConnection:
            log.debug("closing db connection")
            self.dbConnection.close()
            self.dbConnection = None

    def getGameDbCursor(self, mode="ro"):
        if not self.gameDbCursor:
            connection = self.getGameDbConnection(mode)
            self.gameDbCursor = connection.cursor()
        return self.gameDbCursor

    def retrieveDiscoveredPlayfieldsForSolarSystems(self, solarsystems: List[SolarSystem]) -> List[Playfield]:
        """return all playfields that are discovered and belong to the list of given solar systems"""
        log.debug(f"getting discovered playfields for given {len(solarsystems)} solarsystems")
        ssids = []
        for solarsystem in solarsystems:
            ssids.append(solarsystem.ssid)
        discoveredPlayfields = []
        for row in self.getGameDbCursor().execute("SELECT DISTINCT DiscoveredPlayfields.pfid, pfs.name, pfs.ssid, ss.name FROM DiscoveredPlayfields LEFT JOIN Playfields as pfs ON pfs.pfid = DiscoveredPlayfields.pfid LEFT JOIN SolarSystems as ss ON ss.ssid = pfs.ssid ORDER BY pfs.name;"):
            ssid=row[2]
            if ssid in ssids:
                discoveredPlayfields.append(
                    Playfield(ssid=ssid, 
                                pfid=row[0], 
                                starName=row[3], 
                                name=row[1]))
        log.debug(f"discovered playfields for the given solarsystems: {len(discoveredPlayfields)}")
        return discoveredPlayfields

    def retrieveAllSolarSystems(self) -> List[SolarSystem]:
        """returns all solar systems"""
        solarsystems = []
        log.debug("loading solar systems")
        for row in self.getGameDbCursor().execute("SELECT name, sectorx, sectory, sectorz, ssid FROM SolarSystems ORDER BY name"):
            solarsystems.append(SolarSystem(name=row[0], x=row[1], y=row[2], z=row[3], ssid=row[4]))
        log.debug(f"solar systems loaded: {len(solarsystems)}")
        return solarsystems

    def retrievePFsWithPlayerStructures(self) -> List[Playfield]:
        log.debug("finding playfields with player structures")
        pfsWithStructures = []
        for row in self.getGameDbCursor().execute("SELECT pfid, name FROM playfields WHERE pfid IN (SELECT e.pfid FROM Entities e INNER JOIN Structures s ON e.entityid = s.entityid WHERE (ispoi = 0) and (facid > 0) OR ((ispoi = 1) AND (etype = 3) AND (facid > 0) AND (bpname NOT LIKE '%OPV%')) OR ((ispoi = 1) AND (etype != 3) AND (facid > 0))) ORDER BY name;"):
            pfsWithStructures.append(Playfield(pfid=row[0], name=row[1]))
        log.debug(f"playfields with player structures: {len(pfsWithStructures)}")
        return pfsWithStructures

    def retrievePFsWithPlaceables(self) -> List[Playfield]:
        log.debug("finding playfields with terrain placeables")
        pfsWithPlaceables = []
        for row in self.getGameDbCursor().execute("SELECT distinct playfields.pfid, playfields.name from TerrainPlaceables LEFT JOIN playfields ON TerrainPlaceables.pfid = playfields.pfid;"):
            pfsWithPlaceables.append(Playfield(pfid=row[0], name=row[1]))
        log.debug(f"playfields with terrain placeables: {len(pfsWithPlaceables)}")
        return pfsWithPlaceables

    def retrievePFsWithPlayers(self) -> List[Playfield]:
        log.debug("finding playfields with players on them")
        pfsWithPlayers = []
        for row in self.getGameDbCursor().execute("select playfields.pfid, playfields.name from Entities LEFT JOIN playfields ON Entities.pfid = playfields.pfid WHERE Entities.etype = 1;"):
            pfsWithPlayers.append(Playfield(pfid=row[0], name=row[1]))
        log.debug(f"playfields with players on them: {len(pfsWithPlayers)}")
        return pfsWithPlayers

    def retrieveAllNonEmptyPlayfields(self) -> List[Playfield]:
        """this will get *all* non empty playfields from the db, there's no need to filter out before since this is almost instant anyways."""
        pfsWithPlayerStructures = self.retrievePFsWithPlayerStructures()
        pfsWithPlaceables = self.retrievePFsWithPlaceables()
        pfsWithPlayers = self.retrievePFsWithPlayers()

        log.debug("merging all lists, removing duplicates")
        nonEmptyPlayfields = list(set(pfsWithPlayerStructures) | set(pfsWithPlaceables) |set(pfsWithPlayers))
        log.debug(f"total amount of non empty playfields: {len(nonEmptyPlayfields)}")
        return nonEmptyPlayfields

    def retrieveEmptyPlayfields(self, solarsystems) -> List[Playfield]:
        """this will get the empty playfields contained in the array of solarsystems"""
        discoveredPlayfields = self.retrieveDiscoveredPlayfieldsForSolarSystems(solarsystems)
        nonEmptyPlayfields = self.retrieveAllNonEmptyPlayfields()

        log.debug("filtering out non empty playfields from all discovered playfields")
        emptyPlayfields = [playfield for playfield in discoveredPlayfields if playfield not in nonEmptyPlayfields]
        log.debug(f"wipeable empty playfields: {len(emptyPlayfields)}")
        return emptyPlayfields
    
    def deleteFromDiscoveredPlayfields(self, playfields: List[Playfield], batchSize = 1000):
        """ 
        this will delete the rows from DiscoveredPlayfields for all playfields given
        will do the deletion statements in batches
        """
        pfIds = list(map(lambda obj: obj.pfid, playfields))
        log.debug(f"deleting {len(pfIds)} pfids from DiscoveredPlayfields")
        cursor = self.getGameDbCursor()

        # do the deletions in batches, to avoid memory usage and performance issues.
        for i in range(0, len(pfIds), batchSize):
            pfIdBatch = pfIds[i:i+batchSize]        
            query = "DELETE FROM DiscoveredPlayfields WHERE pfid IN ({})".format(','.join(['?'] * len(pfIdBatch)))
            cursor.execute(query, pfIdBatch)

        connection = self.getGameDbConnection()
        connection.commit()
        log.debug(f"deleted {cursor.rowcount} entries from DiscoveredPlayfields")


    def retrieveSolarsystemsByName(self, solarsystemNames: List[str]) -> List[SolarSystem]:
        """return a list of solar systems which match the given names"""
        # SELECT ssid, name, startype, sectorx, sectory, sectorz FROM SolarSystems WHERE name IN ("Alpha", "Beta")
        log.debug(f"selecting solarsystems matching {len(solarsystemNames)} names")
        cursor = self.getGameDbCursor()
        query = "SELECT ssid, name, startype, sectorx, sectory, sectorz FROM SolarSystems WHERE name IN ({})".format(','.join(['?'] * len(solarsystemNames)))
        solarsystems = []
        for row in cursor.execute(query, solarsystemNames):
            solarsystems.append(SolarSystem(ssid=row[0], name=row[1], x=row[3], y=row[4], z=row[5]))
        log.debug(f"found {len(solarsystems)} solarsystems")
        return solarsystems
        

    def retrievePlayfieldsByName(self, playfieldNames: List[str]) -> List[Playfield]:
        """return a list of playfields which match the given names"""
        # SELECT pf.pfid, pf.name, ss.ssid, ss.name FROM Playfields as pf LEFT JOIN SolarSystems AS ss ON pf.ssid=ss.ssid WHERE pf.name IN ("Gaia", "Haven", "schalala")
        log.debug(f"selecting playfields matching {len(playfieldNames)} names")
        cursor = self.getGameDbCursor()
        query = "SELECT pf.pfid, pf.name, ss.ssid, ss.name FROM Playfields as pf LEFT JOIN SolarSystems AS ss ON pf.ssid=ss.ssid WHERE pf.name IN ({})".format(','.join(['?'] * len(playfieldNames)))
        playfields = []
        for row in cursor.execute(query, playfieldNames):
            playfields.append(Playfield(pfid=row[0], name=row[1], ssid=row[2], starName=row[3]))
        log.debug(f"found {len(playfields)} playfields")
        return playfields
