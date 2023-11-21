import logging
import yaml
from functools import cached_property
from pathlib import Path
from esm.ConfigModels import DediConfig, MainConfig
from esm.Exceptions import AdminRequiredException
from esm.ServiceRegistry import Service, ServiceRegistry
from esm.Tools import mergeDicts

log = logging.getLogger(__name__)

@Service
class EsmConfigService:
    """
    Contains all the relevant config for esm, backed by a yaml file that overwrites the default config in the model MainConfig.
    
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

    @cached_property
    def config(self) -> MainConfig:
        return self.getConfig()
    
    def getConfig(self) -> MainConfig:
        if isinstance(self.configFilePath, Path) and self.configFilePath.exists():
            log.debug(f"Reading configuration from path '{self.configFilePath}'")
            with open(self.configFilePath, "r") as configFile:
                configContent = yaml.safe_load(configFile)
                mainConfig = MainConfig.model_validate(configContent)
                self.loadDedicatedYaml(mainConfig)
                mergeDicts(a=mainConfig.context, b={"configFilePath": self.configFilePath})
                return mainConfig
        log.error(f"Could not read configuration from path '{self.configFilePath}'")
        raise AdminRequiredException(f"Could not read configuration from path '{self.configFilePath}'")
    
    def loadDedicatedYaml(self, mainConfig: MainConfig):
        """
        Reads the dedicated YAML file into the mainconfig.dedicatedConfig property.

        Args:
            mainConfig (MainConfig): The main configuration object.

        Returns:
            None
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
                log.error(f"Could not read dedicated.yaml from path '{dedicatedYamlPath}'. Are you sure the path is correct?")
                raise AdminRequiredException(f"Could not read dedicated.yaml from path '{dedicatedYamlPath}'. Are you sure the path is correct?")
        else:
            log.error(f"Could not find install dir at  '{mainConfig.paths.install}'. Are you sure the config is correct?")
            raise AdminRequiredException(f"Could not find install dir at  '{mainConfig.paths.install}'. Are you sure the config is correct?")
        
    def setConfigFilePath(self, configFilePath: Path, searchDedicatedYamlLocal=False):
        """
        Set the path to the config file.

        Parameters:
            configFilePath (Path): The path to the config file.

        Returns:
            None
        """
        assert isinstance(configFilePath, Path), "configFilePath must be of type Path"
        # invalidate cached property
        try: 
            del self.config 
        except AttributeError: 
            pass
        self.configFilePath = configFilePath
        self.searchDedicatedYamlLocal = searchDedicatedYamlLocal
