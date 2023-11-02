from datetime import datetime, timedelta
from functools import cached_property
import logging
from math import sqrt
from pathlib import Path
from typing import List
from esm.Exceptions import WrongParameterError
from esm import Tools
from esm.DataTypes import Entity, Playfield, SolarSystem, Territory, WipeType
from esm.EsmConfigService import EsmConfigService
from esm.EsmDatabaseWrapper import EsmDatabaseWrapper
from esm.EsmFileSystem import EsmFileSystem
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import Timer

log = logging.getLogger(__name__)

@Service
class EsmWipeService:
    """
    Service class that provides some functionality to wipe and purge playfields and other stuff

    optimized for huge savegames, just when you need to wipe a whole galaxy without affecting players.
    """
    @cached_property
    def config(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)

    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)

    def wipeEmptyPlayfields(self, dbLocation, territoryString, wipeType: WipeType, nodryrun, nocleardiscoveredby=False):
        """
        wipe given territory with given wipetype and mode using the given db
        """
        database = EsmDatabaseWrapper(dbLocation)
        if nodryrun and not nocleardiscoveredby:
            # we need to open the db in rw mode, if we are to clear the discoverd-by info
            database.getGameDbConnection(mode="rw")
        with Timer() as timer:
            allSolarSystems = database.retrieveAllSolarSystems()
            if territoryString == Territory.GALAXY:
                territory = Territory(Territory.GALAXY,0,0,0,0)
                solarSystems = allSolarSystems
            else:
                territory = self.getCustomTerritoryByName(territoryString)
                solarSystems = self.getSolarSystemsInCustomTerritory(allSolarSystems, territory)
            log.info(f"The amount of stars is: {len(solarSystems)}")
            emptyPlayfields = database.retrieveEmptyDiscoveredPlayfields(solarSystems)
            log.info(f"The amount of empty but discovered playfields that can be wiped is: {len(emptyPlayfields)}")

            if not nocleardiscoveredby and len(emptyPlayfields) > 0:
                self.clearDiscoveredByInfoForPlayfields(playfields=emptyPlayfields, database=database, nodryrun=nodryrun, closeConnection=False, doPrint=False)

            database.closeDbConnection()
        log.info(f"Connection to database closed. Time elapsed reading from the database: {timer.elapsedTime}")

        if len(emptyPlayfields) < 1:
            log.warn(f"There is nothing to wipe!")
            return

        if nodryrun:
            self.wipePlayfields(emptyPlayfields, wipeType)
        else:
            self.printoutPlayfields(territoryString, emptyPlayfields, wipeType)
        
    def wipePlayfields(self, playfields: List[Playfield], wipeType: WipeType):
        """
        actually wipe the given playfields with the wipeType.
        """
        playfieldsFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.playfields")
        log.info(f"Starting wipe for {len(playfields)} playfields with wipe type '{wipeType.value.name}' in folder '{playfieldsFolderPath}'")
        wiped = 0
        with Timer() as timer:
            counter=0
            for playfield in playfields:
                log.debug(f"wiping playfield: {playfield.name}")
                playfieldPath = Path(f"{playfieldsFolderPath}/{playfield.name}")
                result = self.createWipeInfo(playfieldPath, wipeType)
                if result: 
                    wiped += 1
                counter+=1
                if counter % 1000 == 0:
                    log.info(f"processed {counter} playfields")
        log.info(f"Done with wiping {len(playfields)} PFs in {timer.elapsedTime}, writing {wiped} files! Playfields are wiped when loaded, so to actually see if something has been wiped, you have to visit a playfield.")

    def printoutPlayfields(self, territory, playfields: List[Playfield], wipeType: WipeType):
        """
        creates a csv with the playfields that would have been wiped, to verify the results if needed, or whatever.        
        """
        csvFilename = Path(f"esm-wipe_{territory}_{wipeType.value.name}.csv").absolute()
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
        """create the wipeinfo at the given path, will return True if successful, false otherwise """
        if path.exists():
            filePath = Path(f"{path}/wipeinfo.txt")
            if filePath.exists():
                log.debug(f"File '{filePath}' already exists - will overwrite it")
            filePath.write_text(data=wipeType.value.name)
            return True
        else:
            log.debug(f"playfield path '{path}' doesn't exist! If the playfield doesn't exist on the filesystem, there's no need to wipe it")
            return False

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

    def clearDiscoveredByInfo(self, names, nodryrun, database=None, dbLocation=None, closeConnection=True):
        """
        clears the discoveredbyInfo for playfields/systemnames given. This will resolve these first
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        # get the list of playfields for the solarsystems
        systemNames, playfieldNames = Tools.extractSystemAndPlayfieldNames(names)
        log.debug(f"playfield names: {len(playfieldNames)} system names: {len(systemNames)}")
        if nodryrun:
            # call this once on the db to make sure the db will be writable on the following operations.
            database.getGameDbConnection("rw")
        playfieldsFromSolarSystems = []
        if systemNames and len(systemNames) > 0:
            solarsystems = database.retrieveSolarsystemsByName(systemNames)
            if solarsystems and len(solarsystems) > 0:
                playfieldsFromSolarSystems = database.retrieveDiscoveredPlayfieldsForSolarSystems(solarsystems)
        playfieldsByName = []
        if playfieldNames and len(playfieldNames) > 0:
            playfieldsByName = database.retrievePlayfieldsByName(playfieldNames)
        playfields = list(set(playfieldsByName) | set(playfieldsFromSolarSystems))
        log.info(f"Found {len(playfields)} playfields matching the systems and names given that are currently discovered.")
        if len(playfields) > 0:
            return self.clearDiscoveredByInfoForPlayfields(playfields, nodryrun, database=database, dbLocation=dbLocation, closeConnection=closeConnection)
        else:
            log.info("Nothing to do.")
            return
        
    def clearDiscoveredByInfoForPlayfields(self, playfields: List[Playfield], nodryrun, database=None, dbLocation=None, closeConnection=True, doPrint=True):
        """
        clears the discoveredbyInfo for the given playfields
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        if nodryrun:
            log.info(f"Will delete the discovered-by info from {len(playfields)} playfields")
            database.deleteFromDiscoveredPlayfields(playfields=playfields)
            if closeConnection:
                database.closeDbConnection()
        else:
            if doPrint:
                csvFilename = Path(f"esm-cleardiscoveredby.csv").absolute()
                log.info(f"Will output the list of {len(playfields)} playfields whose discoverd-by info would have been cleared '{csvFilename}'")
                self.printListOfPlayfieldsAsCSV(csvFilename=csvFilename, playfields=playfields)
    
    def printListOfPlayfieldsAsCSV(self, csvFilename, playfields: List[Playfield]):
        """
        creates a csv with the given playfields that would have been altered, to verify the results if needed, or whatever.
        """
        with open(csvFilename, 'w', encoding='utf-8') as file:
            file.write("playfield_id,playfield_name,system_id,system_name\n")
            for playfield in playfields:
                file.write(f"{playfield.pfid},{playfield.name},{playfield.ssid},{playfield.starName}\n")
        log.info("CSV file written. Nothing was changed in the current savegame. Please remember that this list gets instantly outdated once players play the game.")

    def printListOfEntitiesAsCSV(self, csvFilename, entities: List[Entity]):
        """
        creates a csv with the given playfields that would have been altered, to verify the results if needed, or whatever.
        """
        with open(csvFilename, 'w', encoding='utf-8') as file:
            file.write("entity_id,entity_name,entity_pfid,entity_type,entity_isremoved\n")
            for entity in entities:
                file.write(f"{entity.id},{entity.name},{entity.pfid},{entity.type.name},{entity.isremoved}\n")
        log.info("CSV file written. Nothing was changed in the current savegame. Please remember that this list gets instantly outdated once players play the game.")

    def purgeEmptyPlayfields(self, database=None, dbLocation=None, minimumage=30, nodryrun=False, nocleardiscoveredby=False, leavetemplates=False, force=False):
        """
        will purge (delete) all playfields and associated static entities from the filesystem that haven't been visisted for miniumage days.
        this includes deleting the templates, unless leavetemplates is set to true
        
        force will force delete anything without asking the user.
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)

        if nodryrun and not nocleardiscoveredby:
            # we need to open the db in rw mode
            database.getGameDbConnection(mode="rw")

        maxDatetime = datetime.now() - timedelta(minimumage)
        maximumGametick, stoptime = database.retrieveLatestGameStoptickWithinDatetime(maxDatetime)
        log.debug(f"latest entry for given max age is stoptime {stoptime} and gametick {maximumGametick}")
        # get all playfields older than minage
        totalPlayfields = database.countDiscoveredPlayfields()
        log.debug(f"total playfields {totalPlayfields}")
        olderPlayfields = database.retrievePFsUnvisitedSince(maximumGametick)
        log.debug(f"found {len(olderPlayfields)} playfields unvisited since {stoptime}")

        if len(olderPlayfields) < 1:
            log.info(f"Nothing to purge")
            return
        
        # get all occupied playfields
        occupiedPlayfields = database.retrieveAllNonEmptyPlayfields()
        log.debug(f"{len(occupiedPlayfields)} playfields are occupied by players or their stuff")
        # filter out playfields that contain player stuff, using sets, since we can just substract these very fast
        playfields = list(set(olderPlayfields) - set(occupiedPlayfields))
        log.debug(f"{len(playfields)} playfields can be purged")

        # get all purgeable entities that are contained in the playfields
        entities = database.retrievePurgeableEntitiesByPlayfields(playfields)

        if nodryrun:
            log.info(f"Purging {len(playfields)} playfields and {len(entities)} contained entities from the file system.")
            if not nocleardiscoveredby and len(playfields) > 0:
                self.clearDiscoveredByInfoForPlayfields(playfields=playfields, database=database, nodryrun=nodryrun, closeConnection=False, doPrint=False)
            database.closeDbConnection()
            log.debug(f"Purging {len(playfields)} playfields")
            pfCounter, tpCounter = self.doPurgePlayfields(playfields, leavetemplates)
            log.debug(f"Purging {len(entities)} entities")
            enCounter = self.doPurgeEntities(entities)

            additionalInfo = f"{pfCounter} playfield folders, {tpCounter} template folders and {enCounter} entity folders marked for deletion."
            if force:
                result, elapsedTime = self.fileSystem.commitDelete(override="yes", additionalInfo=additionalInfo)
            else:
                result, elapsedTime = self.fileSystem.commitDelete(additionalInfo=additionalInfo)
            log.info(f"Deleting took {elapsedTime}")
        else:
            database.closeDbConnection()
            csvFilename = Path(f"esm-purgeplayfields-older-than-{minimumage}.csv").absolute()
            log.info(f"Will output the list of {len(playfields)} playfields that would have been purged as '{csvFilename}'")
            self.printListOfPlayfieldsAsCSV(csvFilename=csvFilename, playfields=playfields)

            csvFilename = Path(f"esm-purgeentities-older-than-{minimumage}.csv").absolute()
            log.info(f"Will output the list of {len(entities)} entities that would have been purged as '{csvFilename}'")
            self.printListOfEntitiesAsCSV(csvFilename=csvFilename, entities=entities)

    def doPurgePlayfields(self, playfields: List[Playfield], leavetemplates=False):
        """deletes the folders associated with the given playfields
        returns the amount of folders marked for deletion for playfields and templates
        """
        playfieldFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.playfields")
        templateFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.templates")
        markedPfCounter = 0
        markedTpCounter = 0
        for playfield in playfields:
            playfieldPath = Path(f"{playfieldFolderPath}/{playfield.name}")
            if playfieldPath.exists():
                log.debug(f"playfield folder '{playfieldPath}' exists and will be marked for deletion")
                self.fileSystem.markForDelete(targetPath=playfieldPath)
                markedPfCounter += 1
            if not leavetemplates:
                templatePath = Path(f"{templateFolderPath}/{playfield.name}")
                if templatePath.exists():
                    log.debug(f"template folder '{templatePath}' exists and will be marked for deletion")
                    self.fileSystem.markForDelete(targetPath=templatePath)
                    markedTpCounter += 1
        return markedPfCounter, markedTpCounter
    
    def doPurgeEntities(self, entities: List[Entity]):
        """deletes the folders associated with the given entities
        returns the amount of still existing folders marked for deletion
        """
        sharedFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.shared")
        markedCounter = 0
        for entity in entities:
            idPath = Path(f"{sharedFolderPath}/{entity.id}")
            if idPath.exists():
                log.debug(f"folder '{idPath}' exists although it is marked as deleted")
                self.fileSystem.markForDelete(targetPath=idPath)
                markedCounter += 1
        return markedCounter
    
    def purgeRemovedEntities(self, database=None, dbLocation=None, nodryrun=False):
        """purge any entity that is marked as removed in the db
        returns the amount of entity folders marked for deletion
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        # get all entites marked as removed in the db
        removedEntities = database.retrievePuregableRemovedEntities()
        log.debug(f"got {len(removedEntities)} entites marked as removed")
        if nodryrun:
            # purge all their files from the current savegame
            return self.doPurgeEntities(removedEntities)
        else:
            csvFilename = Path(f"esm-clean-removed-entites.csv").resolve()
            log.info(f"Will output the list of {len(removedEntities)} entities that should have been removed as '{csvFilename}'")
            self.printListOfEntitiesAsCSV(csvFilename=csvFilename, entities=removedEntities)
            return None

    def purgeWipedPlayfields(self, leavetemplates=False):
        """
        purge all playfields that have a wipeinfo file containing 'all'. also purge its templates if leavetemplates is False
        """
        playfieldsFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.playfields")
        templatesFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.templates")

        log.debug(f"iterating through playfields in {playfieldsFolderPath}")
        wipedPlayfieldNames = []
        playfieldCount = 0
        processCounter = 0
        for folder in playfieldsFolderPath.iterdir():
            wipeInfoPath = Path(f"{folder}/wipeinfo.txt")
            if wipeInfoPath.exists():
                content = wipeInfoPath.read_text()
                if content is not None and content.startswith(WipeType.ALL.value.name):
                    wipedPlayfieldNames.append(Path(folder).name)
                    playfieldCount += 1
                    self.fileSystem.markForDelete(folder)
            processCounter += 1
            if processCounter % 10000 == 0:
                log.debug(f"processed {processCounter} playfield folders")
        log.debug(f"found {len(wipedPlayfieldNames)} from {processCounter} playfields with a wipeinfo containing '{WipeType.ALL.value.name}'")

        templateCount = 0
        processCounter = 0
        if not leavetemplates:
            for playfieldName in wipedPlayfieldNames:
                templatePath = Path(f"{templatesFolderPath}/{playfieldName}")
                if templatePath.exists():
                    templateCount += 1
                    self.fileSystem.markForDelete(templatePath)
                processCounter += 1
                if processCounter % 10000 == 0:
                    log.debug(f"processed {processCounter} template folders")

        log.debug(f"marked {templateCount} from {processCounter} template folders for deletion")
        return wipedPlayfieldNames, playfieldCount, templateCount

    def cleanUpSharedFolder(self, database=None, dbLocation=None, nodryrun=False, force=False):
        """
        will check the entries in the shared folder, then retrieve all non-removed entities from the db and delete the dangling folders.
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        
        sharedFolderPath = self.fileSystem.getAbsolutePathTo("saves.games.savegame.shared")
        fsEntityIds = []
        for entry in sharedFolderPath.iterdir():
            id = Path(f"{entry}").name
            fsEntityIds.append(id)
        log.debug(f"found {len(fsEntityIds)} entries in the shared folder")
        
        dbEntityIds = database.retrieveNonRemovedEntities()
        log.debug(f"found {len(dbEntityIds)} entries in the database")

        # calculate all ids that are on the FS but not in the DB (or marked as removed there)
        idsOnFsNotInDb = sorted(list(set(fsEntityIds) - set(dbEntityIds)))

        additionalInfo = f"found {len(idsOnFsNotInDb)} dangling entries in the shared folder that can be removed"
        if nodryrun:
            for id in idsOnFsNotInDb:
                self.fileSystem.markForDelete(Path(f"{sharedFolderPath}/{id}"))

            if force:
                result, elapsedTime = self.fileSystem.commitDelete(override="yes", additionalInfo=additionalInfo)
            else:
                result, elapsedTime = self.fileSystem.commitDelete(additionalInfo=additionalInfo)

            if result:
                log.info(f"Deleted {len(idsOnFsNotInDb)} folders in {elapsedTime}")
        else:
            log.info(additionalInfo)
            filename="esm-cleanup-shared-folder.lst"
            log.info(f"Saving list of ids that are obsolete in file {filename}")
            with open(filename, "w", encoding="utf-8") as file:
                file.writelines([line + '\n' for line in idsOnFsNotInDb])

