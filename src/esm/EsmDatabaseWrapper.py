from datetime import datetime
from functools import cached_property
import logging
from pathlib import Path
import sqlite3
from typing import List
from esm.DataTypes import Entity, EntityType, Playfield, SolarSystem
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
        log.debug("finding playfields containing player structures")
        pfsWithStructures = []
        for row in self.getGameDbCursor().execute("SELECT pfid, name FROM playfields WHERE pfid IN (SELECT e.pfid FROM Entities e INNER JOIN Structures s ON e.entityid = s.entityid WHERE (ispoi = 0) and (facid > 0) OR ((ispoi = 1) AND (etype = 3) AND (facid > 0) AND (bpname NOT LIKE '%OPV%')) OR ((ispoi = 1) AND (etype != 3) AND (facid > 0))) ORDER BY name;"):
            pfsWithStructures.append(Playfield(pfid=row[0], name=row[1]))
        log.debug(f"playfields containing player structures: {len(pfsWithStructures)}")
        return pfsWithStructures

    def retrievePFsWithPlaceables(self) -> List[Playfield]:
        log.debug("finding playfields containing terrain placeables")
        pfsWithPlaceables = []
        for row in self.getGameDbCursor().execute("SELECT distinct playfields.pfid, playfields.name from TerrainPlaceables LEFT JOIN playfields ON TerrainPlaceables.pfid = playfields.pfid;"):
            pfsWithPlaceables.append(Playfield(pfid=row[0], name=row[1]))
        log.debug(f"playfields containing terrain placeables: {len(pfsWithPlaceables)}")
        return pfsWithPlaceables

    def retrievePFsWithPlayers(self) -> List[Playfield]:
        log.debug("finding playfields containing players")
        pfsWithPlayers = []
        for row in self.getGameDbCursor().execute("select distinct playfields.pfid, playfields.name from Entities LEFT JOIN playfields ON Entities.pfid = playfields.pfid WHERE Entities.etype = 1;"):
            pfsWithPlayers.append(Playfield(pfid=row[0], name=row[1]))
        log.debug(f"playfields containing players: {len(pfsWithPlayers)}")
        return pfsWithPlayers

    def retrieveAllNonEmptyPlayfields(self) -> List[Playfield]:
        """this will get all non empty playfields from the db, excluding pfs with structures, placeables or players"""
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
            log.debug(f"deleting batch {i}-{i+batchSize} with {len(pfIdBatch)} pfids")
            query = "DELETE FROM DiscoveredPlayfields WHERE pfid IN ({})".format(','.join(['?'] * len(pfIdBatch)))
            cursor.execute(query, pfIdBatch)
            log.debug(f"deleted {cursor.rowcount} entries from DiscoveredPlayfields")

        connection = self.getGameDbConnection()
        connection.commit()

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
        query = "SELECT DISTINCT pf.pfid, pf.name, ss.ssid, ss.name FROM Playfields as pf LEFT JOIN SolarSystems AS ss ON pf.ssid=ss.ssid WHERE pf.name IN ({})".format(','.join(['?'] * len(playfieldNames)))
        playfields = []
        for row in cursor.execute(query, playfieldNames):
            playfields.append(Playfield(pfid=row[0], name=row[1], ssid=row[2], starName=row[3]))
        log.debug(f"found {len(playfields)} playfields")
        return playfields
    
    def retrieveLatestGametime(self):
        """
        returns the current gametick and stoptime from the serverstartstop table. 
        Gameticks and passed time do not correlate exactly, since ticks/second vary. They usually default to ~20 ticks/s though.
        
        select sid, startticks, stopticks, starttime, stoptime, timezone from ServerStartStop order by sid desc limit 1
        34	341747	351813	2023-10-17 18:52:23	2023-10-17 19:00:50	v1.10.4	4243	+02:00
        """
        log.debug(f"quering db for latest serverstartstop entry")
        cursor = self.getGameDbCursor()
        query = "SELECT sid, startticks, stopticks, starttime, stoptime, timezone FROM ServerStartStop ORDER BY sid DESC LIMIT 1"
        cursor.execute(query)
        row = cursor.fetchone()
        stopticks = row[2]
        stoptimeString = row[4]

        dateFormat = '%Y-%m-%d %H:%M:%S'
        # Create a datetime object from the date string
        stoptime = datetime.strptime(stoptimeString, dateFormat)        
        return stopticks, stoptime
    
    def retrievePFsUnvisitedSince(self, gametick) -> List[Playfield]:
        """
        Return all playfields that haven't been warped-to since gametick - in other words: all playfields that have newer visits, will not be returned.
        Will also exclude playfields that contain a player, if he hasn't left that pf since given gametick

        select pfs.pfid, pfs.name, pfs.ssid, ss.name from ChangedPlayfields as cpfs join playfields as pfs on cpfs.topfid = pfs.pfid join SolarSystems as ss on ss.ssid = pfs.ssid where topfid not in (select distinct pfid from entities as e where e.etype = 1) and gametime < 1000000
        """
        cursor = self.getGameDbCursor()
        playfields = []
        query = F"SELECT DISTINCT pfs.pfid, pfs.name, pfs.ssid, ss.name from ChangedPlayfields as cpfs join playfields as pfs on cpfs.topfid = pfs.pfid join SolarSystems as ss on ss.ssid = pfs.ssid where topfid not in (select distinct pfid from entities as e where e.etype = 1)"
        query = F"{query} and gametime < {gametick}"
        for row in cursor.execute(query):
            playfields.append(Playfield(pfid=row[0], name=row[1], ssid=row[2], starName=row[3]))
        return playfields

    def retrievePurgeableEntitiesByPlayfields(self, playfields: List[Playfield]) -> List[Entity]:
        """
        retrieve all entities contained in the given playfield that can be purged, this means:
        * type must be structure (isstructure=1 => is SV HV CV or BA)
        * type must be no proxy

        select entityid, pfid, name, etype from Entities where isstructure=1 and isproxy=0 and etype in (2,3,4,5) and pfid in (x,y,z)
        """
        query = "SELECT entityid, pfid, name, etype, isremoved from Entities where isstructure=1 and isproxy=0 and etype in (2,3,4,5)"
        query = f"{query} and pfid in " + "({})".format(','.join(['?'] * len(playfields)))
        cursor = self.getGameDbCursor()
        entities = []
        playfieldList = list(map(lambda playfield: playfield.pfid, playfields))
        for row in cursor.execute(query, playfieldList):
            entities.append(Entity(id=row[0], pfid=row[1], name=row[2], type=EntityType.byNumber(row[3]), isremoved=row[4]))
        return entities
    
    def retrieveLatestGameStoptickWithinDatetime(self, maxDatetime: datetime):
        """
        return the starttick of the timeperiod the server was running, or the stoptick if it was after a running period.

        select sid, startticks, stopticks, starttime, stoptime, timezone from ServerStartStop order by sid desc limit 1
        34	341747	351813	2023-10-17 18:52:23	2023-10-17 19:00:50	v1.10.4	4243	+02:00
        """
        dateFormat = '%Y-%m-%d %H:%M:%S'
        cursor = self.getGameDbCursor()
        query = "SELECT sid, startticks, stopticks, starttime, stoptime, timezone FROM ServerStartStop ORDER BY sid DESC"
        for row in cursor.execute(query):
            startticks = row[1]
            stopticks = row[2]
            starttimeString = row[3]
            stoptimeString = row[4]
            if starttimeString and stoptimeString:
                # Create a datetime object from the date string
                starttime = datetime.strptime(starttimeString, dateFormat)
                stoptime = datetime.strptime(stoptimeString, dateFormat)
                if starttime < maxDatetime < stoptime:
                    return startticks, stoptime
                elif maxDatetime > stoptime:
                    return stopticks, stoptime
        # return the last of the loop (which will be the first sst entry, being the oldest times)
        return startticks, stoptime
    
    def retrievePuregableRemovedEntities(self) -> List[Entity]:
        """return all entities that are marked as removed from the db

        * type must be structure (isstructure=1 => is SV HV CV or BA)
        * type must be no proxy

        select entityid, pfid, name, etype from Entities where isremoved=1 and isstructure=1 and isproxy=0 and etype in (2,3,4,5)
        """
        entities = []
        cursor = self.getGameDbCursor()
        query = "select entityid, pfid, name, etype from Entities where isremoved=1 and isstructure=1 and isproxy=0 and etype in (2,3,4,5)"
        for row in cursor.execute(query):
            entities.append(Entity(id=row[0], pfid=row[1], name=row[2], type=EntityType.byNumber(row[3]), isremoved=True))
        return entities
    
    def countDiscoveredPlayfields(self) -> int:
        """
        just return the amount of discovered playfields
        """
        cursor = self.getGameDbCursor()
        query = "select count(*) from DiscoveredPlayfields"
        cursor.execute(query)
        return cursor.fetchone()[0]
    