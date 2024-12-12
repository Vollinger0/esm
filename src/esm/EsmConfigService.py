import logging
import os
import yaml

from copy import deepcopy
from typing import List
from functools import cached_property
from pathlib import Path
from esm.ConfigModels import DediConfig, MainConfig
from esm.DataTypes import Territory
from esm.EsmGalaxyConfigReader import EsmGalaxyConfigReader
from esm.FsTools import FsTools
from esm.exceptions import AdminRequiredException
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import mergeDicts
from ruamel.yaml import YAML
from easyconfig import create_app_config
from easyconfig.yaml import yaml_rt

log = logging.getLogger(__name__)

@Service
class EsmConfigService:
    """
    Contains all the relevant config for esm, backed by a yaml file that overwrites the default config in the model MainConfig.
    It also loads the games dedicated yaml file to avoid redundant configuration 
    
    Uses pydantic/easyconfig, so the configuration is a validateable complex model, see ConfigModels for details.
    """
    configFilePath: Path = Path("esm-custom-config.yaml")
    searchDedicatedYamlLocal: bool = False

    @staticmethod
    def fromCustomConfigFile(customConfigFilePath: Path, searchDedicatedYamlLocal=True):
        cs = EsmConfigService()
        cs.setConfigFilePath(customConfigFilePath, searchDedicatedYamlLocal)
        ServiceRegistry.register(cs)
        return cs.config

    @staticmethod
    def createDefaultConfigFile(filename: str = "esm-default-config.example.yaml"):
        """
            Creates a new config yaml from our config model with all the default values
        """
        log.info(f"create a new {filename} from default config model")
        yaml_rt.indent(mapping=2, sequence=4, offset=2)
        configFilePath = Path(filename)
        if configFilePath.exists(): configFilePath.unlink()
        newModel = MainConfig.getExampleConfig()
        config = create_app_config(newModel)
        config.load_config_file(configFilePath)
        log.info(f"created file {filename}")

    @staticmethod
    def getTestConfig(dict: dict=None) -> MainConfig:
        """
            creates an inmemory config for testing
            remember to overwrite any attribute you may need
        """
        if dict is not None:
            mainConfig = MainConfig.model_validate(dict)
        else:
            mainConfig = MainConfig.getExampleConfig()
        cs = EsmConfigService()
        return cs.setConfig(mainConfig)

    @cached_property
    def config(self) -> MainConfig:
        return self.getConfig()
    
    def getConfig(self) -> MainConfig:
        if isinstance(self.configFilePath, Path) and self.configFilePath.exists():
            log.debug(f"Reading configuration from path '{self.configFilePath}'")
            with open(self.configFilePath, "r") as configFile:
                configContent = yaml.safe_load(configFile)
                mainConfig = MainConfig.model_validate(configContent)
                return self.setConfig(mainConfig)
        log.error(f"Could not read configuration from path '{self.configFilePath}'")
        raise AdminRequiredException(f"Could not read configuration from path '{self.configFilePath}'")

    def setConfig(self, mainConfig: MainConfig) -> MainConfig:
        self.loadDedicatedYaml(mainConfig)
        mergeDicts(a=mainConfig.context, b={"configFilePath": self.configFilePath})
        return mainConfig
    
    def saveConfig(self, filePath: Path, overwrite: bool = False):
        """ 
            Save the configuration to a new yaml file.
            filePath: Path to the file to save the configuration to.
        """
        if filePath.exists():
            if overwrite:
                log.warning(f"Overwriting configuration file at path '{filePath.absolute()}'")
            else:
                raise AdminRequiredException(f"Can not save configuration: File already exists at path '{filePath.absolute()}'")

        log.debug(f"Saving configuration to path '{filePath.absolute()}'")
        # work on a deep copy, we don't want to alter the existing config. This might be ok for tool-calls but not otherwise.
        model = deepcopy(self.config)
        del model.context
        effectiveConfig = create_app_config(model)
        effectiveConfig.load_config_file(path=filePath.absolute())
        log.info(f"Created file '{filePath.absolute()}'")
        
    
    def loadDedicatedYaml(self, mainConfig: MainConfig):
        """
        Reads the dedicated YAML file into the mainconfig.dedicatedConfig property.
        """
        if mainConfig.paths.install.exists():
            dedicatedYamlPath = mainConfig.paths.install.joinpath(mainConfig.server.dedicatedYaml)
            # override extending install dir - for testing.
            if self.searchDedicatedYamlLocal:
                dedicatedYamlPath = mainConfig.server.dedicatedYaml
            if dedicatedYamlPath.exists():
                with open(dedicatedYamlPath, "r") as configFile:
                    configContent = yaml.safe_load(configFile)
                    mainConfig.dedicatedConfig = DediConfig.model_validate(configContent)
                    return
            else:
                log.error(f"Could not read dedicated.yaml from path '{dedicatedYamlPath.absolute()}'. Are you sure the path is correct?")
                raise AdminRequiredException(f"Could not read dedicated.yaml from path '{dedicatedYamlPath.absolute()}'. Are you sure the path is correct?")
        else:
            log.error(f"Could not find install dir at '{mainConfig.paths.install}'. Are you sure the config is correct?")
            raise AdminRequiredException(f"Could not find install dir at '{mainConfig.paths.install}'. Are you sure the config is correct?")
        
    def backupDedicatedYaml(self):
        """
        Backs up the dedicated.yaml file in the install directory.
        """
        dedicatedYamlPath = self.config.paths.install.joinpath(self.config.server.dedicatedYaml)
        dedicatedYamlBackupPath = dedicatedYamlPath.with_suffix(".bak")
        if dedicatedYamlPath.exists():
            FsTools.copyFile(source=dedicatedYamlPath, destination=dedicatedYamlBackupPath)

    def rollbackDedicatedYaml(self):
        """
        Rolls back the dedicated.yaml file from the backup in the install directory
        """
        dedicatedYamlPath = self.config.paths.install.joinpath(self.config.server.dedicatedYaml)
        dedicatedYamlBackupPath = dedicatedYamlPath.with_suffix(".bak")
        if dedicatedYamlBackupPath.exists():
            FsTools.copyFile(source=dedicatedYamlBackupPath, destination=dedicatedYamlPath)
        
    def upsertYamlProperty(self, filePath: Path, propertyPath, newValue):
        """
        updates or inserts a property in a yaml file, preserving its structure as much as possible
        """
        yaml = YAML(typ="rt", pure=True)
        yaml.preserve_quotes = True

        with open(filePath, 'r') as file:
            data = yaml.load(file)

        keys = propertyPath.split('.')
        d = data
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[keys[-1]] = newValue

        with open(filePath, 'w') as file:
            yaml.dump(data, file)

    def commentOutYamlProperty(self, filePath: Path, propertyPath, valueToMatch):
        """
        comments out a property in a yaml file, preserving its structure as much as possible
        """
        yaml = YAML(typ="rt", pure=True)
        yaml.preserve_quotes = True

        # Parse the dot-notation key path into a list
        key_path_list = propertyPath.split('.')

        with open(filePath, 'r') as file:
            data = yaml.load(file)

        def comment_key_path(d, key_path_list, value_to_match):
            if not key_path_list:
                return
            for key in key_path_list[:-1]:
                if isinstance(d, dict) and key in d:
                    d = d[key]
                else:
                    return  # Path not found, do nothing
            final_key = key_path_list[-1]
            if isinstance(d, dict) and final_key in d and d[final_key] == value_to_match:
                # Comment out the key
                value = d[final_key]
                d.yaml_set_comment_before_after_key(final_key, before=f"# {final_key}: {value}")
                d.pop(final_key)

        comment_key_path(data, key_path_list, valueToMatch)

        temp_file_path = f"{filePath}.tmp"
        with open(temp_file_path, 'w') as file:
            yaml.dump(data, file)
        os.replace(temp_file_path, filePath)

    def changeSharedDataUrl(self, newSharedDataUrl: str):
        """
        edits the dedicated yaml to add/change the shared data url
        """
        sharedDataUrl = self.config.dedicatedConfig.GameConfig.SharedDataURL
        if sharedDataUrl == newSharedDataUrl:
            log.info(f"The SharedDataURL is already set to '{newSharedDataUrl}'")
            return
        
        if sharedDataUrl is not None:
            log.info(f"There is a SharedDataURL configured in the dedicated yaml, will overwrite it: '{sharedDataUrl}' -> '{newSharedDataUrl}'")
        else:
            log.info(f"Adding the SharedDataURL property to the dedicated yaml: '{newSharedDataUrl}'")

        if self.config.paths.install.exists():
            dedicatedYamlPath = self.config.paths.install.joinpath(self.config.server.dedicatedYaml)

            # override extending install dir - for testing.
            if self.searchDedicatedYamlLocal:
                dedicatedYamlPath = self.config.server.dedicatedYaml
            if dedicatedYamlPath.exists():
                # replace the existing value of the shareddataurl with our new value, to do it in place, we'll only search&replace with regex by line
                self.upsertYamlProperty(dedicatedYamlPath, "GameConfig.SharedDataURL", newSharedDataUrl)
                # reload dedicated yaml config
                self.loadDedicatedYaml(self.config)
                return
            else:
                log.error(f"Could not read dedicated.yaml from path '{dedicatedYamlPath}'. Are you sure the path is correct?")
                raise AdminRequiredException(f"Could not read dedicated.yaml from path '{dedicatedYamlPath}'. Are you sure the path is correct?")
        else:
            log.error(f"Could not find install dir at  '{self.config.paths.install}'. Are you sure the config is correct?")
            raise AdminRequiredException(f"Could not find install dir at  '{self.config.paths.install}'. Are you sure the config is correct?")
        
    def commentOutSharedDataUrl(self, sharedDataUrl: str):
        """
        edits the dedicated yaml to comment out the shared data url if it contains the given shared data url
        """
        if self.config.dedicatedConfig.GameConfig.SharedDataURL is None:
            log.info(f"There is no SharedDataURL configured in the dedicated yaml, nothing to comment out")
            return False

        if self.config.dedicatedConfig.GameConfig.SharedDataURL != sharedDataUrl:
            log.info(f"There is a SharedDataURL configured, but it is not the one that was autoconfigured, so we won't edit it.")
            return False

        if self.config.paths.install.exists():
            dedicatedYamlPath = self.config.paths.install.joinpath(self.config.server.dedicatedYaml)

            # override extending install dir - for testing.
            if self.searchDedicatedYamlLocal:
                dedicatedYamlPath = self.config.server.dedicatedYaml
            if dedicatedYamlPath.exists():
                # replace the existing value of the shareddataurl with our new value, to do it in place, we'll only search&replace with regex by line
                self.commentOutYamlProperty(dedicatedYamlPath, "GameConfig.SharedDataURL", sharedDataUrl)

                # reload dedicated yaml config
                self.loadDedicatedYaml(self.config)
                return
            else:
                log.error(f"Could not read dedicated.yaml from path '{dedicatedYamlPath}'. Are you sure the path is correct?")
                raise AdminRequiredException(f"Could not read dedicated.yaml from path '{dedicatedYamlPath}'. Are you sure the path is correct?")
        else:
            log.error(f"Could not find install dir at  '{self.config.paths.install}'. Are you sure the config is correct?")
            raise AdminRequiredException(f"Could not find install dir at  '{self.config.paths.install}'. Are you sure the config is correct?")


    def setConfigFilePath(self, configFilePath: Path, searchDedicatedYamlLocal=False):
        """
        Set the path to the config file.
        """
        assert isinstance(configFilePath, Path), "configFilePath must be of type Path"
        # invalidate cached property
        try: 
            del self.config 
        except AttributeError: 
            pass
        self.configFilePath = configFilePath
        self.searchDedicatedYamlLocal = searchDedicatedYamlLocal

    def addToContext(self, key, value):
        """
        Add a value to the context
        """
        self.config.context[key] = value

    @cached_property
    def availableTerritories(self) -> List[Territory]:
        return self.readAvailableTerritories()
    
    def getAvailableTerritories(self) -> List[Territory]:
        return self.availableTerritories

    def readAvailableTerritories(self) -> List[Territory]:
        """
        return the list of available territories from galaxy config and custom config

        This will read it from the currently configured scenario's GalaxyConfig.ecf aswell, then add any custom configured one aswell
        """
        territories = []
        for territory in EsmGalaxyConfigReader(self.config).retrieveTerritories():
            territories.append(territory)

        if self.config.galaxy and self.config.galaxy.territories:
            for territory in self.config.galaxy.territories:
                territories.append(Territory(territory["faction"], territory["center-x"], territory["center-y"], territory["center-z"], territory["radius"]))
            
        # make sure there are no entries with the same name, retaining order
        territories = list(dict.fromkeys(territories, lambda x: x.name))
        return territories
