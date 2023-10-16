from functools import cached_property
import logging
from pathlib import Path
import sqlite3
from typing import List
from esm.DataTypes import Playfield, SolarSystem
from esm.EsmConfigService import EsmConfigService
from esm.ServiceRegistry import Service, ServiceRegistry

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
    
    def getGameDbConnection(self) -> sqlite3.Connection:
        if not self.dbConnection:
            log.debug(f"Opening game database at {self.gameDbPath}")
            dbConnectString = self.getGameDbString()
            log.debug(f"using database connect string {dbConnectString}")
            self.dbConnection = sqlite3.connect(dbConnectString, uri=True)
        return self.dbConnection

    def closeDbConnection(self):
        if self.dbConnection:
            log.debug("closing db connection")
            self.dbConnection.close()
            self.dbConnection = None

    def getGameDbCursor(self):
        if not self.gameDbCursor:
            connection = self.getGameDbConnection()
            self.gameDbCursor = connection.cursor()
        return self.gameDbCursor

    def retrieveDiscoveredPlayfields(self, solarsystems: List[SolarSystem]) -> List[Playfield]:
        log.debug("getting discovered playfields")
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
        discoveredPlayfields = self.retrieveDiscoveredPlayfields(solarsystems)
        nonEmptyPlayfields = self.retrieveAllNonEmptyPlayfields()

        log.debug("filtering out non empty playfields from all discovered playfields")
        emptyPlayfields = [playfield for playfield in discoveredPlayfields if playfield not in nonEmptyPlayfields]
        log.debug(f"wipeable empty playfields: {len(emptyPlayfields)}")
        return emptyPlayfields
