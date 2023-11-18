import logging
from pathlib import Path
import sys
import dotsi
import yaml
from esm.Exceptions import AdminRequiredException, ExitCodes

from esm.ServiceRegistry import Service
from esm.Tools import mergeDicts

log = logging.getLogger(__name__)

#@Service  # this is no service any more. We need this to be always properly initialized with a config
class EsmConfigService:
    """
    Contains all the relevant config for esm, backed by a yaml file. 

    Extended to be a dotsi dictionary that can be accessed directly with the dot-notation.

    Configuration may contain the base configuration, configfile will be merged with it, overwriting any property, customConfig will be merged after that overwriting any property again
    The context given will be kept as config.context and may be extended with context relevant information at runtime

    The merges will overwrite existing keys doing a recursive shallow copy so most of the configuration can be kept as is, this does not include arrays.

    For testing, you can override any property in the config by passing the override dictionary
    """
    def __init__(self, configuration: dict=None, configFilePath=None, context=None, customConfigFilePath=None, raiseExceptionOnMissingDedicated=True, override: dict=None):
        """
        since this is a service class, it will be created without any parameters first and later replaced with a parameterized version
        """

        if configuration is None:
            config = {}
        else:
            config = configuration

        if configFilePath:
            if not configFilePath.exists():
                log.error(f"could not find configuration file at {configFilePath}. This is fatal")
                sys.exit(ExitCodes.MISSING_CONFIG)

            with open(configFilePath, "r") as configFile:
                baseConfig = yaml.safe_load(configFile)
            mergeDicts(config, baseConfig)
            mergeDicts(config, {'context': {'configFilePath': configFilePath}})

        if customConfigFilePath:
            if customConfigFilePath.exists():
                with open(customConfigFilePath, "r") as configFile:
                    customConfig = yaml.safe_load(configFile)
                mergeDicts(config, customConfig)
                mergeDicts(config, {'context': {'customConfigFilePath': customConfigFilePath}})
            else:
                log.warning(f"No custom configuration file at {customConfigFilePath}. Script will run with default values!")

        if context:
            mergeDicts(config["context"], context)

        # if a dedicated yaml was defined (has to), read and merge it into the config
        if len(config) > 0:
            self.mergeWithDedicatedYaml(config, raiseExceptionOnMissingDedicated)

        # overwrite all values from the override - should be used for testing purposes only, o.c.
        if override is not None and len(override) > 0:
            mergeDicts(config, override, logOverwrites=True)

        # convert to dotsi dict, that allows the dictionary to be accessed via dotPath notation as attributes
        self.config = dotsi.Dict(config)
    
    def __getattr__(self, attr):
        return self.config.get(attr)

    def mergeWithDedicatedYaml(self, config: dict, raiseExceptionOnMissingDedicated):
        """
        after init, this config should contain the path to the dedicated yaml, we'll look for some infos there, namely:
        - savegame name
        - path to saves
        """
        serverConfig = config.get("server")
        if serverConfig is None or 'dedicatedYaml' not in serverConfig:
            self.raiseOrLog(raiseExceptionOnMissingDedicated, f"could not find configured path to dedicated.yaml. This is fatal, please make sure the path to it in the configuration is correct under server.dedicatedYaml.")
            return
        
        pathConfig = config.get("paths")
        if pathConfig is None or 'install' not in pathConfig:
            self.raiseOrLog(raiseExceptionOnMissingDedicated, f"could not find configured installation dir. This is fatal, please make sure the path to it in the configuration is correct under paths.install.")
            return

        installDir = Path(config.get("paths").get("install")).resolve()
        dedicatedYamlPath = Path(f"{installDir}/{config.get("server").get('dedicatedYaml')}").resolve()
        if not dedicatedYamlPath.exists():
            self.raiseOrLog(raiseExceptionOnMissingDedicated, f"could not find dedicated yaml at '{dedicatedYamlPath}'. This is fatal, please make sure the path to it in the configuration is correct and the file exists.")
            return

        #log.debug(f"Reading dedicated yaml from '{dedicatedYamlPath}'")
        mergeDicts(config, {'context': {'dedicatedYamlPath': dedicatedYamlPath}})
        with open(dedicatedYamlPath, "r") as configFile:
            dedicated = yaml.safe_load(configFile)

        # add config to our config
        dedicatedConfig = {"dedicatedYaml": dedicated}
        mergeDicts(config, dedicatedConfig)

    def raiseOrLog(self, raiseExceptionOnMissingDedicated, message):
        if raiseExceptionOnMissingDedicated:
            raise AdminRequiredException(message)
        else:
            log.error(message)

        # the most interesting configs from there will be:
        #dedicated.ServerConfig.SaveDirectory
        #dedicated.ServerConfig.AdminConfigFile
        #dedicated.GameConfig.GameName
        #dedicated.GameConfig.CustomScenario
