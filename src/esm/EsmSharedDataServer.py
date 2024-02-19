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
        # just using something smaller for debugging
        pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData/Content/Extras")
        #pathToSharedDataFolder = pathToScenarioFolder.joinpath("SharedData")

        if not pathToSharedDataFolder.exists():
            log.warning(f"Path to the shared data in the games scenario folder '{pathToSharedDataFolder}' does not exist. Please check the configuration.")
            return
        
        wwwroot = Path(self.config.downloadtool.wwwroot).resolve()
        if not wwwroot.exists():
            FsTools.createDir(wwwroot)
        
        # create zip from the shared data folder with the configured folder name
        log.debug(f"Creating zip from shared data folder at path '{pathToSharedDataFolder}' with name '{self.config.downloadtool.zipName}.zip'")
        result = shutil.make_archive(self.config.downloadtool.zipName, 'zip', base_dir="", root_dir=pathToSharedDataFolder)
        resultZipFilePath = Path(result)
        shutil.move(resultZipFilePath, wwwroot)
        wwwrootZipFilePath = wwwroot.joinpath(f"{self.config.downloadtool.zipName}.zip").resolve()
        log.debug(f"result of zip creation: {wwwrootZipFilePath}")

        # TODO: start webserver on configured port and serve the zip, maybe also with a dynamic index.html that explains how to handle the shared data
        # TODO: log that the server is running and when someone downloads the zip
        log.info("would have started the download server now, but its not implemented yet")
