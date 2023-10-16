import dotsi
import yaml

from esm.ServiceRegistry import Service

@Service
class EsmConfigService:
    """
    Contains all the relevant config for esm, backed by a yaml file. 

    Extended to be a dotsi dictionary that can be accessed directly with the dot-notation.
    """
    def __init__(self, configuration=None, configFilePath=None, context=None, customConfigFilePath=None):
        config = configuration
        if configFilePath:
            with open(configFilePath, "r") as configFile:
                config = yaml.safe_load(configFile)
            config.update({'context': {'configFilePath': configFilePath}})
            if customConfigFilePath:
                with open(customConfigFilePath, "r") as configFile:
                    customConfig = yaml.safe_load(configFile)
                config["context"].update({'customConfigFilePath': customConfigFilePath})
                config.update(customConfig)
        else:
            if configuration:
                config = configuration
            else:
                config = {}

        if context:
            config.get('context').update(context)
        self.config = dotsi.Dict(config)
    
    def __getattr__(self, attr):
        return self.config.get(attr)
