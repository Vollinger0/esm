import dotsi
import yaml
import logging

#log = logging.getLogger(__name__)

"""
Contains all the relevant config for esm, backed by a yaml file. Extended to be a dotsi dictionary that can be accessed directly with the dot-notation.
"""
class EsmConfig:

    def __init__(self, config):
        self.context = dotsi.Dict({})
        self.config = dotsi.Dict(config)
    
    @classmethod
    def fromConfig(cls, config):
        return cls(config)
    
    @classmethod
    def fromConfigFile(cls, configFilePath):
        with open(configFilePath, "r") as configFile:
            configurationDict = yaml.safe_load(configFile)
        return cls(configurationDict)

    def __getattr__(self, attr):
        return self.config.get(attr)
    
