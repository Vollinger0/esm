from functools import cached_property
import logging
from math import sqrt
from pathlib import Path
import sys
from typing import List
from esm.ConfigModels import MainConfig
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
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config
    
    @cached_property
    def configService(self) -> EsmConfigService:
        return ServiceRegistry.get(EsmConfigService)

    @cached_property
    def fileSystem(self) -> EsmFileSystem:
        return ServiceRegistry.get(EsmFileSystem)

    def wipeTerritory(self, dbLocation, territoryString, wipeType: WipeType, dryrun, cleardiscoveredby=True):
        """
        wipe given territory with given wipetype and mode using the given db
        """
        database = EsmDatabaseWrapper(dbLocation)
        if not dryrun and cleardiscoveredby:
            database.setWriteMode()

        with Timer() as timer:
            allSolarSystems = database.retrieveSSsAll()
            if territoryString == Territory.GALAXY:
                solarSystems = allSolarSystems
            else:
                territory = self.getCustomTerritoryByName(territoryString)
                solarSystems = self.areInCustomTerritory(allSolarSystems, territory)
            log.info(f"The amount of stars is: {len(solarSystems)}")
            emptyPlayfields = database.retrievePFsEmptyDiscoveredBySolarSystems(solarSystems)
            log.info(f"The amount of empty but discovered playfields that can be wiped is: {len(emptyPlayfields)}")

            if cleardiscoveredby and len(emptyPlayfields) > 0:
                self.clearDiscoveredByInfoForPlayfields(playfields=emptyPlayfields, database=database, dryrun=dryrun, closeConnection=True, doPrint=False)
        log.info(f"Connection to database closed. Time elapsed reading from the database: {timer.elapsedTime}")

        if len(emptyPlayfields) < 1:
            log.warn(f"There is nothing to wipe!")
            return

        if dryrun:
            csvFilename = Path(f"esm-wipe_{territoryString}_{wipeType.value.name}.csv").absolute()
            log.info(f"Will output the list of playfields that would have been wiped as '{csvFilename}'")
            self.printListOfPlayfieldsAsCSV(csvFilename=csvFilename, playfields=emptyPlayfields)
        else:
            self.createWipeInfoForPlayfields(emptyPlayfields, wipeType)

        
    def createWipeInfoForPlayfields(self, playfields: List[Playfield], wipeType: WipeType):
        """
        actually wipe the given playfields with the wipeType by creating the wipeinfo files in the file system.
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

    def getCustomTerritoryByName(self, territoryName):
        for ct in self.configService.getAvailableTerritories():
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

    def isInCustomTerritory(self, solarsystem: SolarSystem, customTerritory: Territory):
        """
          calculate distance of given star to center of the custom territory. if its bigger than its radius, we assume its outside.
        """
        distance = sqrt(((solarsystem.x - customTerritory.x)**2) + ((solarsystem.y - customTerritory.y)**2) + ((solarsystem.z - customTerritory.z)**2))
        return (distance <= customTerritory.radius)

    def areInCustomTerritory(self, solarSystems: List[SolarSystem], customTerritory: Territory) -> List[SolarSystem]:
        """
        return the list of solarSystems that are in the custom territory
        """
        if customTerritory == Territory.GALAXY:
            return solarSystems
        else:
            customTerritorySolarSystems = []
            for solarsystem in solarSystems:
                if self.isInCustomTerritory(solarsystem, customTerritory):
                    customTerritorySolarSystems.append(solarsystem)
            return customTerritorySolarSystems

    def clearDiscoveredByInfo(self, systemAndPlayfieldNames, dryrun=True, database=None, dbLocation=None, closeConnection=True):
        """
        clears the discoveredbyInfo for playfields/systemnames given. This will resolve these first
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        # get the list of playfields for the solarsystems
        systemNames, playfieldNames = Tools.extractSystemAndPlayfieldNames(systemAndPlayfieldNames)
        log.debug(f"playfield names: {len(playfieldNames)} system names: {len(systemNames)}")
        if not dryrun:
            database.setWriteMode()
        playfieldsFromSolarSystems = []
        if systemNames and len(systemNames) > 0:
            solarsystems = database.retrieveSSsByName(systemNames)
            if solarsystems and len(solarsystems) > 0:
                playfieldsFromSolarSystems = database.retrievePFsDiscoveredBySolarSystems(solarsystems)
        playfieldsByName = []
        if playfieldNames and len(playfieldNames) > 0:
            playfieldsByName = database.retrievePFsByName(playfieldNames)
        playfields = list(set(playfieldsByName) | set(playfieldsFromSolarSystems))
        if len(playfields) > 0:
            log.info("Found no matching playfields. Nothing to do.")
            if closeConnection:
                database.closeDbConnection()
            return
        log.info(f"Found {len(playfields)} playfields matching the systems and names given that are currently discovered.")
        return self.clearDiscoveredByInfoForPlayfields(playfields, dryrun, database=database, dbLocation=dbLocation, closeConnection=closeConnection)
        
    def clearDiscoveredByInfoForPlayfields(self, playfields: List[Playfield], dryrun, database=None, dbLocation=None, closeConnection=True, doPrint=True):
        """
        clears the discoveredbyInfo for the given playfields
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        if dryrun:
            if closeConnection:
                database.closeDbConnection()
            if doPrint:
                csvFilename = Path(f"esm-cleardiscoveredby.csv").absolute()
                log.info(f"Will output the list of {len(playfields)} playfields whose discoverd-by info would have been cleared '{csvFilename}'")
                self.printListOfPlayfieldsAsCSV(csvFilename=csvFilename, playfields=playfields)
        else:
            log.info(f"Will delete the discovered-by info from {len(playfields)} playfields")
            database.deleteFromDiscoveredPlayfields(playfields=playfields)
            if closeConnection:
                database.closeDbConnection()
    
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

    def purgeEmptyPlayfields(self, database=None, dbLocation=None, minimumage=30, dryrun=True, cleardiscoveredby=True, leavetemplates=False, force=False):
        """
        will purge (delete) all playfields and associated static entities from the filesystem that haven't been visisted for miniumage days.
        this includes deleting the templates, unless leavetemplates is set to true
        
        force will force delete anything without asking the user.
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)

        if not dryrun and cleardiscoveredby:
            # we need to open the db in rw mode
            database.setWriteMode()

        olderPlayfields = database.retrievePFsDiscoveredOlderThanAge(minimumage)

        if len(olderPlayfields) < 1:
            log.info(f"Nothing to purge")
            return
        
        # get all occupied playfields
        occupiedPlayfields = database.retrievePFsAllNonEmpty()
        log.debug(f"{len(occupiedPlayfields)} playfields are occupied by players or their stuff")
        # filter out playfields that contain player stuff, using sets, since we can just substract these very fast
        playfields = list(set(olderPlayfields) - set(occupiedPlayfields))
        log.debug(f"{len(playfields)} playfields can be purged")

        # get all purgeable entities that are contained in the playfields
        entities = database.retrievePurgeableEntitiesByPlayfields(playfields)

        if dryrun:
            database.closeDbConnection()
            csvFilename = Path(f"esm-purgeplayfields-older-than-{minimumage}.csv").absolute()
            log.info(f"Will output the list of {len(playfields)} playfields that would have been purged as '{csvFilename}'")
            self.printListOfPlayfieldsAsCSV(csvFilename=csvFilename, playfields=playfields)

            csvFilename = Path(f"esm-purgeentities-older-than-{minimumage}.csv").absolute()
            log.info(f"Will output the list of {len(entities)} entities that would have been purged as '{csvFilename}'")
            self.printListOfEntitiesAsCSV(csvFilename=csvFilename, entities=entities)

        else:
            log.info(f"Purging {len(playfields)} playfields and {len(entities)} contained entities from the file system.")
            if cleardiscoveredby and len(playfields) > 0:
                self.clearDiscoveredByInfoForPlayfields(playfields=playfields, database=database, dryrun=dryrun, closeConnection=True, doPrint=False)
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
    
    def purgeRemovedEntities(self, database=None, dbLocation=None, dryrun=True):
        """purge any entity that is marked as removed in the db
        returns the amount of entity folders marked for deletion
        """
        if database is None:
            if dbLocation is None:
                raise WrongParameterError("neither database nor dblocation was provided to access the database")
            database = EsmDatabaseWrapper(dbLocation)
        # get all entites marked as removed in the db
        removedEntities = database.retrievePurgeableRemovedEntities()
        database.closeDbConnection()
        log.debug(f"got {len(removedEntities)} entites marked as removed")
        if dryrun:
            csvFilename = Path(f"esm-clean-removed-entites.csv").resolve()
            log.info(f"Will output the list of {len(removedEntities)} entities that should have been removed as '{csvFilename}'")
            self.printListOfEntitiesAsCSV(csvFilename=csvFilename, entities=removedEntities)
            return None
        else:
            # purge all their files from the current savegame
            return self.doPurgeEntities(removedEntities)

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

    def cleanUpSharedFolder(self, database=None, dbLocation=None, dryrun=True, force=False):
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
        database.closeDbConnection()
        log.debug(f"found {len(dbEntityIds)} entries in the database")

        # calculate all ids that are on the FS but not in the DB (or marked as removed there)
        idsOnFsNotInDb = sorted(list(set(fsEntityIds) - set(dbEntityIds)))

        additionalInfo = f"found {len(idsOnFsNotInDb)} dangling entries in the shared folder that can be removed"
        if dryrun:
            log.info(additionalInfo)
            filename="esm-cleanup-shared-folder.lst"
            log.info(f"Saving list of ids that are obsolete in file {filename}")
            with open(filename, "w", encoding="utf-8") as file:
                file.writelines([line + '\n' for line in idsOnFsNotInDb])
        else:
            for id in idsOnFsNotInDb:
                self.fileSystem.markForDelete(Path(f"{sharedFolderPath}/{id}"))

            if force:
                result, elapsedTime = self.fileSystem.commitDelete(override="yes", additionalInfo=additionalInfo)
            else:
                result, elapsedTime = self.fileSystem.commitDelete(additionalInfo=additionalInfo)

            if result:
                log.info(f"Deleted {len(idsOnFsNotInDb)} folders in {elapsedTime}")

    def wipeTool(self, systemAndPlayfieldNames, territory: Territory, purge, wipetype, purgeleavetemplates, purgeleaveentities, cleardiscoveredby, minage, dbLocationPath, dryrun, force):

        log.debug(f"{__name__}.{sys._getframe().f_code.co_name} called with params: {locals()}")

        database: EsmDatabaseWrapper = EsmDatabaseWrapper(dbLocationPath)
        if not dryrun and cleardiscoveredby:
            database.setWriteMode()

        # retrieve solar systems and playfields in either the systemAndPlayfieldNames or the territory
        selectedSolarSystems = []
        selectedPlayFields = []
        if systemAndPlayfieldNames and len(systemAndPlayfieldNames) > 0:
            log.info(f"Selecting playfields for wipe from list of {len(systemAndPlayfieldNames)} names")
            log.debug(f"extracting solar systems and playfields from the list of {len(systemAndPlayfieldNames)} names")
            solarSystemNames, playfieldNames = Tools.extractSystemAndPlayfieldNames(systemAndPlayfieldNames)
            selectedSolarSystems = database.retrieveSSsByName(solarSystemNames)
            selectedPlayFields = database.retrievePFsByName(playfieldNames)
            log.debug(f"extracted {len(selectedSolarSystems)} solarsystems and {len(selectedPlayFields)} playfields from {len(systemAndPlayfieldNames)} names in the list")
        if territory:
            log.info(f"Selecting playfields for wipe from custom territory {territory.name}")
            log.debug(f"extracting solar systems from the custom territory {territory.name}")
            allSolarSystems = database.retrieveSSsAll()
            selectedSolarSystems = self.areInCustomTerritory(allSolarSystems, territory)
            log.debug(f"extracted {len(selectedSolarSystems)} solarsystems from the custom territory {territory.name}")

        pfsEmptyDiscovered = database.retrievePFsEmptyDiscoveredBySolarSystems(selectedSolarSystems)
        allSelectedPlayfields = pfsEmptyDiscovered + selectedPlayFields
        log.debug(f"selected {len(allSelectedPlayfields)} to be wiped disregarding their age")

        pfsUnvisitedSince = database.retrievePFsDiscoveredOlderThanAge(minage)
        log.debug(f"extracted {len(pfsUnvisitedSince)} playfields that are older than {minage} days")

        playfieldsToWipe = list(set(allSelectedPlayfields).intersection(set(pfsUnvisitedSince)))

        if len(playfieldsToWipe) < 1:
            log.info(f"No playfields selected for wipe - nothing to do.")
            return
        else:
            log.info(f"{len(playfieldsToWipe)} playfields selected for wipe/purge")

        if dryrun:
            csvFilename = Path(f"esm-wipe-tool_selected_playfields.csv").absolute()
            log.info(f"Will output the list of {len(playfieldsToWipe)} playfields that would have been wiped/purged as '{csvFilename}'")
            self.printListOfPlayfieldsAsCSV(csvFilename=csvFilename, playfields=playfieldsToWipe)
            return

        if cleardiscoveredby:
            database.deleteFromDiscoveredPlayfields(playfieldsToWipe)

        if purge:
            # TODO: trigger purge for playfieldsToWipe
            # TODO: trigger purge for templates
            # TODO: trigger purge for entities
            pass
        else:
            # TODO: trigger wipe for playfieldsToWipe
            self.createWipeInfoForPlayfields(playfields=playfieldsToWipe, wipetype=wipetype, cleardiscoveredby=cleardiscoveredby)
            pass
