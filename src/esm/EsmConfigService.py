import dotsi
import yaml

from esm.ServiceRegistry import Service
from esm.Tools import mergeDicts

@Service
class EsmConfigService:
    """
    Contains all the relevant config for esm, backed by a yaml file. 

    Extended to be a dotsi dictionary that can be accessed directly with the dot-notation.
    """
    def __init__(self, configuration=None, configFilePath=None, context=None, customConfigFilePath=None):
        if configuration is None:
            config = {}
        else:
            config = configuration

        if configFilePath:
            with open(configFilePath, "r") as configFile:
                baseConfig = yaml.safe_load(configFile)
            mergeDicts(config, baseConfig)
            mergeDicts(config, {'context': {'configFilePath': configFilePath}})

        if customConfigFilePath:
            with open(customConfigFilePath, "r") as configFile:
                customConfig = yaml.safe_load(configFile)
            mergeDicts(config, customConfig)
            mergeDicts(config, {'context': {'customConfigFilePath': customConfigFilePath}})

        if context:
            mergeDicts(config["context"], context)

        # convert to dotsi dict, that allows the dictionary to be accessed via dotPath notation as attributes
        self.config = dotsi.Dict(config)
    
    def __getattr__(self, attr):
        return self.config.get(attr)
    