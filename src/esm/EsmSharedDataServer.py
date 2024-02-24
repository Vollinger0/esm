from functools import cached_property
import logging
from pathlib import Path
import shutil
from esm.ConfigModels import MainConfig
from esm.EsmConfigService import EsmConfigService
from esm.FsTools import FsTools
from esm.ServiceRegistry import Service, ServiceRegistry

log = logging.getLogger(__name__)

@Service
class EsmSharedDataServer:

    @cached_property
    def config(self) -> MainConfig:
        return ServiceRegistry.get(EsmConfigService).config

    def start(self):
        scenarioName = self.config.dedicatedConfig.GameConfig.CustomScenario
        pathToScenarioFolder = Path(f"{self.config.paths.install}/Content/Scenarios/{scenarioName}").resolve()

        log.info(f"Creating new shared data zip file from the current configured scenario at '{pathToScenarioFolder}'")
        resultZipFilePath = self.createSharedDataZipFile(pathToScenarioFolder)
        wwwrootZipFilePath = self.moveSharedDataZipFileToWwwroot(resultZipFilePath)
        log.info(f"Created SharedData zip file as '{wwwrootZipFilePath}' using the cache folder name '{self.config.downloadtool.cacheFolderName}'")

        # TODO: start webserver on configured port and serve the zip, maybe also with a dynamic index.html that explains how to handle the shared data
        # TODO: log that the server is running and when someone downloads the zip
        log.info("would have started the download server now, but its not implemented yet")

    def moveSharedDataZipFileToWwwroot(self, resultZipFilePath: Path) -> Path:
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        if not wwwroot.exists():
            FsTools.createDir(wwwroot)

        wwwrootZipFilePath = wwwroot.joinpath(f"{self.config.downloadtool.zipName}.zip").resolve()
        if wwwrootZipFilePath.exists():
            log.debug(f"Deleting old zip file at '{wwwrootZipFilePath}'")
            FsTools.deleteFile(wwwrootZipFilePath)
        log.debug(f"Moving zip file '{resultZipFilePath}' to '{wwwroot}'")
        shutil.move(resultZipFilePath, wwwroot)
        log.debug(f"result of zip creation: '{wwwrootZipFilePath}'")
        return wwwrootZipFilePath

    def createSharedDataZipFile(self, pathToScenarioFolder: Path) -> Path:
        # just using something smaller for debugging
        pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData/Content/Extras")
        #pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData")

        if not pathToSharedDataFolder.exists():
            log.warning(f"Path to the shared data in the games scenario folder '{pathToSharedDataFolder}' does not exist. Please check the configuration.")
            return
        
        tempFolder = Path(self.config.downloadtool.tempFolder).resolve()
        if tempFolder.exists():
            log.debug(f"deleting old temporary folder '{tempFolder}'")
            FsTools.deleteDir(tempFolder, True)
        FsTools.createDir(tempFolder)
        cacheFolder = tempFolder.joinpath(self.config.downloadtool.cacheFolderName)
        FsTools.createDir(cacheFolder)
        
        log.debug(f"Copying files from '{pathToSharedDataFolder}' to cachefolder '{cacheFolder}'")
        FsTools.copyDir(source=pathToSharedDataFolder, destination=cacheFolder)
        
        # create zip from the cacheFolder
        log.debug(f"Creating zip from cachefolder '{cacheFolder}' with name '{self.config.downloadtool.zipName}.zip'")
        result = shutil.make_archive(self.config.downloadtool.zipName, 'zip', tempFolder)
        resultZipFilePath = Path(result)
        return resultZipFilePath
